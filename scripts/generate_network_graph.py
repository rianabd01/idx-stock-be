import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]

FUZZY_AUTO_MATCH_THRESHOLD = 0.94
FUZZY_REVIEW_THRESHOLD = 0.86

LEGAL_TERMS = {
    "PT",
    "TBK",
    "PERSERO",
    "LTD",
    "LIMITED",
    "PTE",
    "PLC",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "INC",
}

TOKEN_SYNONYMS = {
    "PROPERTI": "PROPERTY",
    "PROPERTIES": "PROPERTY",
}


def normalize_entity_name(value: str) -> str:
    text = value.upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [token for token in text.split() if token not in LEGAL_TERMS]
    return " ".join(tokens)


def canonical_tokens(normalized_name: str) -> list[str]:
    return [TOKEN_SYNONYMS.get(token, token) for token in normalized_name.split()]


def canonical_name(normalized_name: str) -> str:
    return " ".join(canonical_tokens(normalized_name))


def token_overlap_score(first_tokens: list[str], second_tokens: list[str]) -> float:
    first_set = set(first_tokens)
    second_set = set(second_tokens)
    if not first_set or not second_set:
        return 0
    return len(first_set & second_set) / max(len(first_set), len(second_set))


def fuzzy_match_company(normalized_investor_name: str, companies: dict[str, dict]) -> tuple[str | None, str, float | None, str | None]:
    investor_canonical = canonical_name(normalized_investor_name)
    investor_tokens = investor_canonical.split()
    if not investor_tokens:
        return None, "unmatched", None, None

    candidates = []
    for share_code, company in companies.items():
        issuer_normalized = company["data"]["normalized_name"]
        issuer_canonical = canonical_name(issuer_normalized)
        issuer_tokens = issuer_canonical.split()
        if not issuer_tokens or investor_tokens[0] != issuer_tokens[0]:
            continue

        similarity = SequenceMatcher(None, investor_canonical, issuer_canonical).ratio()
        overlap = token_overlap_score(investor_tokens, issuer_tokens)
        confidence = (similarity * 0.7) + (overlap * 0.3)
        candidates.append((confidence, share_code, issuer_normalized))

    candidates.sort(reverse=True)
    if not candidates:
        return None, "unmatched", None, None

    best_confidence, best_code, best_issuer_normalized = candidates[0]
    second_confidence = candidates[1][0] if len(candidates) > 1 else 0
    is_clear_winner = best_confidence - second_confidence >= 0.03

    if best_confidence >= FUZZY_AUTO_MATCH_THRESHOLD and is_clear_winner:
        return best_code, "fuzzy_high_confidence", best_confidence, best_issuer_normalized
    if best_confidence >= FUZZY_REVIEW_THRESHOLD:
        return None, "review_needed", best_confidence, best_issuer_normalized
    return None, "unmatched", best_confidence, best_issuer_normalized


def get_rows():
    load_dotenv(BACKEND_ROOT / ".env")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    date,
                    share_code,
                    issuer_name,
                    investor_name,
                    investor_classification,
                    local_foreign,
                    nationality,
                    domicile,
                    holdings_scripless,
                    holdings_scrip,
                    total_holding_shares,
                    percentage
                from raw
                order by share_code, investor_name
                """
            )
            return cur.fetchall()


def pagerank(node_ids, edges, damping=0.85, iterations=40):
    node_count = len(node_ids)
    if node_count == 0:
        return {}

    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge["source"]].append(edge["target"])

    ranks = {node_id: 1 / node_count for node_id in node_ids}
    base = (1 - damping) / node_count

    for _ in range(iterations):
        next_ranks = {node_id: base for node_id in node_ids}
        dangling_rank = sum(ranks[node_id] for node_id in node_ids if not outgoing.get(node_id))
        dangling_share = damping * dangling_rank / node_count

        for node_id in node_ids:
            next_ranks[node_id] += dangling_share

        for source, targets in outgoing.items():
            share = damping * ranks[source] / len(targets)
            for target in targets:
                next_ranks[target] += share

        ranks = next_ranks

    return ranks


def build_graph(rows):
    period_date = rows[0][0].isoformat() if rows else None
    companies = {}
    company_by_normalized_name = {}

    for row in rows:
        _, share_code, issuer_name, *_ = row
        company_id = f"company:{share_code}"
        companies[share_code] = {
            "id": company_id,
            "type": "company",
            "label": share_code,
            "data": {
                "ticker": share_code,
                "company_name": issuer_name,
                "normalized_name": normalize_entity_name(issuer_name),
            },
        }
        company_by_normalized_name[normalize_entity_name(issuer_name)] = share_code

    investors = {}
    edges = []
    seen_edges = set()

    for index, row in enumerate(rows, start=1):
        (
            _,
            share_code,
            _,
            investor_name,
            investor_classification,
            local_foreign,
            nationality,
            domicile,
            holdings_scripless,
            holdings_scrip,
            total_holding_shares,
            percentage,
        ) = row

        normalized_investor_name = normalize_entity_name(investor_name)
        source_company_code = company_by_normalized_name.get(normalized_investor_name)
        match_method = "exact_normalized" if source_company_code else "unmatched"
        match_confidence = 1.0 if source_company_code else None
        matched_issuer_name = companies[source_company_code]["data"]["company_name"] if source_company_code else None

        if not source_company_code:
            source_company_code, match_method, match_confidence, matched_issuer_normalized = fuzzy_match_company(
                normalized_investor_name,
                companies,
            )
            if source_company_code:
                matched_issuer_name = companies[source_company_code]["data"]["company_name"]
            elif matched_issuer_normalized:
                matched_issuer_name = matched_issuer_normalized

        target_id = f"company:{share_code}"

        if source_company_code:
            source_id = f"company:{source_company_code}"
        else:
            source_id = f"investor:{len(investors) + 1}"
            if normalized_investor_name not in investors:
                investors[normalized_investor_name] = {
                    "id": source_id,
                    "type": "investor",
                    "label": investor_name,
                    "data": {
                        "investor_id": len(investors) + 1,
                        "investor_name": investor_name,
                        "investor_classification": investor_classification,
                        "local_foreign": local_foreign,
                        "nationality": nationality,
                        "domicile": domicile,
                        "normalized_name": normalized_investor_name,
                    },
                }
            else:
                source_id = investors[normalized_investor_name]["id"]

        if source_id == target_id:
            continue

        edge_key = (source_id, target_id, investor_name)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        edges.append(
            {
                "id": f"owns:{index}",
                "source": source_id,
                "target": target_id,
                "type": "owns",
                "label": f"{float(percentage):g}%",
                "data": {
                    "percentage": float(percentage),
                    "total_shares": int(total_holding_shares),
                    "holdings_scripless": int(holdings_scripless),
                    "holdings_scrip": int(holdings_scrip),
                    "investor_name_original": investor_name,
                    "matched_listed_company": source_company_code,
                    "matched_issuer_name": matched_issuer_name,
                    "match_method": match_method,
                    "match_confidence": round(match_confidence, 6) if match_confidence is not None else None,
                },
            }
        )

    node_map = {node["id"]: node for node in companies.values()}
    node_map.update({node["id"]: node for node in investors.values()})

    in_degree = Counter(edge["target"] for edge in edges)
    out_degree = Counter(edge["source"] for edge in edges)
    node_ids = sorted(node_map)
    ranks = pagerank(node_ids, edges)
    max_degree_denominator = max(len(node_ids) - 1, 1)

    for idx, node_id in enumerate(node_ids):
        node = node_map[node_id]
        degree = in_degree[node_id] + out_degree[node_id]
        angle = idx * 2.399963229728653
        radius = 120 * math.sqrt(idx + 1)
        node["metrics"] = {
            "degree": degree,
            "in_degree": in_degree[node_id],
            "out_degree": out_degree[node_id],
            "degree_centrality": degree / max_degree_denominator,
            "pagerank": ranks.get(node_id, 0),
        }
        node["position"] = {
            "x": round(math.cos(angle) * radius, 2),
            "y": round(math.sin(angle) * radius, 2),
        }

    nodes = list(node_map.values())
    nodes.sort(key=lambda node: (node["type"], node["label"]))

    match_counts = Counter(edge["data"].get("match_method", "unmatched") for edge in edges)
    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "investor_count": sum(1 for node in nodes if node["type"] == "investor"),
        "company_count": sum(1 for node in nodes if node["type"] == "company"),
        "density": len(edges) / max(len(nodes) * (len(nodes) - 1), 1),
        "match_counts": dict(sorted(match_counts.items())),
    }

    graph = {"nodes": nodes, "edges": edges, "summary": summary}
    version = {
        "id": 1,
        "period_date": period_date,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "versions": [version],
        "selected_version_id": 1,
        "graphs_by_version": {"1": graph},
        **graph,
    }


def save_graph_to_db(graph: dict, source: str) -> int:
    load_dotenv(BACKEND_ROOT / ".env")
    period_date = graph["versions"][0]["period_date"]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from network_versions where period_date = %s", (period_date,))
            cur.execute(
                "insert into network_versions (period_date, source) values (%s, %s) returning id",
                (period_date, source),
            )
            version_id = cur.fetchone()[0]
            cur.executemany(
                """
                insert into network_nodes
                    (id, version_id, type, label, data, degree, in_degree, out_degree, pagerank, x, y)
                values (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        node["id"],
                        version_id,
                        node["type"],
                        node["label"],
                        json.dumps(node["data"], ensure_ascii=False),
                        node["metrics"]["degree"],
                        node["metrics"]["in_degree"],
                        node["metrics"]["out_degree"],
                        node["metrics"]["pagerank"],
                        node["position"]["x"],
                        node["position"]["y"],
                    )
                    for node in graph["nodes"]
                ],
            )
            cur.executemany(
                """
                insert into network_edges
                    (id, version_id, source, target, type, label, percentage, total_shares, data)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [
                    (
                        edge["id"],
                        version_id,
                        edge["source"],
                        edge["target"],
                        edge["type"],
                        edge["label"],
                        edge["data"]["percentage"],
                        edge["data"]["total_shares"],
                        json.dumps(edge["data"], ensure_ascii=False),
                    )
                    for edge in graph["edges"]
                ],
            )
            return version_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-json", type=Path)
    parser.add_argument("--source", default="peng-06-00015-satu-persen.xlsx", help="Source filename stored in network_versions")
    args = parser.parse_args()

    rows = get_rows()
    graph = build_graph(rows)
    version_id = save_graph_to_db(graph, args.source)
    graph["versions"][0]["id"] = version_id
    graph["selected_version_id"] = version_id
    graph["graphs_by_version"] = {str(version_id): {"nodes": graph["nodes"], "edges": graph["edges"], "summary": graph["summary"]}}
    if args.export_json:
        args.export_json.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote: {args.export_json}")
    print(f"nodes: {graph['summary']['node_count']}")
    print(f"edges: {graph['summary']['edge_count']}")
    print(f"companies: {graph['summary']['company_count']}")
    print(f"investors: {graph['summary']['investor_count']}")
    print(f"match_counts: {graph['summary']['match_counts']}")


if __name__ == "__main__":
    main()
