# gtm-ahrefs

find companies that link to hr vendor sites (adp, workday, gusto, etc.) using ahrefs. each row = one website that links to that vendor’s portal.

## setup

```bash
cp .env.example .env
```

open `.env` and paste your ahrefs api key after `AHREFS_API_KEY=`

## run

```bash
python3 fetch_leads.py
```

pick a vendor from the menu. default fetch = 100 companies.

other useful commands:

```bash
python3 fetch_leads.py --vendor adp-workforcenow   # skip menu
python3 fetch_leads.py --limit 5                   # cheap test
python3 fetch_leads.py --list-vendors
```

## output

each run creates a new csv (old runs are kept):

```text
out/adp-workforcenow/2026-05-26/20260526-143022.csv
```

newest run: `ls -t out/adp-workforcenow/*/*.csv | head -1`

## csv columns

| column | what it is |
|--------|------------|
| `run_id` | this fetch (e.g. `20260526-143022`) |
| `fetched_at` | when (utc) |
| `vendor_slug` | e.g. `adp-workforcenow` |
| `company_domain` | site that linked to the vendor |
| `url_from` | page with the link (check this for qa) |
| `url_to` | vendor portal url (`cid=` = adp tenant id) |
| `domain_rating_source` | ahrefs dr |
| `traffic_domain` | traffic estimate |
| `title` | page title |

**note:** `1_per_domain` = one row per *linking* site, not per adp customer. same customer can appear twice if two sites link to the same portal. dedupe on `cid` in snowflake.

## add a vendor

copy `vendors/adp-workforcenow.json` → `vendors/your-vendor.json`, edit filters, run again. it shows up in the menu automatically.

**gusto** targets company career boards at `jobs.gusto.com/boards/…` (referrers = customer websites linking to their board).

## cost

`traffic_domain` costs ~10 ahrefs units per row (~1,000 units for 100 rows).
