# IDX Stock Backend

Backend Python untuk **IDX Stock Network Analysis**. Service ini bertanggung jawab untuk ingest data publikasi IDX, membangun graph kepemilikan saham, menyimpan graph ke PostgreSQL, dan menyediakan API yang dipakai frontend.

Production API saat ini tersedia di:

```text
https://101-32-249-2.sslip.io
```

## Tech stack

- Python 3.13
- FastAPI
- Uvicorn
- PostgreSQL
- psycopg 3
- python-dotenv
- uv
- Nginx + systemd untuk VPS deployment

## Struktur folder

```text
app/
  main.py                 FastAPI app dan endpoint publik

scripts/
  generate_network_graph.py   build graph dari table raw, insert ke DB, export JSON mock
  import_raw.py               import CSV IDX ke table raw
  inspect_db.py               util inspeksi koneksi/schema DB

assets/
  xlsx_to_csv.py              converter XLSX IDX ke CSV
  Sheet_1.csv                 CSV hasil export/import terakhir
```

## Environment

Buat `.env` di root backend:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME
```

Jangan commit `.env` karena berisi credential database.

## Menjalankan backend local

Install dependency:

```bash
uv sync
```

Jalankan API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
```

Expected:

```json
{"ok": true}
```

## API endpoints

### Health

```text
GET /health
```

Response:

```json
{"ok": true}
```

### Network overview

```text
GET /network-analysis?limit=1200
GET /network-analysis?mode=full
```

Default `mode=overview` mengambil node terpenting berdasarkan PageRank dan degree, supaya initial load frontend tidak langsung menarik seluruh graph.

### Search node

```text
GET /network-analysis/search?q=pollux
```

Return maksimal 12 node hasil pencarian dari table `network_nodes`.

### Node subgraph

```text
GET /network-analysis/nodes/company:SRTG?depth=1
```

`depth` dibatasi 1-3 hop. Endpoint ini dipakai saat user memilih node di frontend.

### Source tracking

```text
POST /analytics/source
```

Payload:

```json
{
  "source": "instagram",
  "visitor_id": "browser-generated-id",
  "path": "/?source=instagram"
}
```

Backend melakukan dedupe per `source + visitor_id + 10-minute bucket`. Visitor yang sama boleh tercatat lagi setelah masuk bucket 10 menit berikutnya.

## CORS

Allowed origins saat ini:

```text
http://localhost:3000
http://127.0.0.1:3000
https://idx-stock.netlify.app
```

Jika domain frontend berubah, update `allow_origins` di `app/main.py`, deploy ulang, lalu restart service.

## Cache

Endpoint graph/search/subgraph memakai in-memory TTL cache:

```text
TTL: 300 detik / 5 menit
```

Response menyertakan header:

```text
Cache-Control: public, max-age=300
X-Cache: HIT | MISS
```

Cache ini lokal di proses Python. Jika service restart, cache hilang. Untuk multi-worker/production skala lebih besar, pindahkan ke Redis.

## Database tables

### Raw IDX import

```text
raw
```

Berisi data mentah dari CSV IDX, termasuk `date`, `share_code`, `issuer_name`, `investor_name`, `total_holding_shares`, dan `percentage`.

### Network graph

```text
network_versions
network_nodes
network_edges
```

Graph dibangun dari `raw` oleh `scripts/generate_network_graph.py`.

### Analytics

```text
source_visits
```

Mencatat traffic source campaign dengan dedupe 10 menit.

## Pipeline data IDX

### 1. Convert XLSX ke CSV

```bash
uv run python assets/xlsx_to_csv.py assets/peng-06-00015-satu-persen.xlsx assets/Sheet_1.csv
```

Converter otomatis mencari header row IDX:

```text
DATE, SHARE_CODE, ISSUER_NAME, INVESTOR_NAME
```

### 2. Import CSV ke table raw

```bash
uv run python scripts/import_raw.py
```

Catatan: script import melakukan `truncate table raw` sebelum insert ulang.

Tanggal Excel serial seperti `46203` dikonversi menjadi PostgreSQL `date`, contoh:

```text
46203 -> 2026-06-30
```

### 3. Generate graph dan simpan ke DB

```bash
uv run python scripts/generate_network_graph.py
```

Script ini:

1. membaca table `raw`.
2. membuat node `company:<ticker>` dan `investor:<id>`.
3. membuat edge ownership `source -> target`.
4. melakukan matching investor yang sebenarnya listed company.
5. menghitung degree dan PageRank sederhana.
6. menyimpan hasil ke `network_versions`, `network_nodes`, `network_edges`.
7. menulis fallback JSON ke frontend mock.

## Entity matching

Matching investor ke emiten dilakukan konservatif:

1. exact normalized name.
2. fuzzy high confidence dengan syarat ketat.

Normalisasi membuang legal suffix seperti:

```text
PT, TBK, PERSERO, LTD, LIMITED, PTE, PLC, CORP, INC
```

Ada synonym kecil untuk kasus bahasa:

```text
PROPERTI / PROPERTIES -> PROPERTY
```

Contoh match:

```text
SARATOGA INVESTAMA SEDAYA TBK PT -> company:SRTG
PT POLLUX PROPERTI INDONESIA TBK -> company:POLL
```

Edge menyimpan metadata audit:

```json
{
  "matched_listed_company": "POLL",
  "matched_issuer_name": "POLLUX PROPERTIES INDONESIA Tbk",
  "match_method": "fuzzy_high_confidence",
  "match_confidence": 1.0
}
```

## Deployment VPS

Backend production dideploy di VPS:

```text
Host: 101.32.249.2
Path: /home/ubuntu/apps/idx-stock-backend
Service: idx-stock-backend.service
Internal port: 127.0.0.1:8001
Public HTTPS: https://101-32-249-2.sslip.io
```

### Sync backend ke VPS

Dari root project frontend:

```bash
rsync -az --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'assets/*.xlsx' \
  --exclude 'assets/*.csv' \
  -e 'ssh -i /Users/rianabdillah/Downloads/local.pem' \
  "idx-stcok-backend/" \
  ubuntu@101.32.249.2:/home/ubuntu/apps/idx-stock-backend/
```

### Restart service

```bash
ssh -i /Users/rianabdillah/Downloads/local.pem ubuntu@101.32.249.2 \
  'sudo systemctl restart idx-stock-backend && sudo systemctl status idx-stock-backend --no-pager'
```

### Logs

```bash
ssh -i /Users/rianabdillah/Downloads/local.pem ubuntu@101.32.249.2 \
  'sudo journalctl -u idx-stock-backend -f'
```

### Nginx

Nginx terminate HTTPS dan proxy ke backend internal:

```text
443/80 -> nginx -> 127.0.0.1:8001
```

Certbot certificate memakai domain sslip.io:

```text
101-32-249-2.sslip.io
```

Cek certificate renewal:

```bash
ssh -i /Users/rianabdillah/Downloads/local.pem ubuntu@101.32.249.2 \
  'sudo certbot renew --dry-run'
```

## Smoke test production

```bash
curl https://101-32-249-2.sslip.io/health
curl 'https://101-32-249-2.sslip.io/network-analysis/search?q=pollux'
curl 'https://101-32-249-2.sslip.io/network-analysis/nodes/company%3ASRTG?depth=1'
```

Expected:

```text
/health -> {"ok": true}
/search?q=pollux -> includes company:POLI and company:POLL
/nodes/company:SRTG?depth=1 -> returns SRTG subgraph
```

## Operational notes

- Jangan jalankan Uvicorn production langsung di shell; gunakan systemd.
- Setelah deploy code backend, restart `idx-stock-backend`.
- Setelah update graph data, jalankan `scripts/generate_network_graph.py` lalu restart backend jika ingin clear in-memory cache segera.
- Jika frontend domain berubah, update CORS dan redeploy backend.
- Jika butuh scale multi-worker, ganti in-memory cache ke Redis.
