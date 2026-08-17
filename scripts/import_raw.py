import argparse
import csv
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
from dotenv import load_dotenv

EXCEL_DATE_BASE = date(1899, 12, 30)

COLUMNS = [
    "date",
    "share_code",
    "issuer_name",
    "investor_name",
    "investor_classification",
    "local_foreign",
    "nationality",
    "domicile",
    "holdings_scripless",
    "holdings_scrip",
    "total_holding_shares",
    "percentage",
]


def excel_serial_to_date(value: str) -> date:
    return EXCEL_DATE_BASE + timedelta(days=int(float(value)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import processed IDX CSV into the raw table.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/sheet_1.csv"),
        help="Processed CSV input path",
    )
    args = parser.parse_args()

    load_dotenv(".env")

    rows = []
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            values = [None if value == "" else value for value in row[: len(COLUMNS)]]
            if values[0] is not None:
                values[0] = excel_serial_to_date(values[0])
            rows.append(values)

    placeholders = ", ".join(["%s"] * len(COLUMNS))
    insert_sql = f"insert into raw ({', '.join(COLUMNS)}) values ({placeholders})"

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate table raw")
            cur.executemany(insert_sql, rows)
            cur.execute(
                """
                select
                    count(*) as rows,
                    count(distinct share_code) as share_codes,
                    min(share_code) as first_code,
                    max(share_code) as last_code
                from raw
                """
            )
            print(cur.fetchone())


if __name__ == "__main__":
    main()
