# gtm-ahrefs

find companies that link to hr vendor career portals using the ahrefs backlinks api. each row is one **referring domain** that links to a vendor surface (ADP Workforce Now, Workday, Gusto boards, etc.).

built for rippling gtm → technographics / snowflake. repo: https://github.com/ripplingdmytro/gtm-ahrefs

## setup

```bash
cp .env.example .env
```

open `.env` and paste your ahrefs api key:

```text
AHREFS_API_KEY=your-key-here
```

requires python 3.9+ (stdlib only).

## run

```bash
python3 fetch_leads.py
```

interactive menu (largest → smallest competitor). default = **100** companies per run.

| # | vendor | slug |
|---|--------|------|
| 1 | Workday | `workday` |
| 2 | ADP | `adp` |
| 3 | Deel | `deel` |
| 4 | Gusto | `gusto` |
| 5 | BambooHR | `bamboohr` |

other commands:

```bash
python3 fetch_leads.py --vendor adp      # skip menu
python3 fetch_leads.py --limit 5         # cheap test
python3 fetch_leads.py --list-vendors
```

## output

each run writes a **new** csv (previous runs are kept):

```text
out/{vendor_slug}/{YYYY-MM-DD}/{run_id}.csv
```

example: `out/adp/2026-05-26/20260526-143022.csv`

newest file for a vendor:

```bash
ls -t out/adp/*/*.csv | head -1
```

`out/` may be committed for sample runs; your local `.env` is never committed.

## csv columns

| column | what it is |
|--------|------------|
| `run_id` | fetch id, e.g. `20260526-143022` |
| `fetched_at` | utc timestamp |
| `vendor_slug` | e.g. `adp`, `workday` |
| `company_domain` | **referring** root domain (who linked) |
| `url_from` | page with the backlink — **qa this** |
| `url_to` | vendor portal url (proof of stack) |
| `domain_rating_source` | ahrefs dr of referrer |
| `traffic_domain` | ahrefs traffic estimate of referrer |
| `title` | referring page title |

### how to read rows

- **`1_per_domain`** (ahrefs): one row per **linking site**, not per customer on the vendor portal.
- **`company_domain`** is usually **not** the employer on ADP/Workday — it’s who published the link. for outreach, dedupe on **tenant** parsed from `url_to`:
  - **ADP:** `cid=` in `workforcenow.adp.com` urls
  - **Workday:** `t=` on outage urls, or `*.myworkdayjobs.com` host
  - **Gusto:** board id in `jobs.gusto.com/boards/…`
  - **BambooHR:** subdomain `{co}.bamboohr.com`
  - **Deel:** path under `jobs.deel.com`
- two rows can share the same tenant if two different sites link to the same portal.

## global ICP filters (all vendors)

every fetch applies shared rules from `vendors/_defaults.json` + `fetch_leads.py`. you do **not** need to copy them into each vendor file.

### edu / gov (not our ICP)

referring sites classified as education or government are excluded:

1. ahrefs `tld_class_source = normal` (drops edu/gov tld class)
2. `root_name_source` must not end with common public-sector suffixes (`.edu`, `.gov`, `.gov.uk`, `.ac.uk`, `.edu.au`, `.gov.au`, `.go.jp`, …) — see `root_name_suffix_exclude` in `_defaults.json`

### shared blocklist (~140 tokens)

`url_from_exclude` in `_defaults.json` drops noisy **referrers**, including:

- media & listicles (e.g. business insider, techcrunch, forbes, axios)
- job boards & ats aggregators (indeed, glassdoor, greenhouse, icims, `python.org/jobs`, `myworkdayjobs.com`)
- social & newsletters (patreon, substack, beehiiv, medium)
- free / temp hosts (notion, canva, `web.app`, azure/wordpress/netlify patterns)
- obvious non-careers noise (toast ordering pages, login spam hosts, etc.)

### add a block rule

edit `vendors/_defaults.json`:

```json
"url_from_exclude": [
  "some-noisy-site.com",
  ...
]
```

re-run any vendor — no script change needed.

vendor-specific extras go in `vendors/{slug}.json` → `url_from_exclude` (merged on top of defaults).

## vendors & signals

| vendor | ahrefs `target` | link must contain (`url_to`) |
|--------|-----------------|------------------------------|
| Workday | `myworkday.com` | `myworkday.com` |
| ADP | `adp.com` | `workforcenow.adp.com` |
| Deel | `jobs.deel.com` | `jobs.deel.com` |
| Gusto | `jobs.gusto.com` | `jobs.gusto.com/boards` |
| BambooHR | `bamboohr.com` | `bamboohr.com/careers` |

each vendor config: `vendors/{slug}.json` — `menu_order` (lower = shown first in menu), `domain_rating_min`, `traffic_domain_min`, vendor-only `url_to_exclude`.

### add a vendor

1. copy `vendors/adp.json` → `vendors/your-slug.json`
2. set `vendor_slug` = filename stem, `display_name`, `menu_order`
3. set `target`, `url_to_contains`, and vendor `url_to_exclude`
4. run `python3 fetch_leads.py --list-vendors` — it appears in the menu

## project layout

```text
fetch_leads.py          # cli + ahrefs api
vendors/
  _defaults.json        # global ICP blocklist (all vendors)
  adp.json              # per-vendor ahrefs filters
  workday.json
  ...
out/                    # run csvs (dated paths)
.env.example
```

## ahrefs cost

`traffic_domain` in `select` costs **~10 units per row**. a 100-row run is roughly **~1,000 units** plus base request cost. use `--limit 5` while testing filters.

## snowflake (recommended next steps)

1. load raw csvs from `out/` with `run_id`, `vendor_slug`, `fetched_at` as dimensions
2. parse `tenant_id` from `url_to` in sql/dbt
3. dedupe to one row per `vendor_slug` + `tenant_id` (best referrer / careers url)
4. enrich tenant → company domain for outreach (clearbit, manual qa, etc.)

quality tiers in warehouse are more reliable than trying to perfect ahrefs filters alone.
