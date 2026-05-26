#!/usr/bin/env python3
"""
Fetch companies linking to ADP Workforce Now (ATS signal) via Ahrefs all-backlinks.

Usage:
  export AHREFS_API_KEY='your-key'
  python fetch_adp_workforcenow.py
  python fetch_adp_workforcenow.py --limit 5 --output adp_leads.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_URL = "https://api.ahrefs.com/v3/site-explorer/all-backlinks"

# Substrings that must NOT appear in the target URL (adp.com noise / regional / marketing).
URL_TO_EXCLUDE = (
    "www.adp.com",
    "investors",
    "payinsights",
    "mediacenter",
    "press",
    "runpayroll",
    "uk.adp.com",
    "in.adp.com",
    "fr.adp.com",
    "apps.adp.com",
)

# Substrings that must NOT appear in the referring page URL (directories, press, etc.).
URL_FROM_EXCLUDE = (
    "wikipedia",
    "apple.com",
    "google",
    "seo",
    "backlink",
    "blog",
    "news",
    "reddit",
    "quora",
    "youtube",
    "twitter",
    "linkedin",
    "facebook",
    "instagram",
    "github",
    "microsoft",
    "amazon",
    "spotify",
    "article",
    "press",
    "goo.gl",
    "bsky",
    "mozilla",
    "yahoo",
    "cloudfront",
    "bbc",
    "bloomberg",
    "best",
    "top",
    "medium",
    "cnn",
    "waze",
    "myshopify",
    "squarespace",
    "weebly",
    "forbes",
    "tips",
    "report",
    "guidance",
    "guide",
    "wixsite",
    "substack",
    "telegram",
    "t.me",
    "bing",
    "archive",
    "how-",
    "server",
    "nytimes",
    "jotform",
    "tripadvisor",
    "time.com",
    "netlify",
    "forum",
    "wsj.com",
    "mstdn",
    "skills",
    "vercel",
    "gitlab",
    "pages.dev",
    "site.com",
    "wpengine.com",
    "webflow.com",
    "webflow.io",
    "indeed",
    "glassdoor",
    "zendesk",
    "mastodon",
    "bio.link",
    "wiki",
    "template",
)

CSV_COLUMNS = (
    "company_domain",
    "vendor",
    "url_from",
    "domain_rating_source",
    "traffic_domain",
    "title",
)


def _not_substring(field: str, value: str) -> dict[str, Any]:
    return {"not": {"field": field, "is": ["substring", value]}}


def build_where_filter() -> dict[str, Any]:
    """Ahrefs filter expression for ADP Workforce Now ATS backlinks."""
    clauses: list[dict[str, Any]] = [
        {"field": "url_to_plain", "is": ["substring", "workforcenow.adp.com"]},
        {"field": "domain_rating_source", "is": ["gte", 20]},
        {"field": "traffic_domain", "is": ["gte", 1000]},
    ]
    for token in URL_TO_EXCLUDE:
        clauses.append(_not_substring("url_to_plain", token))
    for token in URL_FROM_EXCLUDE:
        clauses.append(_not_substring("url_from_plain", token))
    return {"and": clauses}


def fetch_backlinks(
    api_key: str,
    *,
    limit: int,
    target: str = "adp.com",
    mode: str = "subdomains",
    aggregation: str = "1_per_domain",
    history: str = "live",
) -> list[dict[str, Any]]:
    where = build_where_filter()
    params = {
        "target": target,
        "mode": mode,
        "aggregation": aggregation,
        "history": history,
        "where": json.dumps(where, separators=(",", ":")),
        "select": "url_from,root_name_source,domain_rating_source,traffic_domain,title",
        "order_by": "domain_rating_source:desc",
        "limit": str(limit),
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else ""
        raise SystemExit(f"Ahrefs API error {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed: {exc.reason}") from exc

    payload = json.loads(body)
    if "error" in payload and payload.get("error"):
        raise SystemExit(f"Ahrefs API returned error: {payload['error']}")
    return payload.get("backlinks") or []


def rows_for_csv(backlinks: list[dict[str, Any]], vendor: str = "adp_workforcenow") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in backlinks:
        rows.append(
            {
                "company_domain": item.get("root_name_source") or "",
                "vendor": vendor,
                "url_from": item.get("url_from") or "",
                "domain_rating_source": item.get("domain_rating_source", ""),
                "traffic_domain": item.get("traffic_domain", ""),
                "title": item.get("title") or "",
            }
        )
    return rows


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export ADP Workforce Now backlink leads from Ahrefs to CSV.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max companies to fetch (default: 5 for cheap test runs)",
    )
    parser.add_argument(
        "--output",
        default="adp_workforcenow_leads.csv",
        help="Output CSV path (default: adp_workforcenow_leads.csv)",
    )
    parser.add_argument(
        "--history",
        default="live",
        choices=("live", "all_time"),
        help="Backlink history scope (default: live)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("AHREFS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set AHREFS_API_KEY in your environment.")

    print(f"Fetching up to {args.limit} domains (ordered by domain_rating_source desc)...")
    backlinks = fetch_backlinks(api_key, limit=args.limit, history=args.history)
    rows = rows_for_csv(backlinks)
    write_csv(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
