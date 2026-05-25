import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import snowflake.connector

from snowflake.connector.pandas_tools import write_pandas

# ===================================
# SETTINGS
# ===================================

zones = ["SE1", "SE2", "SE3", "SE4"]

# ===================================
# BACKFILL MODE
# ===================================

BACKFILL_MODE = False

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

    progress = (
        current_date - start_date
    ).days + 1

    print(
        f"Fetching actual prices for "
        f"{current_date} "
        f"({progress}/{days_back + 1})"
    )

    daily_data = {}

    for zone in zones:

        url = (
            f"https://www.elprisetjustnu.se/api/v1/prices/"
            f"{current_date.strftime('%Y/%m-%d')}_{zone}.json"
        )

        try:

            response = requests.get(
                url,
                timeout=20
            )

            if response.status_code != 200:

                print(
                    f"Failed for {zone} "
                    f"on {current_date}"
                )

                continue

            data = response.json()

            for hour_entry in data:

                timestamp = hour_entry["time_start"]

                price = hour_entry["SEK_per_kWh"]

                if timestamp not in daily_data:

                    daily_data[timestamp] = {}

                daily_data[timestamp][zone] = price

        except Exception as e:

            print(
                f"Error for {zone} "
                f"on {current_date}: {e}"
            )

    # -----------------------------------
    # CONVERT TO ROWS
    # -----------------------------------

    for timestamp, zone_prices in daily_data.items():

        row = {

            "datetime": timestamp,

            "SE1": zone_prices.get("SE1"),

            "SE2": zone_prices.get("SE2"),

            "SE3": zone_prices.get("SE3"),

            "SE4": zone_prices.get("SE4")

        }

        all_data.append(row)

    current_date += timedelta(days=1)

    time.sleep(0.1)

# ===================================
# CREATE ACTUAL DATAFRAME
# ===================================

df = pd.DataFrame(all_data)

if df.empty:

    print("No actual data fetched.")

    exit()

# -----------------------------------
# HANDLE TIMEZONES
# -----------------------------------

df["datetime"] = pd.to_datetime(

    df["datetime"],

    utc=True

)

df["datetime"] = (

    df["datetime"]

    .dt.tz_convert(None)

)

# Sort
df = df.sort_values("datetime")

# Remove duplicates
df = df.drop_duplicates(
    subset=["datetime"]
)

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

        schema=os.environ["SNOWFLAKE_SCHEMA"]

    )

    print(
        "Snowflake connection successful!"
    )

except Exception as e:

    print(
        "Snowflake connection failed:"
    )

    print(e)

    raise

cur = conn.cursor()

# ===================================
# DELETE EXISTING ACTUAL ROWS
# ===================================

min_dt = (

    df["datetime"]

    .min()

    .strftime("%Y-%m-%d %H:%M:%S")

)

max_dt = (

    df["datetime"]

    .max()

    .strftime("%Y-%m-%d %H:%M:%S")

)

print(

    f"\nDeleting existing rows "

    f"between {min_dt} and {max_dt}"

)

delete_sql = """
DELETE FROM electricity_prices
WHERE datetime BETWEEN %s AND %s
"""

cur.execute(
    delete_sql,
    (min_dt, max_dt)
)

# ===================================
# BULK INSERT ACTUAL PRICES
# ===================================

print("\nBulk inserting actual prices...")

df["datetime"] = (

    df["datetime"]

    .dt.strftime("%Y-%m-%d %H:%M:%S")

)

df.columns = [

    "DATETIME",

    "SE1",

    "SE2",

    "SE3",

    "SE4"

]

success, nchunks, nrows, _ = write_pandas(

    conn,

    df,

    table_name="ELECTRICITY_PRICES",

    auto_create_table=False

)

print(f"\nInserted {nrows} actual rows.")

# ===================================
# FORECAST SECTION
# ===================================

print(
    "\nFetching tomorrow forecast prices..."
)

tomorrow_date = (

    datetime.today().date()

    + timedelta(days=1)

)

forecast_data = {}

for zone in zones:

    url = (
        f"https://www.elprisetjustnu.se/api/v1/prices/"
        f"{tomorrow_date.strftime('%Y/%m-%d')}_{zone}.json"
    )

    try:

        response = requests.get(
            url,
            timeout=20
        )

        if response.status_code != 200:

            print(
                f"No forecast available "
                f"for {zone}"
            )

            continue

        data = response.json()

        for hour_entry in data:

            timestamp = hour_entry["time_start"]

            price = hour_entry["SEK_per_kWh"]

            if timestamp not in forecast_data:

                forecast_data[timestamp] = {}

            forecast_data[timestamp][zone] = price

    except Exception as e:

        print(
            f"Forecast error "
            f"for {zone}: {e}"
        )

# ===================================
# FORECAST DATAFRAME
# ===================================

forecast_rows = []

for timestamp, zone_prices in forecast_data.items():

    row = {

        "target_datetime": timestamp,

        "SE1": zone_prices.get("SE1"),

        "SE2": zone_prices.get("SE2"),

        "SE3": zone_prices.get("SE3"),

        "SE4": zone_prices.get("SE4")

    }

    forecast_rows.append(row)

forecast_df = pd.DataFrame(forecast_rows)

if not forecast_df.empty:

    # -----------------------------------
    # HANDLE TIMEZONES
    # -----------------------------------

    forecast_df["target_datetime"] = (

        pd.to_datetime(

            forecast_df["target_datetime"],

            utc=True

        )

    )

    forecast_df["target_datetime"] = (

        forecast_df["target_datetime"]

        .dt.tz_convert(None)

    )

    forecast_df = (

        forecast_df

        .sort_values("target_datetime")

    )

    print("\nForecast preview:")

    print(forecast_df.head())

    # -----------------------------------
    # FORMAT DATETIME
    # -----------------------------------

    forecast_df["target_datetime"] = (

        forecast_df["target_datetime"]

        .dt.strftime("%Y-%m-%d %H:%M:%S")

    )

    forecast_df.columns = [

        "TARGET_DATETIME",

        "SE1",

        "SE2",

        "SE3",

        "SE4"

    ]

    # ===================================
    # BULK INSERT FORECASTS
    # ===================================

    print(
        "\nBulk inserting forecasts..."
    )

    success, nchunks, nrows, _ = (

        write_pandas(

            conn,

            forecast_df,

            table_name="ELECTRICITY_PRICE_FORECAST",

            auto_create_table=False

        )

    )

    print(
        f"\nInserted {nrows} "
        f"forecast rows."
    )

else:

    print(
        "\nNo forecast prices available yet."
    )

# ===================================
# TELEGRAM DAILY REPORT
# ===================================

telegram_query = """
SELECT
    target_datetime,
    se3
FROM electricity_price_forecast
WHERE target_datetime >= CURRENT_DATE + 1
  AND target_datetime < CURRENT_DATE + 2
ORDER BY target_datetime
"""

telegram_df = pd.read_sql(
    telegram_query,
    conn
)

# -----------------------------------
# REMOVE DUPLICATES
# -----------------------------------

telegram_df = telegram_df.drop_duplicates(
    subset=["TARGET_DATETIME"]
)

telegram_df = telegram_df.sort_values(
    "TARGET_DATETIME"
)

telegram_df = telegram_df.reset_index(
    drop=True
)

if not telegram_df.empty:

    # -----------------------------------
    # FORMAT DATETIME
    # -----------------------------------

    telegram_df["TARGET_DATETIME"] = (

        pd.to_datetime(
            telegram_df["TARGET_DATETIME"]
        )

    )

    # -----------------------------------
    # PRICE STATISTICS
    # -----------------------------------

    prices = telegram_df["SE3"]

    low_threshold = prices.quantile(0.25)

    high_threshold = prices.quantile(0.75)

    lowest_price = prices.min()

    highest_price = prices.max()

    average_price = prices.mean()

    # -----------------------------------
    # CHEAPEST HOURS
    # -----------------------------------

    cheap_hours = telegram_df[
        telegram_df["SE3"] <= low_threshold
    ]["TARGET_DATETIME"]

    # -----------------------------------
    # MOST EXPENSIVE HOURS
    # -----------------------------------

    expensive_hours = telegram_df[
        telegram_df["SE3"] >= high_threshold
    ]["TARGET_DATETIME"]

    # -----------------------------------
    # KEEP ONLY ROUND HOURS
    # -----------------------------------

    cheap_hours = cheap_hours[
        cheap_hours.dt.minute == 0
    ]

    expensive_hours = expensive_hours[
        expensive_hours.dt.minute == 0
    ]

    # -----------------------------------
    # FORMAT HOURS
    # -----------------------------------

    cheap_text = ", ".join(

        cheap_hours.dt.strftime("%H:%M")

    )

    expensive_text = ", ".join(

        expensive_hours.dt.strftime("%H:%M")

    )

    # -----------------------------------
    # TELEGRAM MESSAGE
    # -----------------------------------

    message = f"""
Daily Electricity Report

CHEAPEST HOURS
{cheap_text}

MOST EXPENSIVE HOURS
{expensive_text}

Lowest price: {lowest_price:.2f} SEK/kWh
Highest price: {highest_price:.2f} SEK/kWh
Average price: {average_price:.2f} SEK/kWh
"""

    # -----------------------------------
    # SEND TELEGRAM MESSAGE
    # -----------------------------------

    bot_token = os.environ[
        "TELEGRAM_BOT_TOKEN"
    ]

    chat_id = os.environ[
        "TELEGRAM_CHAT_ID"
    ]

    url = (
        f"https://api.telegram.org/"
        f"bot{bot_token}/sendMessage"
    )

    payload = {

        "chat_id": chat_id,

        "text": message

    }

    response = requests.post(
        url,
        data=payload
    )

    print(
        "\nTelegram report sent!"
    )

else:

    print(
        "\nNo forecast data available "
        "for Telegram report."
    )

# ===================================
# CLEANUP
# ===================================

cur.close()

conn.close()

print("\nDone.")
