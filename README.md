# gtm-ahrefs

Lead gen via Ahrefs: find companies that publicly link to HR vendor surfaces (Workday, ADP, Gusto, etc.).

Repo: https://github.com/ripplingdmytro/gtm-ahrefs

## Setup

1. Copy `.env.example` to `.env`
2. Paste your Ahrefs API key after `AHREFS_API_KEY=` (one line, no quotes)

`.env` is gitignored.

## Run

**Interactive menu** (pick ADP, Workday, Gusto, …):

```bash
python3 fetch_leads.py
```

Skip the menu:

```bash
python3 fetch_leads.py --vendor adp-workforcenow
```

List vendors:

```bash
python3 fetch_leads.py --list-vendors
```

Small test:

```bash
python3 fetch_leads.py --vendor adp-workforcenow --limit 5
```

## Output paths

Each run writes a **new** file (nothing overwritten except `latest.csv`):

```text
out/adp-workforcenow/2026-05-26/20260526-143022.csv
out/adp-workforcenow/latest.csv
```

- **Folders** use `/` as separators (normal on disk).
- **Names** use dashes only: `adp-workforcenow`, `2026-05-26`, `20260526-143022` — no slashes inside filenames or slug values (pipeline-friendly).

Override path manually:

```bash
python3 fetch_leads.py --vendor adp-workforcenow --output ./my-export.csv
```

## CSV schema (same for every vendor)

| Column | Description |
|--------|-------------|
| `run_id` | e.g. `20260526-143022` |
| `fetched_at` | UTC ISO timestamp |
| `vendor_slug` | e.g. `adp-workforcenow` |
| `company_domain` | Root domain of linking company |
| `url_from` | Page with the link |
| `url_to` | Target URL (Workforce Now, etc.) |
| `domain_rating_source` | Ahrefs DR |
| `traffic_domain` | Organic traffic estimate (10 API units/row) |
| `title` | Referring page title |

## Add a vendor (Workday, Gusto, SAP, …)

Copy `vendors/adp-workforcenow.json` → `vendors/workday.json` (or similar), then edit:

- `vendor_slug` (must match filename, use dashes)
- `target`, `url_to_contains`, exclude lists, `order_by`

No new script needed — one `fetch_leads.py` loads the config.

## API cost

`traffic_domain` in `select` costs **10 units per row** (~1,000 units for 100 rows).
