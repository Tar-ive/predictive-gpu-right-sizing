-- Load asi_opensource_server_hourly (days 158-184) into SERVER_HOURLY.
-- Run in Snowflake AFTER the Colab loader has uploaded the files
-- (TABLE = "asi_opensource_server_hourly", DAYS = range(158, 185), DRY_RUN = False).

USE WAREHOUSE ASI_WH;
USE SCHEMA ASI_TRACE.RAW;

-- 1. Uploaded files: expect 648 (27 days x 24 hours)
LIST @ASI_STAGE/asi_opensource_server_hourly/;

-- 2. Create the table from the files' own columns, plus the source file name
CREATE OR REPLACE TABLE SERVER_HOURLY USING TEMPLATE (
  SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
  FROM TABLE(INFER_SCHEMA(
    LOCATION => '@ASI_STAGE/asi_opensource_server_hourly/',
    FILE_FORMAT => 'PARQUET_FMT',
    IGNORE_CASE => TRUE))
);
ALTER TABLE SERVER_HOURLY ADD COLUMN SOURCE_FILE STRING;

-- 3. Load
COPY INTO SERVER_HOURLY
FROM @ASI_STAGE/asi_opensource_server_hourly/
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FMT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
INCLUDE_METADATA = (SOURCE_FILE = METADATA$FILENAME)
PATTERN = '.*[.]parquet';

-- 4. Day and hour from the folder names (the same repair as the pod table)
ALTER TABLE SERVER_HOURLY ADD COLUMN DAY_ INT, HOUR_ INT;
UPDATE SERVER_HOURLY SET
  DAY_  = REGEXP_SUBSTR(SOURCE_FILE, 'day=([0-9]+)',  1, 1, 'e', 1)::INT,
  HOUR_ = REGEXP_SUBSTR(SOURCE_FILE, 'hour=([0-9]+)', 1, 1, 'e', 1)::INT;

-- 5. Checks - send these three results
SELECT COUNT(*) AS rows_loaded, COUNT_IF(DAY_ IS NULL) AS missing_day, COUNT_IF(HOUR_ IS NULL) AS missing_hour,
       MIN(DAY_) AS first_day, MAX(DAY_) AS last_day, COUNT(DISTINCT DAY_ * 24 + HOUR_) AS hours
FROM SERVER_HOURLY;

DESCRIBE TABLE SERVER_HOURLY;

SELECT * FROM SERVER_HOURLY LIMIT 5;
