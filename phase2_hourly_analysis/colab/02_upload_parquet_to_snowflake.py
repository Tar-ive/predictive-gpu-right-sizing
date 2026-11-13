# Upload one Parquet file (or a folder of Parquet files) from Google Drive into a new Snowflake table.
# The table's columns and types are read from the file automatically.
#
# In Colab, first run:
#   !pip install snowflake-connector-python

import os
import glob
import getpass
import logging
from google.colab import drive
import snowflake.connector

logging.getLogger("snowflake.connector").setLevel(logging.ERROR)
drive.mount("/content/drive")

# ---------------- settings ----------------
PARQUET_PATH = "/content/drive/MyDrive/PATH/TO/D1_RIGHTSIZING.parquet"   # a file, or a folder of .parquet files
TABLE_NAME = "D1_RIGHTSIZING"

SF = dict(
    account="YOUR_ACCOUNT_IDENTIFIER",
    user="YOUR_USERNAME",
    password=getpass.getpass("Snowflake password: "),
    warehouse="ASI_WH",
    database="ASI_TRACE",
    schema="RAW",
    role="ACCOUNTADMIN",
)
# ------------------------------------------

files = sorted(glob.glob(os.path.join(PARQUET_PATH, "**", "*.parquet"), recursive=True)) \
    if os.path.isdir(PARQUET_PATH) else [PARQUET_PATH]
if not files or not os.path.exists(files[0]):
    raise SystemExit(f"No Parquet files found at {PARQUET_PATH}")
print(f"{len(files)} file(s), {sum(os.path.getsize(f) for f in files) / 1e6:.1f} MB")

stage_dir = f"@ASI_STAGE/project/{TABLE_NAME}"
conn = snowflake.connector.connect(**SF)
cur = conn.cursor()
try:
    cur.execute("CREATE FILE FORMAT IF NOT EXISTS PARQUET_FMT TYPE = PARQUET")
    cur.execute(f"REMOVE {stage_dir}/")   # clear any earlier upload of this table
    for f in files:
        cur.execute(f"PUT 'file://{f}' '{stage_dir}/' AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        print("uploaded", os.path.basename(f))

    # create the table with columns read from the Parquet file, then load it
    cur.execute(f"""
        CREATE OR REPLACE TABLE {TABLE_NAME} USING TEMPLATE (
          SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
          FROM TABLE(INFER_SCHEMA(LOCATION => '{stage_dir}/', FILE_FORMAT => 'PARQUET_FMT',
                                  IGNORE_CASE => TRUE))   -- upper-case column names, so queries need no quotes
        )""")
    cur.execute(f"""
        COPY INTO {TABLE_NAME} FROM {stage_dir}/
        FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FMT')
        MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
        PATTERN = '.*[.]parquet'""")

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    print(f"\n{TABLE_NAME}: {cur.fetchone()[0]:,} rows loaded")
    cur.execute(f"DESCRIBE TABLE {TABLE_NAME}")
    print("columns:", [row[0] for row in cur.fetchall()])
finally:
    cur.close()
    conn.close()
