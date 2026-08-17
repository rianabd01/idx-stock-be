from typing import Any

from psycopg import Connection


def latest_articles(conn: Connection, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
                a.id,
                s.name as source_name,
                a.url,
                a.title,
                a.summary,
                a.published_at::text,
                a.scraped_at::text
            from news_articles a
            join news_sources s on s.id = a.source_id
            order by coalesce(a.published_at, a.scraped_at) desc
            limit %s
            """,
            (limit,),
        )
        return list(cur.fetchall())
