"""Run one Athena query via the AWS CLI, wait, print stats and (optionally) results.

usage: python athena.py <sql-file> [--rows N] [--csv out.csv]
"""
import json
import subprocess
import sys
import time

BUCKET = "alibaba-cluster-data-migration-445056752928"
OUT = f"s3://{BUCKET}/athena-results/"
DB = "alibaba_trace"


def aws(*args):
    r = subprocess.run(["aws", "--region", "us-east-1", "--output", "json", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr.strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}


def run(sql, rows=50, csv=None):
    qid = aws("athena", "start-query-execution", "--query-string", sql,
              "--query-execution-context", f"Database={DB}",
              "--result-configuration", f"OutputLocation={OUT}",
              "--work-group", "primary")["QueryExecutionId"]
    while True:
        q = aws("athena", "get-query-execution", "--query-execution-id", qid)["QueryExecution"]
        st = q["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(3)
    stats = q.get("Statistics", {})
    scanned = stats.get("DataScannedInBytes", 0)
    print(f"[{st}] {qid} scanned={scanned/2**30:.2f} GiB (~${scanned/1e12*5:.3f}) time={stats.get('TotalExecutionTimeInMillis',0)/1000:.1f}s",
          file=sys.stderr)
    if st != "SUCCEEDED":
        sys.exit(q["Status"].get("StateChangeReason", st))
    if q.get("StatementType") == "DML":
        res = aws("athena", "get-query-results", "--query-execution-id", qid, "--max-items", str(rows + 1))
        data = [[c.get("VarCharValue", "") for c in r["Data"]] for r in res["ResultSet"]["Rows"]]
        if csv:
            subprocess.run(["aws", "--region", "us-east-1", "s3", "cp", "--quiet",
                            q["ResultConfiguration"]["OutputLocation"], csv], check=True)
        w = [max(len(r[i]) for r in data) for i in range(len(data[0]))] if data else []
        for r in data:
            print("  ".join(v.ljust(w[i]) for i, v in enumerate(r)))


if __name__ == "__main__":
    sql = open(sys.argv[1]).read()
    rows = int(sys.argv[sys.argv.index("--rows") + 1]) if "--rows" in sys.argv else 50
    csv = sys.argv[sys.argv.index("--csv") + 1] if "--csv" in sys.argv else None
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        run(stmt, rows, csv)
