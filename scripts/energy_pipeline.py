"""Ingest tomorrow's Danish day-ahead prices from Energinet."""

import argparse
import hashlib
import json
import logging
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

LOG = logging.getLogger(__name__)
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
UTC = timezone.utc
DAY = timedelta(days=1)
QUARTER = timedelta(minutes=15)
URL = "https://api.energidataservice.dk/dataset/DayAheadPrices"
ZONES = ("DK1", "DK2")
PRICES = ("DayAheadPriceEUR", "DayAheadPriceDKK")
TIMEOUT = (5, 15)  # Connection and read timeouts, in seconds.
ATTEMPTS = 4
SCHEMA = pa.schema([
    ("TimeUTC", pa.timestamp("ns", tz="UTC")),
    ("TimeDK", pa.timestamp("ns")),
    ("PriceArea", pa.string()),
    ("DayAheadPriceEUR", pa.float64()),
    ("DayAheadPriceDKK", pa.float64()),
    ("DeliveryDate", pa.date32()),
])


class InvalidData(ValueError):
    """The response is not a complete, valid delivery day."""


def tomorrow(now=None):
    # I add a calendar day after finding today's date in Copenhagen.
    return (now or datetime.now(UTC)).astimezone(COPENHAGEN).date() + DAY


def validate(payload, day):
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        raise InvalidData("Energinet returned no records for the delivery date.")

    # I convert both local midnights to UTC to count the real quarter hours.
    start = datetime.combine(day, datetime.min.time(), COPENHAGEN).astimezone(UTC)
    end = datetime.combine(day + DAY, datetime.min.time(), COPENHAGEN).astimezone(UTC)
    quarters = range((end - start) // QUARTER)
    expected = {start + i * QUARTER for i in quarters}
    seen = {zone: set() for zone in ZONES}
    rows = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise InvalidData(f"Record {index} is not a JSON object.")
        zone = record.get("PriceArea")
        if zone not in ZONES:
            raise InvalidData(f"Record {index} is outside DK1/DK2.")

        # I use UTC to tell the two occurrences of the autumn hour apart.
        try:
            stamp = datetime.fromisoformat(record["TimeUTC"])
            if stamp.utcoffset() not in (None, timedelta(0)):
                raise ValueError("TimeUTC must be UTC")
            stamp = stamp.replace(tzinfo=UTC)
            local = datetime.fromisoformat(record["TimeDK"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidData(f"Record {index} has an invalid timestamp.") from exc
        if stamp not in expected or local != stamp.astimezone(COPENHAGEN).replace(tzinfo=None):
            raise InvalidData(f"{zone}: invalid delivery interval {stamp.isoformat()}.")
        if stamp in seen[zone]:
            raise InvalidData(f"{zone}: duplicate interval {stamp.isoformat()}.")
        seen[zone].add(stamp)

        for field in PRICES:
            price = record.get(field)
            if type(price) not in (int, float) or not math.isfinite(price):
                raise InvalidData(f"{zone} at {stamp.isoformat()}: invalid {field}.")
        rows.append({
            "TimeUTC": stamp, "TimeDK": local, "PriceArea": zone,
            **{field: record[field] for field in PRICES}, "DeliveryDate": day,
        })

    missing = {zone: len(expected - seen[zone]) for zone in ZONES}
    if any(missing.values()):
        raise InvalidData(f"Incomplete delivery date {day}; missing intervals: {missing}.")
    return sorted(rows, key=lambda row: (row["TimeUTC"], row["PriceArea"]))


def decode(raw, day):
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise InvalidData("Energinet response is not valid JSON.") from exc
    return validate(payload, day)


def retry_delay(response, attempt):
    delay = 2 ** attempt
    if response is not None and (header := response.headers.get("Retry-After")):
        try:
            seconds = int(header)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        delay = max(delay, seconds)
    return delay


def fetch(day):
    # I ask for tomorrow from midnight up to, but excluding, the next midnight.
    params = {
        "start": day.isoformat(),
        "end": (day + DAY).isoformat(),
        "filter": json.dumps({"PriceArea": ZONES}),
        "sort": "TimeUTC asc,PriceArea asc",
        "limit": "0",
    }
    for attempt in range(1, ATTEMPTS + 1):
        response = None
        try:
            response = requests.get(URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            raw = response.content
            return raw, decode(raw, day)
        except (requests.RequestException, InvalidData) as exc:
            if isinstance(exc, requests.HTTPError):
                status = response.status_code
                if status not in (408, 429) and not 500 <= status < 600:
                    raise
            elif not isinstance(exc, (requests.Timeout, requests.ConnectionError,
                                      requests.exceptions.ChunkedEncodingError, InvalidData)):
                raise

            delay = retry_delay(response, attempt)
            if attempt == ATTEMPTS or delay > 60:
                raise
            LOG.warning("Energinet %s attempt %s/%s failed: %s; retrying in %gs",
                        day, attempt, ATTEMPTS, exc, delay)
            time.sleep(delay)


def artifacts(day, raw, rows):
    # I keep the API response as received and match the notebook's Parquet columns.
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer, compression="snappy")
    partition = f"dayaheadprices/delivery_date={day.isoformat()}"
    return (
        (f"raw/{partition}/prices.json", raw, "application/json"),
        (f"processed/{partition}/day_ahead_prices.parquet",
         buffer.getvalue().to_pybytes(), "application/vnd.apache.parquet"),
    )


def put_once(s3, bucket, key, body, content_type):
    # I let S3 reject overwrites, even when two runs arrive at the same time.
    digest = hashlib.sha256(body).hexdigest()
    for attempt in range(3):
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type,
                          IfNoneMatch="*", Metadata={"sha256": digest})
            LOG.info("Uploaded s3://%s/%s", bucket, key)
            return
        except ClientError as exc:
            status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
            if status == 409 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            if status != 412:
                raise
            # I can resume a partial upload if the existing object matches these bytes.
            existing = s3.head_object(Bucket=bucket, Key=key)
            if existing.get("Metadata", {}).get("sha256") != digest:
                raise RuntimeError(f"s3://{bucket}/{key} already exists with different "
                                   "or unverified content.") from exc
            LOG.info("Already stored s3://%s/%s (matching SHA-256)", bucket, key)
            return


def run(day, *, bucket=None, output=None, input_json=None):
    LOG.info("Starting DayAheadPrices for delivery_date=%s", day)
    if input_json is None:
        raw, rows = fetch(day)
    else:
        raw = input_json.read_bytes()
        rows = decode(raw, day)
    LOG.info("Validated %s records across DK1 and DK2 for %s", len(rows), day)
    files = artifacts(day, raw, rows)

    if output is not None:
        # I use a new output directory so a local test cannot replace old files.
        output.mkdir(parents=True, exist_ok=False)
        for key, body, _ in files:
            path = output / key
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(body)
            LOG.info("Wrote %s", path)
    else:
        # Boto3 looks up my local profile or the Lambda execution role on its own.
        s3 = boto3.client("s3", config=Config(
            connect_timeout=5, read_timeout=15,
            retries={"mode": "standard", "total_max_attempts": 3},
        ))
        for key, body, content_type in files:
            put_once(s3, bucket, key, body, content_type)

    return {"delivery_date": day.isoformat(), "records": len(rows),
            "keys": [key for key, _, _ in files]}


def bucket_name():
    bucket = os.environ.get("ENERGY_S3_BUCKET", "").strip()
    if not bucket:
        raise ValueError("Set ENERGY_S3_BUCKET for S3 uploads.")
    return bucket


def lambda_handler(event, context):
    LOG.setLevel(logging.INFO)
    try:
        return run(tomorrow(), bucket=bucket_name())
    except Exception:
        # I raise the error again so Lambda records the invocation as failed.
        LOG.exception("DayAheadPrices Lambda job failed")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local-output", type=Path, metavar="NEW_DIR")
    mode.add_argument("--upload", action="store_true", help="Write to ENERGY_S3_BUCKET.")
    parser.add_argument("--input-json", type=Path, help="Read a saved API response locally.")
    parser.add_argument("--delivery-date", type=date.fromisoformat, metavar="YYYY-MM-DD",
                        help="Delivery date of the saved API response.")
    args = parser.parse_args(argv)
    if args.input_json is not None or args.delivery_date is not None:
        if args.local_output is None or args.input_json is None or args.delivery_date is None:
            parser.error("--input-json and --delivery-date must be used together with --local-output")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(args.delivery_date or tomorrow(), output=args.local_output,
            input_json=args.input_json, bucket=bucket_name() if args.upload else None)
    except Exception:
        LOG.exception("DayAheadPrices job failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
