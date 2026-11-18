# ⚡ Danish Electricity Price Analytics 🇩🇰

An end-to-end data engineering project built to support **recurring, ongoing reports on Danish electricity prices** using real day-ahead data from Energinet. The pipeline collects and validates prices for **DK1 (Western Denmark)** and **DK2 (Eastern Denmark)**, stores them in Amazon S3, and is being extended with a **Databricks medallion architecture** for reporting and analytics.

The goal is to keep reports up to date as new prices arrive: compare regions, track price patterns over time, and identify cheaper periods through reusable SQL analysis and an interactive Streamlit app. Historical storage, repeatable transformations, and consistent quality checks provide the foundation for reliable reporting across successive days, weeks, and months.

**Current stage:** Working toward the **Bronze → Silver → Gold** structure in Databricks using PySpark and Delta Lake. Direct access to the private S3 bucket is pending; no active Unity Catalog external location or successful Databricks read has been verified.

## 📍 Project Status

| Stage | Status |
|---|---|
| Explore the Energinet API and validate initial data | Completed |
| Prepare JSON and Parquet datasets | Completed |
| Upload raw and processed data to Amazon S3 | Completed |
| Build the daily ingestion script | Completed |
| Deploy and manually test AWS Lambda | Completed — tested on 14 November 2026 |
| Connect Databricks to private S3 data | Pending — external location and successful read not verified |
| Build the Databricks medallion structure | In progress — S3 access pending |
| Develop reusable SQL analytics and recurring reports | Planned |
| Build the Streamlit app | Planned |
| Verify EventBridge scheduling | IAM execution role exists with recent activity; schedule and invocation unverified |
| Verify CloudWatch monitoring | Execution logs and failure alerting unverified |

## 🗺️ Architecture

```text
Energinet API
    ↓
Python ingestion on AWS Lambda
    ↓
Amazon S3 — raw JSON + prepared Parquet
    ↓
Databricks / PySpark / Delta Lake          ← Current work
    Bronze → Silver → Gold
    ↓
SQL analytics and recurring reports      ← Planned
    ↓
Streamlit app                            ← Planned
```

![Project architecture](PROJECT_ARCHITECTURE.png)

The architecture image shows the overall project design. Ingestion, S3 storage, and a manual Lambda test are confirmed. Scheduled invocation and CloudWatch monitoring still require verification. Work on the Databricks layer is in progress, with direct S3 access pending.

## 🛠️ Technology Stack

| Area | Technologies | Status |
|---|---|---|
| Extraction and preparation | Python, Requests, Pandas, PyArrow | Implemented |
| Storage and cloud execution | Amazon S3, AWS Lambda, Boto3 | Implemented |
| Data formats | JSON, Parquet | Implemented |
| Lakehouse processing | Databricks, PySpark, Delta Lake | In progress |
| Analytics and recurring reporting | SQL | Planned |
| Visualization | Streamlit | Planned |
| Scheduling and monitoring | EventBridge, CloudWatch | Scheduler role exists; scheduling, logs, and alerting require verification |
| Version control | Git, GitHub | In use |

## 🔄 Data Pipeline

### 1. Extract and validate prices

The initial exploration in [`scripts/api_data_extraction.ipynb`](scripts/api_data_extraction.ipynb) uses Energinet's `DayAheadPrices` dataset for DK1 and DK2. It checks missing values, duplicates, price areas, price types, timestamps, and missing 15-minute intervals.

The initial dataset contains **1,344 records covering 1–7 November 2026**, with the implemented quality checks passing.

### 2. Prepare and store data

[`scripts/data_preparation.ipynb`](scripts/data_preparation.ipynb) prepares timestamps and delivery dates and exports Parquet while preserving the original price precision. [`scripts/aws_s3_integration.ipynb`](scripts/aws_s3_integration.ipynb) uploads the original JSON and prepared Parquet to S3.

The daily pipeline uses this layout:

```text
s3://nordic-energy-data-pipeline-yh2026/
├── raw/dayaheadprices/delivery_date=YYYY-MM-DD/prices.json
└── processed/dayaheadprices/delivery_date=YYYY-MM-DD/day_ahead_prices.parquet
```

The earlier notebook uploads use `ingestion_date=YYYY-MM-DD` partitions instead of `delivery_date=YYYY-MM-DD`. These existing S3 paths are ingestion outputs; the Databricks medallion layers are the current development stage.

### 3. Run ingestion through AWS Lambda

[`scripts/energy_pipeline.py`](scripts/energy_pipeline.py) combines extraction, validation, JSON/Parquet output, and optional S3 upload. It:

- Calculates tomorrow's delivery date in the `Europe/Copenhagen` timezone.
- Validates complete DK1/DK2 coverage, with **96 quarter-hour observations per area** on normal days and **92 or 100** on daylight saving transition days.
- Retries transient API failures and incomplete responses.
- Preserves the raw API response alongside prepared Parquet.
- Supports safe retries and rejects conflicting S3 overwrites.

The pipeline was deployed to **AWS Lambda and manually tested successfully on 14 November 2026**. Lambda authenticates through an IAM execution role. See [AWS setup and deployment notes](docs/AWS_SETUP.md) for the documented configuration.

### AWS deployment, scheduling, and monitoring

- **Confirmed:** The ingestion pipeline was deployed to AWS Lambda and manually tested successfully on 14 November 2026. The `nordic-energy` AWS CLI profile was also verified to have access to the project's S3 bucket in `eu-north-1`.
- **EventBridge Scheduler:** An IAM execution role exists and shows recent activity. The daily schedule, timezone, Lambda target, and successful scheduled invocation still need to be verified.
- **CloudWatch:** Lambda execution logs and failure alerting still need to be verified.
- **Databricks:** Direct access to the private S3 bucket is pending. No active Unity Catalog external location or successful Databricks read has been verified.

### 4. Build the Databricks medallion structure — in progress

Once S3 access is established and a Databricks read succeeds, the medallion structure will organize the data into three Delta Lake layers:

| Layer | Intended role |
|---|---|
| **Bronze** | Ingest source data from S3 and retain source records for downstream processing. |
| **Silver** | Apply consistent types, clean and validate records, and handle duplicates for reliable DK1/DK2 price data. |
| **Gold** | Prepare reusable reporting tables and summaries for recurring regional comparisons, price trends, and cheaper-period analysis. |

Databricks notebooks and table definitions will be added to this repository as the implementation progresses.

### 5. Produce recurring reports and visualize results — planned

Reusable SQL queries will use the Gold layer to produce ongoing reports comparing DK1 and DK2, tracking price trends, and identifying cheaper periods. The intended workflow will refresh reporting tables as new data arrives, so the same reporting logic can run consistently over an expanding history. Report scheduling and refresh orchestration remain to be implemented.

A Streamlit app will provide access to the latest reporting results and interactive historical exploration. Any savings estimates will need to distinguish spot prices from the customer's total electricity cost, including tariffs and contract terms.

## 🚀 Getting Started

The local setup runs the Python ingestion pipeline. Databricks processing is being built separately in the workspace.

```bash
git clone https://github.com/Yassdata/Nordic-energy-data-pipeline.git
cd Nordic-energy-data-pipeline
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The pinned dependencies in [`requirements.txt`](requirements.txt) were verified for Python 3.12.

### Run locally

Fetch tomorrow's data and write it locally:

```bash
scratch="$(mktemp -d)"
python -B scripts/energy_pipeline.py --local-output "$scratch/output"
```

To use a saved, complete single-day API response:

```bash
scratch="$(mktemp -d)"
python -B scripts/energy_pipeline.py \
  --input-json /path/to/single-day-response.json \
  --delivery-date YYYY-MM-DD \
  --local-output "$scratch/output"
```

### Upload to S3

With valid AWS authentication configured:

```bash
export AWS_PROFILE=nordic-energy
export ENERGY_S3_BUCKET=nordic-energy-data-pipeline-yh2026
python -B scripts/energy_pipeline.py --upload
```

Local development can use the named AWS profile; Lambda uses its IAM execution role. See [AWS Setup](docs/AWS_SETUP.md).

## 🧪 Testing and Data Quality

Run the automated ingestion tests:

```bash
python -B -m unittest discover -s tests -v
```

The tests cover Copenhagen delivery dates, daylight saving transitions, missing and duplicate intervals, invalid prices and areas, retry behavior, local JSON/Parquet output, Lambda uploads, and S3 overwrite safeguards.

## 📁 Repository Structure

```text
├── scripts/
│   ├── api_data_extraction.ipynb   # Initial API exploration and checks
│   ├── data_preparation.ipynb     # Timestamp preparation and Parquet export
│   ├── aws_s3_integration.ipynb   # Initial S3 uploads
│   └── energy_pipeline.py        # CLI and Lambda ingestion pipeline
├── tests/
│   └── test_energy_pipeline.py
├── json_data_file/                # Local raw data
├── data/processed/                # Local prepared data
├── docs/
│   └── AWS_SETUP.md
├── PROJECT_ARCHITECTURE.png
├── requirements.txt
└── README.md
```

## 📊 What's Next?

1. **Establish Databricks access to S3:** Configure and verify private bucket access, including the Unity Catalog external location, and confirm a successful read.
2. **Build the Databricks medallion structure:** Build and validate Bronze, Silver, and Gold Delta tables with PySpark, and add notebooks and setup documentation to the repository.
3. **Verify AWS automation and monitoring:** Confirm the daily schedule, timezone, Lambda target, successful scheduled invocation, execution logs, and failure alerting.
4. **Develop recurring reports:** Create reusable SQL queries for DK1/DK2 comparisons, price trends, and cheaper periods, and implement reporting refreshes as new data arrives.
5. **Build the Streamlit app:** Present the latest reports and make historical comparisons and price exploration interactive.

## 🌍 Future Possibilities

Expand beyond Denmark to compare electricity prices across other Nordic countries.

## 📚 Data Source

[Energinet — Energi Data Service](https://www.energidataservice.dk/), using the `DayAheadPrices` dataset for DK1 and DK2.
