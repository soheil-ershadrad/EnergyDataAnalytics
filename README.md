# Swedish Electricity Price Database and Analytics via Snowflake

## Business Problem
Energy companies need reliable, timely data on electricity 
price patterns to optimize operations and costs. 
This pipeline automates the collection, transformation, 
and analysis of Swedish electricity market data.

## Architecture
[paste your architecture diagram here]

Bronze (Raw) → Silver (Cleaned) → Gold (Analytics)
AWS S3 → Snowflake

## Key Insights Delivered
- Peak vs off-peak price differentials by season
- Daily price volatility trends
- Monthly and seasonal price patterns for SE3 region

## Tech Stack
- Python (ingestion & orchestration)
- AWS S3 (raw data storage)
- Snowflake (data warehouse)
- Medallion Architecture (Bronze/Silver/Gold)

## Data Quality
Automated checks on every pipeline run covering
null values, negative prices, and record completeness.

## How to Run
[setup instructions]

