import os
import socket
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(".env")
    database_url = os.environ["DATABASE_URL"]
    parsed = urlparse(database_url)

    print(f"host: {parsed.hostname}")
    print(f"port: {parsed.port}")
    socket.getaddrinfo(parsed.hostname, parsed.port)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user, version()")
            database, user, version = cur.fetchone()
            print("CONNECTED")
            print(f"database: {database}")
            print(f"user: {user}")
            print(f"postgres: {version.split(',')[0]}")

            cur.execute(
                """
                select table_schema, table_name
                from information_schema.tables
                where table_type = 'BASE TABLE'
                  and table_schema not in ('pg_catalog', 'information_schema')
                order by table_schema, table_name
                """
            )
            tables = cur.fetchall()
            print(f"tables: {len(tables)}")

            for schema, table in tables:
                print(f"\n{schema}.{table}")
                cur.execute(
                    """
                    select column_name, data_type, is_nullable, column_default
                    from information_schema.columns
                    where table_schema = %s and table_name = %s
                    order by ordinal_position
                    """,
                    (schema, table),
                )
                for column, data_type, nullable, default in cur.fetchall():
                    default_text = f" default={default}" if default else ""
                    print(f"  - {column}: {data_type} nullable={nullable}{default_text}")



if __name__ == "__main__":
    main()
