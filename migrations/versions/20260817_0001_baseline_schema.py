"""Baseline schema shared by backend and workers.

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260817_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS network_versions (
            id bigserial PRIMARY KEY,
            period_date date NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now(),
            source text,
            is_active boolean NOT NULL DEFAULT true
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS network_nodes (
            id text NOT NULL,
            version_id bigint NOT NULL REFERENCES network_versions(id) ON DELETE CASCADE,
            type text NOT NULL CHECK (type IN ('company', 'investor')),
            label text NOT NULL,
            data jsonb NOT NULL DEFAULT '{}',
            degree integer NOT NULL DEFAULT 0,
            in_degree integer NOT NULL DEFAULT 0,
            out_degree integer NOT NULL DEFAULT 0,
            pagerank numeric NOT NULL DEFAULT 0,
            x numeric NOT NULL DEFAULT 0,
            y numeric NOT NULL DEFAULT 0,
            PRIMARY KEY (version_id, id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS network_edges (
            id text NOT NULL,
            version_id bigint NOT NULL REFERENCES network_versions(id) ON DELETE CASCADE,
            source text NOT NULL,
            target text NOT NULL,
            type text NOT NULL DEFAULT 'owns',
            label text,
            percentage numeric NOT NULL,
            total_shares bigint NOT NULL,
            data jsonb NOT NULL DEFAULT '{}',
            PRIMARY KEY (version_id, id),
            FOREIGN KEY (version_id, source) REFERENCES network_nodes(version_id, id) ON DELETE CASCADE,
            FOREIGN KEY (version_id, target) REFERENCES network_nodes(version_id, id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_visits (
            id bigserial PRIMARY KEY,
            source text NOT NULL,
            visitor_id text NOT NULL,
            visit_bucket timestamptz NOT NULL,
            path text NOT NULL,
            user_agent text,
            first_seen_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_sources (
            id bigserial PRIMARY KEY,
            name text NOT NULL,
            base_url text NOT NULL,
            feed_url text NOT NULL UNIQUE,
            is_active boolean NOT NULL DEFAULT true,
            crawl_delay_seconds integer NOT NULL DEFAULT 600,
            last_fetched_at timestamptz,
            last_status_code integer,
            last_error text,
            etag text,
            last_modified text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_articles (
            id bigserial PRIMARY KEY,
            source_id bigint NOT NULL REFERENCES news_sources(id),
            url text NOT NULL UNIQUE,
            title text NOT NULL,
            summary text,
            published_at timestamptz,
            content_hash text NOT NULL,
            raw_payload jsonb NOT NULL DEFAULT '{}',
            scraped_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_fetch_logs (
            id bigserial PRIMARY KEY,
            source_id bigint REFERENCES news_sources(id),
            url text NOT NULL,
            status_code integer,
            duration_ms integer,
            error text,
            fetched_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS article_impact_analysis (
            id bigserial PRIMARY KEY,
            article_id bigint NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
            affected_tickers text[],
            relevance text NOT NULL CHECK (relevance IN ('relevant', 'not_relevant')),
            confidence numeric NOT NULL DEFAULT 0,
            reasoning text,
            model_name text NOT NULL,
            raw_response jsonb NOT NULL DEFAULT '{}',
            analyzed_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (article_id, model_name)
        )
        """,
        "CREATE INDEX IF NOT EXISTS network_nodes_version_type_idx ON network_nodes (version_id, type)",
        "CREATE INDEX IF NOT EXISTS network_nodes_label_idx ON network_nodes USING gin (to_tsvector('simple', label))",
        "CREATE INDEX IF NOT EXISTS network_edges_version_source_idx ON network_edges (version_id, source)",
        "CREATE INDEX IF NOT EXISTS network_edges_version_target_idx ON network_edges (version_id, target)",
        "CREATE INDEX IF NOT EXISTS network_edges_version_percentage_idx ON network_edges (version_id, percentage DESC)",
        "ALTER TABLE source_visits ADD COLUMN IF NOT EXISTS visit_bucket timestamptz",
        "UPDATE source_visits SET visit_bucket = date_trunc('minute', first_seen_at) WHERE visit_bucket IS NULL",
        "ALTER TABLE source_visits ALTER COLUMN visit_bucket SET NOT NULL",
        "ALTER TABLE source_visits DROP CONSTRAINT IF EXISTS source_visits_source_visitor_id_key",
        "CREATE INDEX IF NOT EXISTS source_visits_source_idx ON source_visits (source)",
        "CREATE INDEX IF NOT EXISTS source_visits_first_seen_idx ON source_visits (first_seen_at DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS source_visits_source_visitor_bucket_idx ON source_visits (source, visitor_id, visit_bucket)",
        "CREATE INDEX IF NOT EXISTS news_articles_published_idx ON news_articles (published_at DESC)",
        "CREATE INDEX IF NOT EXISTS news_articles_source_idx ON news_articles (source_id)",
        "CREATE INDEX IF NOT EXISTS article_impact_analysis_article_idx ON article_impact_analysis (article_id)",
        "CREATE INDEX IF NOT EXISTS article_impact_analysis_tickers_idx ON article_impact_analysis USING gin (affected_tickers)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "article_impact_analysis",
        "news_fetch_logs",
        "news_articles",
        "news_sources",
        "source_visits",
        "network_edges",
        "network_nodes",
        "network_versions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
