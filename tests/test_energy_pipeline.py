import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import boto3
import pyarrow.parquet as pq
import requests
from botocore.stub import ANY, Stubber

from scripts import energy_pipeline as job


def response_body(day, first_utc, count):
    start = datetime.fromisoformat(first_utc)
    records = []
    for i in range(count):
        utc = start + timedelta(minutes=15 * i)
        for zone in ("DK1", "DK2"):
            records.append({
                "TimeUTC": utc.isoformat(),
                "TimeDK": (datetime.combine(day, datetime.min.time())
                           + timedelta(minutes=15 * i)).isoformat(),
                "PriceArea": zone,
                "DayAheadPriceEUR": -2.5,
                "DayAheadPriceDKK": -18.7,
            })
    return records


class PipelineTests(unittest.TestCase):
    def test_tomorrow_uses_copenhagen_around_utc_midnight(self):
        self.assertEqual(
            job.tomorrow(datetime(2026, 11, 14, 23, 30, tzinfo=timezone.utc)),
            date(2026, 11, 16),
        )

    def test_regular_and_dst_days_have_exact_quarter_hours_per_zone(self):
        for day, start, quarters in (
            (date(2026, 11, 15), "2026-11-14T23:00:00", 96),
            (date(2026, 3, 29), "2026-03-28T23:00:00", 92),
            (date(2026, 10, 25), "2026-10-24T22:00:00", 100),
        ):
            with self.subTest(day=day):
                records = response_body(day, start, quarters)
                # Use the same clock for the two occurrences of 02:00 in October.
                if quarters == 100:
                    for i in range(24, 32):
                        records[i]["TimeDK"] = records[i - 8]["TimeDK"]
                    for i in range(32, len(records)):
                        records[i]["TimeDK"] = (
                            datetime.fromisoformat(records[i]["TimeDK"])
                            - timedelta(hours=1)
                        ).isoformat()
                elif quarters == 92:
                    for row in records[16:]:
                        row["TimeDK"] = (
                            datetime.fromisoformat(row["TimeDK"]) + timedelta(hours=1)
                        ).isoformat()
                normalized = job.validate({"records": records[::-1]}, day)
                self.assertEqual(len(normalized), quarters * 2)
                self.assertEqual(normalized[0]["TimeUTC"].isoformat(), start + "+00:00")
                self.assertEqual(normalized[0]["DeliveryDate"], day)
                if quarters == 100:
                    self.assertEqual(normalized[16]["TimeDK"], normalized[24]["TimeDK"])
                    self.assertNotEqual(normalized[16]["TimeUTC"], normalized[24]["TimeUTC"])

    def test_rejects_missing_duplicate_extra_bad_price_and_empty_rows(self):
        day = date(2026, 11, 15)
        records = response_body(day, "2026-11-14T23:00:00", 96)
        for bad in (
            [],
            records[:-1],
            records[:-1] + [records[0]],
            records[:-1] + [dict(records[-1], TimeUTC="2026-11-15T23:00:00")],
            records[:-1] + [dict(records[-1], TimeUTC="2026-11-15T22:46:00")],
            records[:-1] + [dict(records[-1], DayAheadPriceDKK=None)],
            records[:-1] + [dict(records[-1], PriceArea="SE1")],
        ):
            with self.subTest(row_count=len(bad)):
                with self.assertRaises(job.InvalidData):
                    job.validate({"records": bad}, day)

    def test_retries_timeout_and_incomplete_response_then_preserves_bytes(self):
        day = date(2026, 11, 15)
        raw = json.dumps({"records": response_body(day, "2026-11-14T23:00:00", 96)},
                         indent=2).encode()
        empty = requests.Response()
        empty.status_code, empty._content = 200, b'{"records": []}'
        ready = requests.Response()
        ready.status_code, ready._content = 200, raw
        with patch.object(job.requests, "get", side_effect=[
            requests.Timeout(), empty, ready,
        ]) as get, patch.object(job.time, "sleep"), self.assertLogs(job.LOG, "WARNING"):
            received, rows = job.fetch(day)
        self.assertEqual(received, raw)
        self.assertEqual(len(rows), 192)
        self.assertEqual(get.call_count, 3)
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["start"], params["end"]), ("2026-11-15", "2026-11-16"))
        self.assertEqual(json.loads(params["filter"]), {"PriceArea": ["DK1", "DK2"]})
        self.assertEqual(params["limit"], "0")
        self.assertTrue(all(x > 0 for x in get.call_args.kwargs["timeout"]))

    def test_http_400_is_not_retried(self):
        response = requests.Response()
        response.status_code = 400
        with patch.object(job.requests, "get", return_value=response) as get:
            with self.assertRaises(requests.HTTPError):
                job.fetch(date(2026, 11, 15))
        self.assertEqual(get.call_count, 1)

    def test_fixture_cli_writes_raw_bytes_and_parquet_without_s3(self):
        day = date(2026, 11, 15)
        raw = json.dumps({"records": response_body(day, "2026-11-14T23:00:00", 96)},
                         indent=2).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(job.boto3, "client") as s3, \
                patch.object(job.requests, "get") as get:
            root = Path(tmp)
            fixture = root / "sample.json"
            fixture.write_bytes(raw)
            out = root / "new-output"
            args = ["--local-output", str(out), "--input-json", str(fixture),
                    "--delivery-date", str(day)]
            self.assertEqual(job.main(args), 0)
            files = {p.name: p for p in out.rglob("*") if p.is_file()}
            self.assertEqual(files["prices.json"].read_bytes(), raw)
            table = pq.ParquetFile(files["day_ahead_prices.parquet"]).read()
            self.assertEqual(table.num_rows, 192)
            self.assertEqual(table["DeliveryDate"][0].as_py(), day)
            self.assertEqual(table["TimeUTC"][0].as_py().isoformat(), "2026-11-14T23:00:00+00:00")
            with self.assertLogs(job.LOG, "ERROR"):
                self.assertEqual(job.main(args), 1)
            self.assertEqual(files["prices.json"].read_bytes(), raw)
            s3.assert_not_called()
            get.assert_not_called()

    def test_lambda_uploads_both_delivery_date_keys(self):
        day = date(2026, 11, 15)
        rows = response_body(day, "2026-11-14T23:00:00", 96)
        response = requests.Response()
        response.status_code, response._content = 200, json.dumps({"records": rows}).encode()
        client = boto3.client("s3", region_name="eu-west-1",
                              aws_access_key_id="testing", aws_secret_access_key="testing")
        keys = ["raw/dayaheadprices/delivery_date=2026-11-15/prices.json",
                "processed/dayaheadprices/delivery_date=2026-11-15/day_ahead_prices.parquet"]
        with Stubber(client) as stub, patch.object(job.boto3, "client", return_value=client), \
                patch.object(job.requests, "get", return_value=response), \
                patch.object(job, "tomorrow", return_value=day), \
                patch.dict(os.environ, {"ENERGY_S3_BUCKET": "test-bucket"}):
            for key, body, mime in zip(
                keys, (response.content, ANY), ("application/json", "application/vnd.apache.parquet")
            ):
                stub.add_response("put_object", {}, {
                    "Bucket": "test-bucket", "Key": key, "Body": body,
                    "ContentType": mime, "IfNoneMatch": "*", "Metadata": ANY,
                })
            result = job.lambda_handler({}, None)
            stub.assert_no_pending_responses()
        self.assertEqual(result, {"delivery_date": str(day), "records": 192, "keys": keys})

    def test_s3_retries_same_payload_and_refuses_different_payload(self):
        client = boto3.client("s3", region_name="eu-west-1",
                              aws_access_key_id="testing", aws_secret_access_key="testing")
        key = "raw/dayaheadprices/delivery_date=2026-11-15/prices.json"
        with Stubber(client) as stub:
            params = {"Bucket": "test-bucket", "Key": key, "Body": b"hello",
                      "ContentType": "application/json", "IfNoneMatch": "*",
                      "Metadata": {"sha256": hashlib.sha256(b"hello").hexdigest()}}
            for metadata in (params["Metadata"], {"sha256": "different"}):
                stub.add_client_error("put_object", "PreconditionFailed", http_status_code=412,
                                      expected_params=params)
                stub.add_response("head_object", {"Metadata": metadata},
                                  {"Bucket": "test-bucket", "Key": key})
            job.put_once(client, "test-bucket", key, b"hello", "application/json")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                job.put_once(client, "test-bucket", key, b"hello", "application/json")
            stub.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
