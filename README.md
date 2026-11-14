# Nordic Energy Data Pipeline

A data engineering project focused on collecting, validating, and processing Danish electricity market data using Python and AWS.

The project uses the [Energi Data Service](https://www.energidataservice.dk/) API to retrieve day-ahead electricity prices for Denmark's DK1 and DK2 price areas. The goal is to build an automated pipeline that stores and transforms the data for further analysis.

## Tech Stack

**Currently used:** Python, Pandas, Requests, Boto3, AWS S3, JSON, Parquet, Git, GitHub

**Planned:** AWS Lambda, EventBridge Scheduler, CloudWatch, Databricks, PySpark, Delta Lake, SQL, dbt, DuckDB, Streamlit

## Pipeline Overview

### 1. Data Extraction & Validation

`api_data_extraction.ipynb`

Retrieves electricity prices from the Energi Data Service API and saves the raw response as JSON.

The following data quality checks are included:

- Missing values and duplicate records
- Valid price areas (DK1 and DK2)
- Price data types and timestamp validation
- Missing 15-minute intervals

### 2. Data Preparation

`data_preparation.ipynb`

Converts JSON records into a Pandas DataFrame, prepares the timestamp columns, adds a delivery date, and exports the data to Parquet.

### 3. AWS Cloud Storage

`aws_s3_integration.ipynb`

Uses Boto3 to upload raw JSON and processed Parquet files to Amazon S3, with separate storage paths and upload verification.

```text
s3://nordic-energy-data-pipeline-yh2026/
├── raw/dayaheadprices/
│   └── ingestion_date=YYYY-MM-DD/prices.json
└── processed/dayaheadprices/
    └── ingestion_date=YYYY-MM-DD/day_ahead_prices.parquet
```

The initial dataset contains **1,344 records** covering 1–7 November 2026 for DK1 and DK2. All implemented data quality checks passed on this dataset.

## Project Structure

```text
Nordic Energy Data Pipeline/
├── scripts/
│   ├── api_data_extraction.ipynb
│   ├── data_preparation.ipynb
│   ├── aws_s3_integration.ipynb
│   └── energy_pipeline.py
├── json_data_file/
├── data/
│   └── processed/
├── requirements.txt
└── README.md
```

Raw and processed datasets are generated locally and excluded from Git. The `energy_pipeline.py` script runs the daily job independently of the notebooks.

## Getting Started

Clone the repository and install the dependencies:

```bash
git clone https://github.com/Yassdata/Nordic-energy-data-pipeline.git
cd Nordic-energy-data-pipeline

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the notebooks in VS Code using the project's Python environment.

Run them in this order:

1. `api_data_extraction.ipynb` — Extract and validate electricity prices.
2. `data_preparation.ipynb` — Prepare the data and export to Parquet.
3. `aws_s3_integration.ipynb` — Upload and verify files in S3 (requires configured AWS access).

## Daily ingestion script

The script requests tomorrow's prices using Copenhagen calendar dates. It
validates a full day for DK1 and DK2 before creating either output. Each area
must have 96 quarter-hours on a normal day, 92 when clocks move forward, or
100 when they move back.

Run the tests from the repo root with the project's Python environment active:

```bash
python -B -m unittest discover -s tests -v
```

To check tomorrow's live response and write only to a new temporary directory:

```bash
scratch="$(mktemp -d)"
python -B scripts/energy_pipeline.py --local-output "$scratch/output"
```

Run after tomorrow's prices are published. For an offline check, add
`--input-json /path/to/single-day-response.json --delivery-date YYYY-MM-DD`.
The input must contain exactly one complete delivery day, including both zones.
Local mode does not create an AWS client and refuses to reuse an output directory.

An intentional AWS run requires `--upload` and `ENERGY_S3_BUCKET`. Boto3 uses
its normal credential chain; set `AWS_PROFILE` locally if you want to select a
configured profile. For Lambda, configure
`scripts.energy_pipeline.lambda_handler` when packaging from the repo root,
include the dependencies for the Lambda runtime and architecture, set
`ENERGY_S3_BUCKET`, and use the execution role. Do not put AWS keys in source
or Lambda environment variables.

Daily S3 keys are separate from the notebooks' historical `ingestion_date` keys:

```text
raw/dayaheadprices/delivery_date=YYYY-MM-DD/prices.json
processed/dayaheadprices/delivery_date=YYYY-MM-DD/day_ahead_prices.parquet
```

The role needs `s3:PutObject` on both prefixes and `s3:GetObject` to check
existing objects. S3 refuses overwrites. If a run stops after uploading raw JSON,
a retry with matching content can finish the Parquet upload; a content mismatch
fails and leaves the existing object in place. The two uploads are separate
operations.

## Next Steps

- Automate daily extraction and S3 uploads using **AWS Lambda and EventBridge Scheduler**.
- Build **Bronze, Silver, and Gold** data layers using Databricks, PySpark, and Delta Lake.
- Use SQL, dbt, and DuckDB for transformations and electricity price analysis.
- Develop a Streamlit dashboard to compare DK1 and DK2 prices, explore historical trends, and identify lower-price periods.

## Data Source

[Energi Data Service — DayAheadPrices](https://www.energidataservice.dk/)