from typing import Any


def active_version(cur) -> dict[str, Any] | None:
    cur.execute("select id, period_date::text, imported_at::text from network_versions where is_active = true order by period_date desc, id desc limit 1")
    return cur.fetchone()


def overview(cur, version_id: int, node_limit: int):
    cur.execute(
        """select id, type, label, data, degree, in_degree, out_degree, pagerank, x, y
        from network_nodes where version_id = %s order by pagerank desc, degree desc, label limit %s""",
        (version_id, node_limit),
    )
    nodes = cur.fetchall()
    cur.execute(
        """with selected_nodes as (select id from network_nodes where version_id = %s order by pagerank desc, degree desc, label limit %s)
        select e.id, e.source, e.target, e.type, e.percentage, e.total_shares, e.data from network_edges e
        join selected_nodes source_node on source_node.id = e.source join selected_nodes target_node on target_node.id = e.target
        where e.version_id = %s order by e.percentage desc""",
        (version_id, node_limit, version_id),
    )
    edges = cur.fetchall()
    cur.execute(
        """with node_counts as (select count(*) as node_count, count(*) filter (where type = 'investor') as investor_count,
        count(*) filter (where type = 'company') as company_count from network_nodes where version_id = %s),
        edge_counts as (select count(*) as edge_count from network_edges where version_id = %s)
        select node_count, edge_count, investor_count, company_count,
        case when node_count <= 1 then 0 else edge_count::numeric / (node_count::numeric * (node_count::numeric - 1)) end as density
        from node_counts, edge_counts""",
        (version_id, version_id),
    )
    return nodes, edges, cur.fetchone()


def search_nodes(cur, query: str):
    cur.execute(
        """select n.id, n.type, n.label, n.data, n.degree, n.in_degree, n.out_degree, n.pagerank, n.x, n.y
        from network_nodes n join network_versions v on v.id = n.version_id where v.is_active = true
        and (n.id ilike %s or n.label ilike %s or n.data::text ilike %s)
        order by case when n.label ilike %s then 0 else 1 end, n.pagerank desc, n.degree desc, n.label limit 12""",
        (f"%{query}%", f"%{query}%", f"%{query}%", f"{query}%"),
    )
    return cur.fetchall()


def node_subgraph(cur, version_id: int, node_id: str, depth: int):
    recursive = """with recursive visible_nodes(id, depth) as (
        select %s::text, 0 union select case when e.source = visible_nodes.id then e.target else e.source end, visible_nodes.depth + 1
        from visible_nodes join network_edges e on e.version_id = %s and (e.source = visible_nodes.id or e.target = visible_nodes.id)
        where visible_nodes.depth < %s)"""
    cur.execute(
        recursive + """ select distinct n.id, n.type, n.label, n.data, n.degree, n.in_degree, n.out_degree, n.pagerank, n.x, n.y
        from network_nodes n join visible_nodes vn on vn.id = n.id where n.version_id = %s order by n.label""",
        (node_id, version_id, depth, version_id),
    )
    nodes = cur.fetchall()
    cur.execute(
        recursive + """ select distinct e.id, e.source, e.target, e.type, e.percentage, e.total_shares, e.data
        from network_edges e join visible_nodes source_node on source_node.id = e.source
        join visible_nodes target_node on target_node.id = e.target where e.version_id = %s order by e.id""",
        (node_id, version_id, depth, version_id),
    )
    return nodes, cur.fetchall()
