# Swedish Electricity Price Analytics Platform

## Overview

This project is an automated data engineering and analytics platform for Swedish electricity prices.

It continuously:
- collects electricity market data
- stores data in Snowflake
- provides interactive Streamlit dashboards
- sends automated Telegram price recommendations
- supports machine learning experimentation for forecasting

The platform focuses on Swedish electricity zones SE1-SE4, with analytics primarily centered on Stockholm prices (SE3).

---

# Architecture Workflow

![Workflow Diagram](images/workflow.png)

---

# Business Problem

Electricity prices fluctuate heavily throughout the day due to:
- demand variability
- renewable generation
- weather conditions
- transmission constraints

Consumers and energy analysts benefit from:
- automated electricity monitoring
- historical analytics
- forecast tracking
- cheap vs expensive usage recommendations

This platform automates the complete pipeline from ingestion to user-facing insights.

---

# Features

## Automated ETL Pipeline
- Fetches Swedish electricity prices automatically
- Supports:
  - historical actual prices
  - next-day forecasts
- Handles timezone normalization
- Includes automated historical backfill

---

## Snowflake Cloud Warehouse
Stores:
- actual electricity prices
- forecast prices
- ML feature datasets
- benchmarking datasets

Includes:
- deduplication logic
- overwrite handling
- scalable cloud storage

---

## Interactive Streamlit Dashboard
Provides:
- electricity price visualization
- SE1-SE4 comparisons
- highlighted cheap/expensive regions
- interactive time-series analytics

---

## Telegram Daily Alerts
Every day the pipeline automatically sends:
- cheapest electricity hours
- most expensive electricity hours
- minimum daily price
- maximum daily price
- average daily price

---

## Machine Learning Experiments

Prototype forecasting models were developed inside Snowflake notebooks using:
- XGBoost regression
- lag features
- rolling averages
- volatility indicators
- temporal features

Experiments include:
- chronological train/test splitting
- benchmarking against market forecasts
- feature engineering workflows
- model evaluation

Current benchmark performance:
- MAE: 0.0608
- RMSE: 0.0954
- R²: 0.9587

ML models are currently experimental and not yet integrated into the production dashboard pipeline.

---

# Tech Stack

## Data Engineering
- Python
- Pandas
- GitHub Actions

## Cloud Data Warehouse
- Snowflake

## Visualization
- Streamlit
- Plotly

## Machine Learning
- XGBoost
- Scikit-learn

## Notifications
- Telegram Bot API

---

# Database Tables

| Table | Description |
|---|---|
| `electricity_prices` | Historical electricity prices |
| `electricity_price_forecast` | Forecast electricity prices |
| `ml_features` | Engineered ML features |
| `model_comparison` | ML benchmarking dataset |

---

# Data Quality

Automated validation includes:
- duplicate handling
- timezone normalization
- API response validation
- null value handling
- overwrite protection
- forecast deduplication

---

# Automation

The full pipeline runs automatically every day using GitHub Actions.

Daily workflow:
1. Fetch latest prices
2. Update Snowflake tables
3. Fetch next-day forecasts
4. Compute cheap/expensive hours
5. Send Telegram notification

---

# Repository Structure

```text
.
├── images/
│   └── workflow.png
│
├── fetch_prices.py
├── streamlit_app.py
├── requirements.txt
├── README.md
│
└── .github/
    └── workflows/
        └── electricity_pipeline.yml
```

---

# Setup Instructions

## Clone Repository

```bash
git clone <your_repo_url>
cd <repo_name>
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Snowflake Secrets

Add GitHub repository secrets:

- SNOWFLAKE_USER
- SNOWFLAKE_PASSWORD
- SNOWFLAKE_ACCOUNT
- SNOWFLAKE_WAREHOUSE
- SNOWFLAKE_DATABASE
- SNOWFLAKE_SCHEMA

---

## Configure Telegram Secrets

Add:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

---

## Run Locally

```bash
python fetch_prices.py
```

---

## Launch Dashboard

```bash
streamlit run streamlit_app.py
```

---

# Future Improvements

Potential next steps:
- weather feature integration
- advanced time-series forecasting
- anomaly detection
---
