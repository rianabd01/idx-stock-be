import os
import time
from contextlib import contextmanager
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

load_dotenv(".env")

app = FastAPI(title="IDX Stock Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://idx-stock.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

CACHE_TTL_SECONDS = 300
_cache: dict[str, tuple[float, Any]] = {}


def get_cached(cache_key: str):
    cached = _cache.get(cache_key)
    if cached is None:
        return None

    expires_at, value = cached
    if expires_at <= time.monotonic():
        _cache.pop(cache_key, None)
        return None

    return value


def set_cached(cache_key: str, value: Any):
    _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, value)
    return value


def set_cache_headers(response: Response, hit: bool):
    response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL_SECONDS}"
    response.headers["X-Cache"] = "HIT" if hit else "MISS"


class SourceTrackingPayload(BaseModel):
    source: str = Field(min_length=1, max_length=80)
    visitor_id: str = Field(min_length=16, max_length=80)
    path: str = Field(default="/", max_length=300)


def normalize_source(value: str) -> str:
    return "".join(char for char in value.lower().strip() if char.isalnum() or char in "_-.")[:80]


def ensure_analytics_schema(cur):
    cur.execute(
        """
        create table if not exists source_visits (
            id bigserial primary key,
            source text not null,
            visitor_id text not null,
            visit_bucket timestamptz not null,
            path text not null,
            user_agent text,
            first_seen_at timestamptz not null default now()
        )
        """
    )
    cur.execute("alter table source_visits add column if not exists visit_bucket timestamptz")
    cur.execute("update source_visits set visit_bucket = date_trunc('minute', first_seen_at) where visit_bucket is null")
    cur.execute("alter table source_visits alter column visit_bucket set not null")
    cur.execute("alter table source_visits drop constraint if exists source_visits_source_visitor_id_key")
    cur.execute("create index if not exists source_visits_source_idx on source_visits (source)")
    cur.execute("create index if not exists source_visits_first_seen_idx on source_visits (first_seen_at desc)")
    cur.execute("create unique index if not exists source_visits_source_visitor_bucket_idx on source_visits (source, visitor_id, visit_bucket)")


@contextmanager
def get_connection():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        yield conn


def active_version(cur) -> dict[str, Any] | None:
    cur.execute(
        """
        select id, period_date::text, imported_at::text
        from network_versions
        where is_active = true
        order by period_date desc, id desc
        limit 1
        """
    )
    return cur.fetchone()


def to_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "label": row["label"],
        "data": row["data"],
        "metrics": {
            "degree": row["degree"],
            "in_degree": row["in_degree"],
            "out_degree": row["out_degree"],
            "pagerank": float(row["pagerank"]),
        },
        "position": {"x": float(row["x"]), "y": float(row["y"])},
    }


def to_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "target": row["target"],
        "type": row["type"],
        "data": {
            **row["data"],
            "percentage": float(row["percentage"]),
            "total_shares": int(row["total_shares"]),
        },
    }


def graph_response(version: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], summary: dict[str, Any]):
    return {
        "versions": [
            {
                "id": version["id"],
                "period_date": version["period_date"],
                "imported_at": version["imported_at"],
            }
        ],
        "nodes": nodes,
        "edges": edges,
        "summary": summary,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analytics/source")
def track_source(payload: SourceTrackingPayload, request: Request):
    source = normalize_source(payload.source)
    if not source:
        return {"tracked": False, "reason": "empty_source"}

    user_agent = request.headers.get("user-agent")
    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_analytics_schema(cur)
            cur.execute(
                """
                insert into source_visits (source, visitor_id, visit_bucket, path, user_agent)
                values (%s, %s, to_timestamp(floor(extract(epoch from now()) / 600) * 600), %s, %s)
                on conflict (source, visitor_id, visit_bucket) do nothing
                returning id
                """,
                (source, payload.visitor_id, payload.path, user_agent),
            )
            inserted = cur.fetchone() is not None
            return {"tracked": inserted, "source": source}


@app.get("/network-analysis")
def get_network_analysis(
    response: Response,
    mode: str = "overview",
    limit: int = Query(default=1200, ge=1, le=100000),
):
    cache_key = f"network-analysis:{mode}:{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached

    node_limit = 100000 if mode == "full" else limit
    with get_connection() as conn:
        with conn.cursor() as cur:
            version = active_version(cur)
            if version is None:
                return graph_response({}, [], [], {})

            cur.execute(
                """
                select id, type, label, data, degree, in_degree, out_degree, pagerank, x, y
                from network_nodes
                where version_id = %s
                order by pagerank desc, degree desc, label
                limit %s
                """,
                (version["id"], node_limit),
            )
            nodes = [to_node(row) for row in cur.fetchall()]

            cur.execute(
                """
                with selected_nodes as (
                    select id
                    from network_nodes
                    where version_id = %s
                    order by pagerank desc, degree desc, label
                    limit %s
                )
                select e.id, e.source, e.target, e.type, e.percentage, e.total_shares, e.data
                from network_edges e
                join selected_nodes source_node on source_node.id = e.source
                join selected_nodes target_node on target_node.id = e.target
                where e.version_id = %s
                order by e.percentage desc
                """,
                (version["id"], node_limit, version["id"]),
            )
            edges = [to_edge(row) for row in cur.fetchall()]

            cur.execute(
                """
                with node_counts as (
                    select
                        count(*) as node_count,
                        count(*) filter (where type = 'investor') as investor_count,
                        count(*) filter (where type = 'company') as company_count
                    from network_nodes
                    where version_id = %s
                ),
                edge_counts as (
                    select count(*) as edge_count
                    from network_edges
                    where version_id = %s
                )
                select node_count, edge_count, investor_count, company_count,
                    case
                        when node_count <= 1 then 0
                        else edge_count::numeric / (node_count::numeric * (node_count::numeric - 1))
                    end as density
                from node_counts, edge_counts
                """,
                (version["id"], version["id"]),
            )
            summary_row = cur.fetchone()
            summary = {
                "node_count": summary_row["node_count"],
                "edge_count": summary_row["edge_count"],
                "investor_count": summary_row["investor_count"],
                "company_count": summary_row["company_count"],
                "density": float(summary_row["density"]),
            }
            result = graph_response(version, nodes, edges, summary)
            set_cache_headers(response, False)
            return set_cached(cache_key, result)


@app.get("/network-analysis/search")
def search_network_nodes(response: Response, q: str = Query(default="", min_length=0)):
    query = q.strip()
    if not query:
        return []

    cache_key = f"network-analysis:search:{query.lower()}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select n.id, n.type, n.label, n.data, n.degree, n.in_degree, n.out_degree, n.pagerank, n.x, n.y
                from network_nodes n
                join network_versions v on v.id = n.version_id
                where v.is_active = true
                  and (n.id ilike %s or n.label ilike %s or n.data::text ilike %s)
                order by
                  case when n.label ilike %s then 0 else 1 end,
                  n.pagerank desc,
                  n.degree desc,
                  n.label
                limit 12
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%", f"{query}%"),
            )
            result = [to_node(row) for row in cur.fetchall()]
            set_cache_headers(response, False)
            return set_cached(cache_key, result)


@app.get("/network-analysis/nodes/{node_id:path}")
def get_network_node_subgraph(
    node_id: str,
    response: Response,
    depth: int = Query(default=1, ge=1, le=3),
):
    cache_key = f"network-analysis:node:{node_id}:depth:{depth}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached

    with get_connection() as conn:
        with conn.cursor() as cur:
            version = active_version(cur)
            if version is None:
                return graph_response({}, [], [], {})

            cur.execute(
                """
                with recursive visible_nodes(id, depth) as (
                    select %s::text, 0
                    union
                    select
                        case when e.source = visible_nodes.id then e.target else e.source end,
                        visible_nodes.depth + 1
                    from visible_nodes
                    join network_edges e
                      on e.version_id = %s
                     and (e.source = visible_nodes.id or e.target = visible_nodes.id)
                    where visible_nodes.depth < %s
                )
                select distinct n.id, n.type, n.label, n.data, n.degree, n.in_degree, n.out_degree, n.pagerank, n.x, n.y
                from network_nodes n
                join visible_nodes vn on vn.id = n.id
                where n.version_id = %s
                order by n.label
                """,
                (node_id, version["id"], depth, version["id"]),
            )
            nodes = [to_node(row) for row in cur.fetchall()]

            cur.execute(
                """
                with recursive visible_nodes(id, depth) as (
                    select %s::text, 0
                    union
                    select
                        case when e.source = visible_nodes.id then e.target else e.source end,
                        visible_nodes.depth + 1
                    from visible_nodes
                    join network_edges e
                      on e.version_id = %s
                     and (e.source = visible_nodes.id or e.target = visible_nodes.id)
                    where visible_nodes.depth < %s
                )
                select distinct e.id, e.source, e.target, e.type, e.percentage, e.total_shares, e.data
                from network_edges e
                join visible_nodes source_node on source_node.id = e.source
                join visible_nodes target_node on target_node.id = e.target
                where e.version_id = %s
                order by e.id
                """,
                (node_id, version["id"], depth, version["id"]),
            )
            edges = [to_edge(row) for row in cur.fetchall()]
            summary = {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "investor_count": sum(1 for node in nodes if node["type"] == "investor"),
                "company_count": sum(1 for node in nodes if node["type"] == "company"),
                "density": len(edges) / max(len(nodes) * (len(nodes) - 1), 1),
            }
            result = graph_response(version, nodes, edges, summary)
            set_cache_headers(response, False)
            return set_cached(cache_key, result)
