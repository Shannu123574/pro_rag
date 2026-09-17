import sys
from app.db import init_db
from app.ingest import ingest_dir
if __name__ == "__main__":
    init_db()
    if len(sys.argv)!=3 or sys.argv[1]!="ingest":
        raise SystemExit("Usage: python -m app.cli ingest /app/data/sample")
    print(ingest_dir(sys.argv[2]))
