# Nordic Energy Data Pipeline

A data engineering project focused on collecting and processing Danish electricity market data using Python and SQL.

The project uses [Energi Data Service](https://www.energidataservice.dk/) to retrieve day-ahead electricity prices for the DK1 and DK2 price areas. The goal is to build a pipeline that takes data from an API, validates its quality, and prepares it for storage and analysis.

## Tech Stack

**Currently used:** Python, Pandas, Requests, JSON, Parquet, Git, GitHub

**Planned:** Databricks, Delta Lake, SQL, DuckDB, dbt

## Pipeline Overview

The pipeline currently covers two main stages:

**1. Data Extraction**

The `api_data_extraction.ipynb` notebook retrieves electricity prices from the Energi Data Service API and saves the raw response as JSON.

It also includes data quality checks for:

- Missing values
- Duplicate records using a composite key (`TimeUTC`, `PriceArea`)
- Invalid price areas
- Incorrect price data types
- Invalid timestamps
- Missing 15-minute intervals

**2. Data Preparation**

The `data_preparation.ipynb` notebook reads the JSON data and prepares it for further processing.

This includes converting the records into a Pandas DataFrame, converting timestamps to datetime, creating a delivery date column, and exporting the dataset to Parquet.

## Dataset

The initial dataset covers 1–7 November 2026 and contains 1,344 records for the two Danish electricity price areas.

The main fields are:

| Column | Description |
|---|---|
| TimeUTC | Delivery timestamp in UTC |
| TimeDK | Delivery timestamp in Danish local time |
| PriceArea | Danish electricity price area (DK1 or DK2) |
| DayAheadPriceEUR | Day-ahead electricity price in EUR/MWh |
| DayAheadPriceDKK | Day-ahead electricity price in DKK/MWh |

All implemented data quality checks passed on the initial dataset.

## Project Structure

```text
Nordic Energy Data Pipeline/
├── scripts/
│   ├── api_data_extraction.ipynb
│   └── data_preparation.ipynb
├── json_data_file/
│   └── prices.json
├── data/
│   └── processed/
│       └── day_ahead_prices.parquet
├── requirements.txt
└── README.md
```

The JSON and Parquet datasets are generated locally and excluded from Git.

## Getting Started

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/Yassdata/Nordic-energy-data-pipeline.git
cd Nordic-energy-data-pipeline

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the project in VS Code and select the project's Python environment as the Jupyter kernel.

Run the notebooks in this order:

1. `api_data_extraction.ipynb` — Extract and validate the electricity price data.
2. `data_preparation.ipynb` — Prepare the data and export it to Parquet.

## Next Steps

The next stage is to extend the local pipeline with Databricks and Delta Lake for structured data storage and transformations.

I also plan to use SQL, DuckDB, and dbt to explore electricity price patterns, compare DK1 and DK2, and build a simple analytical layer.

## Data Source

[Energi Data Service — DayAheadPrices](https://www.energidataservice.dk/)