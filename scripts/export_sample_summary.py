from __future__ import annotations
import json, sqlite3
from pathlib import Path
from urllib.parse import urlparse

def db_path():
    db_url=[l for l in Path(".env").read_text(encoding="utf-8").splitlines() if l.startswith("DB_URL=")][0].split("=",1)[1].strip()
    p=urlparse(db_url); path=p.path
    if path.startswith("/") and len(path)>=3 and path[2]==":": path=path[1:]
    return path

def main():
    con=sqlite3.connect(db_path())
    cur=con.cursor()

    # counts
    apps=cur.execute("select count(*) from apps").fetchone()[0]
    reviews=cur.execute("select count(*) from reviews").fetchone()[0]
    runs=cur.execute("select count(*) from ingestion_runs").fetchone()[0]

    # basic completeness checks (no content exported)
    null_content=cur.execute("select count(*) from reviews where content is null or length(trim(content))=0").fetchone()[0]
    null_at=cur.execute("select count(*) from reviews where at is null").fetchone()[0]
    rating_dist=cur.execute("select rating, count(*) from reviews group by rating order by rating").fetchall()

    out = {
        "apps_count": apps,
        "reviews_count": reviews,
        "runs_count": runs,
        "null_content": null_content,
        "null_at": null_at,
        "rating_distribution": rating_dist,
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/sample_run_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("WROTE reports/sample_run_summary.json")

if __name__ == "__main__":
    main()
