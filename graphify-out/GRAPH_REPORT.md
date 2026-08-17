# Graph Report - idx-stock-backend  (2026-08-17)

## Corpus Check
- 35 files · ~17,096 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 199 nodes · 262 edges · 27 communities (22 shown, 5 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7df0fabe`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- IDX Stock Backend
- xlsx_to_csv.py
- RTK Commands by Workflow
- What You Must Do When Invoked
- generate_network_graph.py
- /graphify
- graphify reference: extra exports and benchmark
- graphify reference: query, path, explain
- excel_serial_to_date
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native AGENTS.md integration
- graphify reference: incremental update and cluster-only
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- AGENTS.md
- extraction-spec.md
- idx-stock-backend
- /graphify

## God Nodes (most connected - your core abstractions)
1. `IDX Stock Backend` - 15 edges
2. `What You Must Do When Invoked` - 12 edges
3. `get_network_analysis()` - 11 edges
4. `get_network_node_subgraph()` - 11 edges
5. `RTK Commands by Workflow` - 11 edges
6. `/graphify` - 10 edges
7. `get_connection()` - 9 edges
8. `convert_xlsx_to_csv()` - 9 edges
9. `search_network()` - 8 edges
10. `graphify reference: extra exports and benchmark` - 8 edges

## Surprising Connections (you probably didn't know these)
- `test_helpers_and_routes_are_registered()` --calls--> `normalize_source()`  [EXTRACTED]
  tests/test_app.py → app/routers/analytics.py
- `test_helpers_and_routes_are_registered()` --calls--> `to_node()`  [EXTRACTED]
  tests/test_app.py → app/routers/network.py
- `test_helpers_and_routes_are_registered()` --calls--> `to_edge()`  [EXTRACTED]
  tests/test_app.py → app/routers/network.py
- `test_helpers_and_routes_are_registered()` --calls--> `graph_response()`  [EXTRACTED]
  tests/test_app.py → app/routers/network.py
- `get_network_analysis()` --calls--> `get_connection()`  [EXTRACTED]
  app/routers/network.py → app/core/db.py

## Import Cycles
- None detected.

## Communities (27 total, 5 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.18
Nodes (11): get_connection(), track_source_visit(), latest_articles(), Any, normalize_source(), SourceTrackingPayload, track_source(), get_latest_news() (+3 more)

### Community 1 - "IDX Stock Backend"
Cohesion: 0.06
Nodes (30): 1. Convert XLSX ke CSV, 2. Import CSV ke table raw, 3. Generate graph dan simpan ke DB, Analytics, API endpoints, Cache, CORS, Database tables (+22 more)

### Community 2 - "xlsx_to_csv.py"
Cohesion: 0.30
Nodes (14): Element, cell_text(), col_to_index(), convert_xlsx_to_csv(), iter_sheet_rows(), main(), Return zero-based column index from an Excel cell reference like 'C12'., Return list of (sheet_name, sheet_xml_path). (+6 more)

### Community 3 - "RTK Commands by Workflow"
Cohesion: 0.13
Nodes (14): Analysis & Debug (70-90% savings), Build & Compile (80-90% savings), Files & Search (60-75% savings), Git (59-80% savings), GitHub (26-87% savings), Golden Rule, Infrastructure (85% savings), JavaScript/TypeScript Tooling (70-90% savings) (+6 more)

### Community 4 - "What You Must Do When Invoked"
Cohesion: 0.13
Nodes (15): Part A - Structural extraction for code files, Part B - Semantic extraction (parallel subagents), Part C - Merge AST + semantic into final extraction, Step 0 - GitHub repos and multi-path merge (only if a URL or several paths), Step 1 - Ensure graphify is installed, Step 2.5 - Video and audio (only if video files detected), Step 2 - Detect files, Step 3 - Extract entities and relationships (+7 more)

### Community 5 - "generate_network_graph.py"
Cohesion: 0.35
Nodes (10): build_graph(), canonical_name(), canonical_tokens(), fuzzy_match_company(), get_rows(), main(), normalize_entity_name(), pagerank() (+2 more)

### Community 6 - "/graphify"
Cohesion: 0.20
Nodes (19): get_cached(), Any, Response, set_cache_headers(), set_cached(), active_version(), node_subgraph(), overview() (+11 more)

### Community 7 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 8 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 9 - "excel_serial_to_date"
Cohesion: 0.50
Nodes (4): date, Path, excel_serial_to_date(), main()

### Community 11 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 12 - "graphify reference: commit hook and native AGENTS.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native AGENTS.md integration (Trae), graphify reference: commit hook and native AGENTS.md integration

### Community 13 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 26 - "/graphify"
Cohesion: 0.20
Nodes (9): For /graphify add and --watch, For /graphify query, For the commit hook and native AGENTS.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Usage (+1 more)

## Knowledge Gaps
- **80 isolated node(s):** `idx-stock-backend`, `Usage`, `What graphify is for`, `Step 0 - GitHub repos and multi-path merge (only if a URL or several paths)`, `Step 1 - Ensure graphify is installed` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `What You Must Do When Invoked` connect `What You Must Do When Invoked` to `/graphify`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `get_connection()` connect `main.py` to `/graphify`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `idx-stock-backend`, `Usage`, `What graphify is for` to the rest of the system?**
  _80 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `IDX Stock Backend` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Should `RTK Commands by Workflow` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `What You Must Do When Invoked` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._