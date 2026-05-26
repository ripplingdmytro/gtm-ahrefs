# Lead gen: vendor signals via Ahrefs

Local script to find companies that publicly link to ADP Workforce Now (`workforcenow.adp.com`) — a strong ATS / HR stack signal.

## Setup

```bash
export AHREFS_API_KEY='your-key-here'
```

Requires Python 3.10+ (stdlib only).

## Run

Default test run (5 rows, sorted by highest domain rating):

```bash
python fetch_adp_workforcenow.py
```

Custom limit and output file:

```bash
python fetch_adp_workforcenow.py --limit 25 --output adp_leads.csv
```

## Output CSV

| Column | Description |
|--------|-------------|
| `company_domain` | Root domain of the linking company |
| `vendor` | Fixed tag `adp_workforcenow` |
| `url_from` | Page that links to Workforce Now |
| `domain_rating_source` | Ahrefs DR of referring domain |
| `traffic_domain` | Estimated monthly organic traffic (costs API units) |
| `title` | Referring page title |

## API cost note

`traffic_domain` costs **10 units per row** in `select`. Keep `--limit` low while testing.

## Filters

See `build_where_filter()` in `fetch_adp_workforcenow.py` for the full Ahrefs `where` JSON (Workforce Now target URL, DR ≥ 20, traffic ≥ 1000, and exclude lists for noisy referrers/targets).
