# agent context — gtm-ahrefs

read this at the start of a **new cursor chat** on this repo. setup commands and full docs live in **README.md** — don’t duplicate them here; link or point the user there.

## a) what we’re doing

building a **technographic lead list** for rippling gtm: companies that likely use competitor hr/payroll/ats stacks (workday, adp, gusto, deel, bamboohr, …).

**method:** ahrefs `all-backlinks` api — find domains whose websites link **to** known vendor career portal urls (e.g. `workforcenow.adp.com`, `jobs.gusto.com/boards`, `{co}.bamboohr.com/careers`).

**output:** csv per run under `out/{vendor_slug}/{date}/{run_id}.csv` → eventually **snowflake** for dedupe, enrichment, outreach.

## b) why we’re doing it

rippling wants to reach **switchers** — orgs already on adp/workday/etc. public career links to those portals are a strong, observable signal (not job-title guessing).

this repo is the **extract** step only: cheap, repeatable ahrefs pulls with shared icp hygiene. warehouse logic (tenant dedupe, company enrichment) is **downstream**, not fully built here yet.

## c) how it works

```
fetch_leads.py          → cli, ahrefs http, csv write
vendors/{slug}.json     → per-vendor target + url_to filters + menu_order
vendors/_defaults.json  → global referrer blocklist + edu/gov rules (all vendors)
.env                    → AHREFS_API_KEY (gitignored)
out/                    → immutable run csvs
```

**flow**

1. user runs `python3 fetch_leads.py` (menu) or `--vendor adp`
2. script loads `vendors/{slug}.json`, merges `_defaults.json` into `url_from_exclude`
3. builds ahrefs `where` json: icp rules + vendor `url_to_contains` + dr/traffic mins
4. `GET /v3/site-explorer/all-backlinks`, `aggregation=1_per_domain`, default `limit=500`
5. writes csv with `run_id`, `fetched_at`, `vendor_slug`, backlink fields

**ahrefs semantics (critical)**

- `1_per_domain` = one row per **referring domain** (who linked), not per vendor customer
- `company_domain` = **referrer** root domain — often **not** the employer on the portal
- real customer key is usually in **`url_to`** (adp `cid=`, workday `t=` or `myworkdayjobs.com`, etc.)

**global icp (every vendor, automatic)**

- `tld_class_source = normal` (drops ahrefs edu/gov class)
- `root_name_suffix_exclude` — `.edu`, `.gov`, `.gov.uk`, `.ac.uk`, …
- ~200 `url_from_exclude` tokens + `url_from_require_any` (careers/jobs path on referrer) — see `_defaults.json`

edit blocklist: **`vendors/_defaults.json`** only (unless vendor-specific `url_from_exclude` in `{slug}.json`).

**vendors (menu order = competitor size)**

| slug | signal |
|------|--------|
| `workday` | links to `myworkday.com` |
| `adp` | links to `workforcenow.adp.com` |
| `deel` | links to `jobs.deel.com` |
| `gusto` | links to `jobs.gusto.com/boards` |
| `bamboohr` | links to `{tenant}.bamboohr.com/careers` |

add vendor = new `vendors/{slug}.json`; menu picks it up via `display_name` + `menu_order`.

## d) where we are now

**done**

- single script `fetch_leads.py` + json vendor configs (no per-vendor scripts)
- interactive menu, proper-case labels (ADP, Workday, …)
- output path `out/{vendor}/{date}/{run_id}.csv` (no `latest.csv`)
- renamed adp slug from `adp-workforcenow` → `adp`
- global edu/gov exclusion + extensive shared `url_from_exclude`
- gusto/deel/bamboohr configs from real portal patterns
- readme documents schema, icp, snowflake direction
- sample runs in `out/` may exist on github; `.env` never committed

**known quality limits (don’t over-promise)**

- sorting by `domain_rating_source:desc` still favors large referrers; filters help but aren’t perfect
- workday `myworkday.com` target is broad (login/learning/outage urls) — discussed tightening to `myworkdayjobs.com` later
- media/job-board rows reduced by blocklist; **tenant dedupe in snowflake** is still required for outreach
- ahrefs may cap rows per request on some plans — watch if `--limit 500` returns fewer

**not done / sensible next steps**

- workday: `tenant_id` in csv; stricter `url_from_require_any` + login/learning `url_to_exclude` in `vendors/workday.json`
- optional: `myworkdayjobs.com` primary target (may shrink pool vs outage urls)
- optional post-fetch `--strict` filter (tighter careers path on `url_from` than `url_from_require_any`)
- snowflake load + dbt models for dedupe/enrichment
- do **not** add `examples/` sample csvs unless user asks (they rejected this)
- do **not** reintroduce `latest.csv`

## conventions for agents

- **stdlib only** — no new pip deps unless user asks
- **minimal diffs** — vendor tuning = json edits in `vendors/`, not script rewrites
- **secrets** — only `.env`; never commit api keys or add keys to code/comments
- **commits** — only when user asks to commit/push
- **icp** — commercial employers only; user explicitly wants **no .edu / .gov referrers**
- when improving quality: prefer `_defaults.json` blocklist + ahrefs `where` over complex python unless necessary
- user repo: https://github.com/ripplingdmytro/gtm-ahrefs

## quick pointers

| task | where |
|------|--------|
| run / setup | README.md |
| block noisy sites | `vendors/_defaults.json` → `url_from_exclude` |
| tune one vendor | `vendors/{slug}.json` |
| ahrefs filter logic | `fetch_leads.py` → `build_where_filter()` |
| review a run | `out/{vendor}/*/*.csv`, qa `url_from` + `url_to` |
