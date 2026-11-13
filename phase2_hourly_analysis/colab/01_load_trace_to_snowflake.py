# Load selected days of the Alibaba ASI GPU trace (cluster-trace-gpu-v2026) into Snowflake.
#
# Runs in Google Colab or on a laptop. It reads only the needed files out of the remote
# zip (using HTTP range requests), uploads them one day at a time to a Snowflake stage,
# then deletes the local copy, so you never need 352 GB of disk.
#
# Before running: run Part A of load_asi_to_snowflake.sql in Snowflake (creates the stage).
#
# In Colab, first run:
#   !pip install remotezip snowflake-connector-python

import os
import re
import shutil
import time
import getpass
import logging
from remotezip import RemoteZip
import snowflake.connector

# ---------------- settings ----------------
BASE_URL = "https://tre-clusterdata.oss-cn-hangzhou.aliyuncs.com/cluster-trace-gpu-v2026/data/"
TABLE = "asi_opensource_pod_hourly"     # later: "asi_opensource_server_hourly" for the simulation
DAYS = range(158, 184)                  # test days 158-183
LOCAL_DIR = "/content/asi_tmp"          # on a laptop, use any folder with ~5 GB free
DRY_RUN = True                          # True = only list files and sizes; set False to load

SF = dict(
    account="YOUR_ACCOUNT_IDENTIFIER",   # format ORGNAME-ACCOUNTNAME, from Snowsight > your name (bottom left) > Account > View account details
    user="YOUR_USERNAME",
    password=getpass.getpass("Snowflake password: "),
    warehouse="ASI_WH",
    database="ASI_TRACE",
    schema="RAW",
    role="ACCOUNTADMIN",                 # or whichever role created the stage
)
STAGE = "@ASI_STAGE"
# ------------------------------------------

DAY_RE = re.compile(r"day=(\d+)/")

# hide the connector's harmless proxy and cloud-detection warnings
logging.getLogger("snowflake.connector").setLevel(logging.ERROR)


def wanted(name):
    m = DAY_RE.search(name)
    return name.endswith(".parquet") and m is not None and int(m.group(1)) in DAYS


def main():
    url = BASE_URL + TABLE + ".zip"
    with RemoteZip(url) as z:
        infos = [i for i in z.infolist() if wanted(i.filename)]
        total_gb = sum(i.file_size for i in infos) / 1e9
        print(f"{len(infos)} files for days {DAYS.start}-{DAYS.stop - 1}, about {total_gb:.1f} GB")
        print("example names:", [i.filename for i in infos[:3]])
        if DRY_RUN:
            return

        conn = snowflake.connector.connect(**SF)
        cur = conn.cursor()
        try:
            # files already in the stage from an earlier run are skipped, so a rerun resumes
            cur.execute(f"LIST {STAGE}/{TABLE}/")
            already = {row[0].split("/", 1)[1] for row in cur.fetchall()}
            print(f"{len(already)} files already in the stage; skipping those")

            for day in DAYS:
                day_files = [i for i in infos
                             if int(DAY_RE.search(i.filename).group(1)) == day
                             and i.filename not in already]
                if not day_files:
                    print(f"day {day}: nothing new to upload")
                    continue
                os.makedirs(LOCAL_DIR, exist_ok=True)
                for n, info in enumerate(day_files, 1):
                    t0 = time.time()
                    local_path = z.extract(info, LOCAL_DIR)
                    # keep the day=/hour= folders in the stage path; the SQL reads day and hour from it
                    stage_dir = os.path.dirname(info.filename)
                    cur.execute(
                        f"PUT 'file://{local_path}' '{STAGE}/{stage_dir}/' "
                        "AUTO_COMPRESS=FALSE OVERWRITE=TRUE PARALLEL=8"
                    )
                    os.remove(local_path)
                    print(f"  day {day} file {n}/{len(day_files)}: "
                          f"{info.file_size / 1e6:.0f} MB in {time.time() - t0:.0f} s", flush=True)
                shutil.rmtree(LOCAL_DIR)   # free disk before the next day
                print(f"day {day}: uploaded {len(day_files)} files")
        finally:
            cur.close()
            conn.close()


if __name__ == "__main__":
    main()
