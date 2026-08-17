def track_source_visit(conn, source: str, visitor_id: str, path: str, user_agent: str | None) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into source_visits (source, visitor_id, visit_bucket, path, user_agent)
            values (%s, %s, to_timestamp(floor(extract(epoch from now()) / 600) * 600), %s, %s)
            on conflict (source, visitor_id, visit_bucket) do nothing
            returning id
            """,
            (source, visitor_id, path, user_agent),
        )
        return cur.fetchone() is not None
