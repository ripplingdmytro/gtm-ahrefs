# gtm-ahrefs

find companies that link to hr vendor sites (ADP, Workday, Gusto, etc.) using ahrefs. each row = one website that links to that vendor’s portal.

## setup

```bash
cp .env.example .env
```

open `.env` and paste your ahrefs api key after `AHREFS_API_KEY=`

## run

```bash
python3 fetch_leads.py
```

pick a vendor from the menu (largest → smallest competitor). default fetch = 100 companies.

menu order: **Workday** → **ADP** → **Deel** → **Gusto** → **BambooHR**

other useful commands:

```bash
python3 fetch_leads.py --vendor adp   # skip menu
python3 fetch_leads.py --limit 5      # cheap test
python3 fetch_leads.py --list-vendors
```

## output

each run creates a new csv (old runs are kept):

```text
out/adp/2026-05-26/20260526-143022.csv
```

newest run: `ls -t out/adp/*/*.csv | head -1`

## csv columns

| column | what it is |
|--------|------------|
| `run_id` | this fetch (e.g. `20260526-143022`) |
| `fetched_at` | when (utc) |
| `vendor_slug` | e.g. `adp` |
| `company_domain` | site that linked to the vendor |
| `url_from` | page with the link (check this for qa) |
| `url_to` | vendor portal url (`cid=` = ADP tenant id) |
| `domain_rating_source` | ahrefs dr |
| `traffic_domain` | traffic estimate |
| `title` | page title |

**note:** `1_per_domain` = one row per *linking* site, not per ADP customer. same customer can appear twice if two sites link to the same portal. dedupe on `cid` in snowflake.

## add a vendor

copy `vendors/adp.json` → `vendors/your-vendor.json`, edit filters, set `display_name` (menu label) and `menu_order` (lower = bigger competitor, shows first).

**global ICP filters** (all vendors, in `vendors/_defaults.json` + `fetch_leads.py`): no `.edu` / `.gov` referrers (`tld_class_source=normal` + suffix rules), plus a shared blocklist (media, job boards, social, free hosts). add more tokens to `_defaults.json` → `url_from_exclude`.

| vendor | signal |
|--------|--------|
| Workday | `*.myworkday.com` |
| ADP | `workforcenow.adp.com` |
| Deel | `jobs.deel.com/…` |
| Gusto | `jobs.gusto.com/boards/…` |
| BambooHR | `{company}.bamboohr.com/careers` |

## cost

`traffic_domain` costs ~10 ahrefs units per row (~1,000 units for 100 rows).
