from typing import Any

from fastapi import APIRouter, Query, Response

from app.core.cache import get_cached, set_cache_headers, set_cached
from app.core.db import get_connection
from app.repositories.network_repository import active_version, node_subgraph, overview, search_nodes

router = APIRouter()


def to_node(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "type": row["type"], "label": row["label"], "data": row["data"], "metrics": {"degree": row["degree"], "in_degree": row["in_degree"], "out_degree": row["out_degree"], "pagerank": float(row["pagerank"])}, "position": {"x": float(row["x"]), "y": float(row["y"])}}


def to_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "source": row["source"], "target": row["target"], "type": row["type"], "data": {**row["data"], "percentage": float(row["percentage"]), "total_shares": int(row["total_shares"])}}


def graph_response(version, nodes, edges, summary):
    versions = [{"id": version["id"], "period_date": version["period_date"], "imported_at": version["imported_at"]}] if version else []
    return {"versions": versions, "nodes": nodes, "edges": edges, "summary": summary}


@router.get("/network-analysis")
def get_network_analysis(response: Response, mode: str = "overview", limit: int = Query(default=1200, ge=1, le=100000)):
    cache_key = f"network-analysis:{mode}:{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached
    with get_connection() as conn, conn.cursor() as cur:
        version = active_version(cur)
        if version is None:
            return graph_response({}, [], [], {})
        rows, edge_rows, summary_row = overview(cur, version["id"], 100000 if mode == "full" else limit)
    nodes, edges = [to_node(row) for row in rows], [to_edge(row) for row in edge_rows]
    summary = {"node_count": summary_row["node_count"], "edge_count": summary_row["edge_count"], "investor_count": summary_row["investor_count"], "company_count": summary_row["company_count"], "density": float(summary_row["density"])}
    result = graph_response(version, nodes, edges, summary)
    set_cache_headers(response, False)
    return set_cached(cache_key, result)


@router.get("/network-analysis/search")
def search_network(response: Response, q: str = Query(default="", min_length=0)):
    query = q.strip()
    if not query:
        return []
    cache_key = f"network-analysis:search:{query.lower()}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached
    with get_connection() as conn, conn.cursor() as cur:
        result = [to_node(row) for row in search_nodes(cur, query)]
    set_cache_headers(response, False)
    return set_cached(cache_key, result)


@router.get("/network-analysis/nodes/{node_id:path}")
def get_network_node_subgraph(node_id: str, response: Response, depth: int = Query(default=1, ge=1, le=3)):
    cache_key = f"network-analysis:node:{node_id}:depth:{depth}"
    cached = get_cached(cache_key)
    if cached is not None:
        set_cache_headers(response, True)
        return cached
    with get_connection() as conn, conn.cursor() as cur:
        version = active_version(cur)
        if version is None:
            return graph_response({}, [], [], {})
        rows, edge_rows = node_subgraph(cur, version["id"], node_id, depth)
    nodes, edges = [to_node(row) for row in rows], [to_edge(row) for row in edge_rows]
    summary = {"node_count": len(nodes), "edge_count": len(edges), "investor_count": sum(node["type"] == "investor" for node in nodes), "company_count": sum(node["type"] == "company" for node in nodes), "density": len(edges) / max(len(nodes) * (len(nodes) - 1), 1)}
    result = graph_response(version, nodes, edges, summary)
    set_cache_headers(response, False)
    return set_cached(cache_key, result)
