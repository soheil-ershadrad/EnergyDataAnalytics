import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import snowflake.connector

# ===================================
# SETTINGS
# ===================================

zones = ["SE1", "SE2", "SE3", "SE4"]

# ===================================
# BACKFILL MODE
# ===================================

# Set to True ONLY ONCE
# to load historical data

BACKFILL_MODE = True

if BACKFILL_MODE:
    days_back = 365
else:
    days_back = 3

# ===================================
# DATE RANGE
# ===================================

end_date = datetime.today().date()
start_date = end_date - timedelta(days=days_back)

all_data = []

# ===================================
# FETCH ACTUAL PRICES
# ===================================

current_date = start_date

while current_date <= end_date:

    print(f"Fetching actual prices for {current_date}")

    daily_data = {}

    for zone in zones:

        url = (
            f"https://www.elprisetjustnu.se/api/v1/prices/"
            f"{current_date.strftime('%Y/%m-%d')}_{zone}.json"
        )

        try:

            response = requests.get(url, timeout=20)

            if response.status_code != 200:
                print(f"Failed for {zone} on {current_date}")
                continue

            data = response.json()

            for hour_entry in data:

                timestamp = hour_entry["time_start"]
                price = hour_entry["SEK_per_kWh"]

                if timestamp not in daily_data:
                    daily_data[timestamp] = {}

                daily_data[timestamp][zone] = price

        except Exception as e:

            print(f"Error for {zone} on {current_date}: {e}")

    # -----------------------------------
    # CONVERT TO ROWS
    # -----------------------------------

    for timestamp, zone_prices in daily_data.items():

        row = {
            "datetime": timestamp,
            "SE1": zone_prices.get("SE1"),
            "SE2": zone_prices.get("SE2"),
            "SE3": zone_prices.get("SE3"),
            "SE4": zone_prices.get("SE4"),
        }

        all_data.append(row)

    current_date += timedelta(days=1)

    # Avoid hammering API
    time.sleep(0.1)

# ===================================
# CREATE ACTUAL DATAFRAME
# ===================================

df = pd.DataFrame(all_data)

if df.empty:
    print("No actual data fetched.")
    exit()

# -----------------------------------
# HANDLE TIMEZONES SAFELY
# -----------------------------------

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True
)

# Remove timezone for Snowflake
df["datetime"] = df["datetime"].dt.tz_convert(None)

# Sort
df = df.sort_values("datetime")

# Remove duplicates
df = df.drop_duplicates(subset=["datetime"])

# Reset index
df = df.reset_index(drop=True)

print("\nActual prices preview:")
print(df.head())

# ===================================
# CONNECT TO SNOWFLAKE
# ===================================

print("\nConnecting to Snowflake...")

try:

    conn = snowflake.connector.connect(
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )

    print("Snowflake connection successful!")

except Exception as e:

    print("Snowflake connection failed:")
    print(e)

    raise

cur = conn.cursor()

# ===================================
# DELETE EXISTING ACTUAL ROWS
# ===================================

min_dt = df["datetime"].min().strftime("%Y-%m-%d %H:%M:%S")
max_dt = df["datetime"].max().strftime("%Y-%m-%d %H:%M:%S")

print(f"\nDeleting existing actual rows between {min_dt} and {max_dt}")

delete_sql = """
DELETE FROM electricity_prices
WHERE datetime BETWEEN %s AND %s
"""

cur.execute(delete_sql, (min_dt, max_dt))

# ===================================
# INSERT ACTUAL PRICES
# ===================================

print("\nInserting actual prices...")

insert_sql = """
INSERT INTO electricity_prices (
    datetime,
    se1,
    se2,
    se3,
    se4
)
VALUES (%s, %s, %s, %s, %s)
"""

rows_inserted = 0

for _, row in df.iterrows():

    cur.execute(
        insert_sql,
        (
            row["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
            row["SE1"],
            row["SE2"],
            row["SE3"],
            row["SE4"],
        )
    )

    rows_inserted += 1

conn.commit()

print(f"\nInserted {rows_inserted} actual rows.")

# ===================================
# FORECAST SECTION
# ===================================

print("\nFetching tomorrow forecast prices...")

tomorrow_date = datetime.today().date() + timedelta(days=1)

forecast_data = {}

for zone in zones:

    url = (
        f"https://www.elprisetjustnu.se/api/v1/prices/"
        f"{tomorrow_date.strftime('%Y/%m-%d')}_{zone}.json"
    )

    try:

        response = requests.get(url, timeout=20)

        if response.status_code != 200:
            print(f"No forecast available for {zone}")
            continue

        data = response.json()

        for hour_entry in data:

            timestamp = hour_entry["time_start"]
            price = hour_entry["SEK_per_kWh"]

            if timestamp not in forecast_data:
                forecast_data[timestamp] = {}

            forecast_data[timestamp][zone] = price

    except Exception as e:

        print(f"Forecast error for {zone}: {e}")

# ===================================
# FORECAST DATAFRAME
# ===================================

forecast_rows = []

for timestamp, zone_prices in forecast_data.items():

    row = {
        "datetime": timestamp,
        "SE1": zone_prices.get("SE1"),
        "SE2": zone_prices.get("SE2"),
        "SE3": zone_prices.get("SE3"),
        "SE4": zone_prices.get("SE4"),
    }

    forecast_rows.append(row)

forecast_df = pd.DataFrame(forecast_rows)

if not forecast_df.empty:

    # -----------------------------------
    # HANDLE FORECAST TIMEZONES
    # -----------------------------------

    forecast_df["datetime"] = pd.to_datetime(
        forecast_df["datetime"],
        utc=True
    )

    forecast_df["datetime"] = (
        forecast_df["datetime"]
        .dt.tz_convert(None)
    )

    forecast_df = forecast_df.sort_values("datetime")

    print("\nForecast preview:")
    print(forecast_df.head())

    # ===================================
    # INSERT FORECASTS
    # ===================================

    forecast_insert_sql = """
    INSERT INTO electricity_price_forecast (
        target_datetime,
        se1,
        se2,
        se3,
        se4
    )
    VALUES (%s, %s, %s, %s, %s)
    """

    inserted_forecasts = 0

    for _, row in forecast_df.iterrows():

        cur.execute(
            forecast_insert_sql,
            (
                row["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
                row["SE1"],
                row["SE2"],
                row["SE3"],
                row["SE4"],
            )
        )

        inserted_forecasts += 1

    conn.commit()

    print(f"\nInserted {inserted_forecasts} forecast rows.")

else:

    print("\nNo forecast prices available yet.")

# ===================================
# CLEANUP
# ===================================

cur.close()
conn.close()

print("\nDone.")
