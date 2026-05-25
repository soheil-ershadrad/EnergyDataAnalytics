import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import snowflake.connector

# -----------------------------------
# SETTINGS
# -----------------------------------

zones = ["SE1", "SE2", "SE3", "SE4"]

# Fetch only recent days
# (safer if GitHub Actions misses a run)
days_back = 3

end_date = datetime.today().date()
start_date = end_date - timedelta(days=days_back)

all_data = []

# -----------------------------------
# FETCH DATA
# -----------------------------------

current_date = start_date

while current_date <= end_date:

    print(f"Fetching {current_date}")

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

    # Convert to rows
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

# -----------------------------------
# CREATE DATAFRAME
# -----------------------------------

df = pd.DataFrame(all_data)

if df.empty:
    print("No data fetched.")
    exit()

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime")

df = df.drop_duplicates(subset=["datetime"])

df = df.reset_index(drop=True)

print("\nPreview:")
print(df.head())

# -----------------------------------
# CONNECT TO SNOWFLAKE
# -----------------------------------

print("\nConnecting to Snowflake...")

conn = snowflake.connector.connect(
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"]
)

cur = conn.cursor()

# -----------------------------------
# DELETE EXISTING ROWS
# (prevents duplicates)
# -----------------------------------

min_dt = df["datetime"].min()
max_dt = df["datetime"].max()

print(f"\nDeleting existing rows between {min_dt} and {max_dt}")

delete_sql = """
DELETE FROM electricity_prices
WHERE datetime BETWEEN %s AND %s
"""

cur.execute(delete_sql, (min_dt, max_dt))

# -----------------------------------
# INSERT NEW DATA
# -----------------------------------

print("\nInserting new rows...")

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
            row["datetime"],
            row["SE1"],
            row["SE2"],
            row["SE3"],
            row["SE4"],
        )
    )

    rows_inserted += 1

conn.commit()

print(f"\nInserted {rows_inserted} rows.")

# -----------------------------------
# CLEANUP
# -----------------------------------

cur.close()
conn.close()

print("\nDone.")
