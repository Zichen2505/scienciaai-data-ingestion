from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.config.settings import load_settings
from sciencia_ingestion.storage.sqlite_store import connect_sqlite, rollback_run

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    s = load_settings()
    con = connect_sqlite(s.db_path)
    rollback_run(con, args.run_id)
    print(f"rolled_back_run={args.run_id}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
