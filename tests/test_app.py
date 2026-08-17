from fastapi.testclient import TestClient

from app.main import app
from app.routers import analytics, network, news
from app.routers.analytics import normalize_source
from app.routers.network import graph_response, to_edge, to_node

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_analytics_payload_validation_avoids_database():
    response = client.post("/analytics/source", json={"source": "ref", "visitor_id": "short"})
    assert response.status_code == 422


def test_helpers_and_routes_are_registered():
    assert normalize_source("  IDX Campaign! ") == "idxcampaign"
    node = to_node({"id": "a", "type": "company", "label": "A", "data": {}, "degree": 1, "in_degree": 1, "out_degree": 0, "pagerank": 0.5, "x": 1, "y": 2})
    edge = to_edge({"id": "e", "source": "a", "target": "b", "type": "owns", "data": {}, "percentage": 2.5, "total_shares": 10})
    assert graph_response({}, [node], [edge], {})["versions"] == []
    paths = set(app.openapi()["paths"])
    router_paths = {route.path for router in (analytics.router, news.router, network.router) for route in router.routes}
    assert {"/health"} <= paths
    assert {"/analytics/source", "/news/latest", "/network-analysis", "/network-analysis/search", "/network-analysis/nodes/{node_id:path}"} <= router_paths
