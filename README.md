# ⚡ End-to-End Danish Electricity Price Analytics | Real Energinet Data 🇩🇰

Ever wondered why electricity prices change throughout the day, or why they can be different across Denmark? In this project, I'm exploring **real day-ahead electricity prices from [Energinet's Energi Data Service API](https://www.energidataservice.dk/)**, covering Denmark's two electricity price areas, **DK1 (Western Denmark) and DK2 (Eastern Denmark)**. Using Python, AWS, and data engineering tools, I'm building an automated system that collects, validates, and prepares this data for analysis. The goal is to uncover price patterns, compare electricity prices across regions, and identify the cheapest hours to use electricity, turning real market data into practical insights that anyone can understand.

## 🗺️ Architecture

![Project architecture — implemented and planned stages](PROJECT_ARCHITECTURE.png)

The diagram distinguishes the **implemented ingestion and storage pipeline** from the **planned analytics and web app**. EventBridge and CloudWatch are supporting services whose configuration still needs verification.

## 🛠️ Technologies

**Implemented:** Python, Pandas, Requests, Boto3, Amazon S3, AWS Lambda, JSON, Parquet, Git and GitHub.

**Planned:** Databricks, PySpark, Delta Lake, SQL and Streamlit.

**To verify and document:** EventBridge scheduling and CloudWatch monitoring.

## 🔄 How the Project Works

The idea is to take real electricity prices from Energinet and turn them into reliable, organized data that will eventually power an **interactive web app where anyone can explore electricity prices, compare regions, and discover cheaper hours to use electricity**.

### 1. Collecting real electricity prices

`scripts/api_data_extraction.ipynb` connects to Energinet's `DayAheadPrices` API for DK1 and DK2. It checks missing values, duplicate records, invalid price areas, price types, timestamps and missing 15-minute intervals.

The initial dataset contains **1,344 records for 1–7 November 2026**; the implemented quality checks passed.

### 2. Preparing the data

`scripts/data_preparation.ipynb` converts API JSON into a Pandas DataFrame, prepares timestamps and delivery dates, and exports Parquet for efficient downstream use. Original price precision is preserved.

### 3. Storing data in Amazon S3

`scripts/aws_s3_integration.ipynb` uses Boto3 to upload the original JSON and prepared Parquet files to separate paths:

```text
s3://nordic-energy-data-pipeline-yh2026/
├── raw/dayaheadprices/ingestion_date=YYYY-MM-DD/prices.json
└── processed/dayaheadprices/ingestion_date=YYYY-MM-DD/day_ahead_prices.parquet
```

### 4. Automating the daily pipeline

`scripts/energy_pipeline.py` calculates tomorrow's delivery date in the Copenhagen timezone, requests DK1/DK2 prices, validates completeness, creates JSON and Parquet output, and optionally uploads to S3. It accounts for daylight saving changes: normally **96** quarter-hour observations per area, or **92/100** on clock-change days. Upload safeguards avoid overwrites and support safe retries.

The automated script uses **delivery-date** prefixes rather than the notebook's ingestion-date prefixes:

```text
raw/dayaheadprices/delivery_date=YYYY-MM-DD/prices.json
processed/dayaheadprices/delivery_date=YYYY-MM-DD/day_ahead_prices.parquet
```

### 5. AWS Lambda

The Python ingestion pipeline was **deployed to AWS Lambda and successfully tested on 14 November 2026**. Lambda uses an IAM execution role rather than embedded AWS credentials. Daily EventBridge scheduling and CloudWatch monitoring have not yet been verified in this documentation.

## 🧪 Testing and Data Quality

Run the automated tests:

```bash
python -B -m unittest discover -s tests -v
```

Run locally without uploading to AWS:

```bash
scratch="$(mktemp -d)"
python -B scripts/energy_pipeline.py --local-output "$scratch/output"
```

Test against a saved, complete single-day API response:

```bash
python -B scripts/energy_pipeline.py \
  --input-json /path/to/single-day-response.json \
  --delivery-date YYYY-MM-DD \
  --local-output "$scratch/output"
```

## 📁 Project Structure

```text
├── scripts/
│   ├── api_data_extraction.ipynb
│   ├── data_preparation.ipynb
│   ├── aws_s3_integration.ipynb
│   └── energy_pipeline.py
├── tests/
├── json_data_file/
├── data/processed/
├── docs/AWS_SETUP.md
├── PROJECT_ARCHITECTURE.png
├── requirements.txt
└── README.md
```

## 🚀 Getting Started

```bash
git clone https://github.com/Yassdata/Nordic-energy-data-pipeline.git
cd Nordic-energy-data-pipeline
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

AWS uploads require `--upload`, `ENERGY_S3_BUCKET`, and valid AWS authentication. Local development can use `AWS_PROFILE`; Lambda uses its execution role. See [AWS Setup](docs/AWS_SETUP.md).

## 📊 What's Next?

- Verify and document scheduling and monitoring.
- Connect S3 data to Databricks and build Bronze, Silver and Gold Delta Lake tables with PySpark.
- Use SQL to compare DK1/DK2 prices, identify trends and cheaper periods.
- Build a Streamlit app for interactive exploration and potential spot-price savings estimates, with appropriate caveats about tariffs and electricity contracts.

## 🌍 Future Possibilities

Expand beyond Denmark to compare electricity prices across other Nordic countries.

## 📚 Data Source

[Energinet — Energi Data Service](https://www.energidataservice.dk/), `DayAheadPrices` for DK1 and DK2.
