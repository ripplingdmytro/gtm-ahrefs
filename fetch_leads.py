#!/usr/bin/env python3
"""
Fetch technographic leads from Ahrefs backlinks (one vendor config per run).

Usage:
  python3 fetch_leads.py              # interactive menu
  python3 fetch_leads.py --vendor adp
  python3 fetch_leads.py --list-vendors
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_URL = "https://api.ahrefs.com/v3/site-explorer/all-backlinks"
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
VENDORS_DIR = SCRIPT_DIR / "vendors"
OUT_DIR = SCRIPT_DIR / "out"

# Ahrefs puts the where filter in the request; too many exclude clauses blows the header limit.
AHREFS_URL_FROM_EXCLUDE_CAP = 200

CSV_COLUMNS = (
    "run_id",
    "fetched_at",
    "vendor_slug",
    "company_domain",
    "url_from",
    "url_to",
    "tenant_id",
    "domain_rating_source",
    "traffic_domain",
    "title",
)


def _not_substring(field: str, value: str) -> dict[str, Any]:
    return {"not": {"field": field, "is": ["substring", value]}}


def _load_shared_defaults() -> dict[str, Any]:
    defaults_path = VENDORS_DIR / "_defaults.json"
    if not defaults_path.is_file():
        return {}
    return json.loads(defaults_path.read_text(encoding="utf-8"))


def _icp_referrer_clauses(defaults: dict[str, Any]) -> list[dict[str, Any]]:
    """ICP filters applied to every vendor: no .edu/.gov referrers, shared blocklist."""
    clauses: list[dict[str, Any]] = [
        {"field": "tld_class_source", "is": ["eq", "normal"]},
    ]
    for suffix in defaults.get("root_name_suffix_exclude", []):
        clauses.append(_not_substring("root_name_source", suffix))
    return clauses


def build_where_filter(vendor: dict[str, Any]) -> dict[str, Any]:
    defaults = _load_shared_defaults()
    clauses: list[dict[str, Any]] = [
        *_icp_referrer_clauses(defaults),
        {
            "field": "url_to_plain",
            "is": ["substring", vendor["url_to_contains"]],
        },
        {
            "field": "domain_rating_source",
            "is": ["gte", vendor["domain_rating_min"]],
        },
        {
            "field": "traffic_domain",
            "is": ["gte", vendor["traffic_domain_min"]],
        },
    ]
    for token in vendor.get("url_to_exclude", []):
        clauses.append(_not_substring("url_to_plain", token))
    for token in vendor.get("url_from_exclude", [])[:AHREFS_URL_FROM_EXCLUDE_CAP]:
        clauses.append(_not_substring("url_from_plain", token))
    hints = vendor.get("url_from_require_any")
    if hints is None:
        hints = defaults.get("url_from_require_any", [])
    if hints:
        clauses.append(
            {
                "or": [
                    {"field": "url_from_plain", "is": ["substring", hint]}
                    for hint in hints
                ]
            }
        )
    return {"and": clauses}


def _apply_shared_defaults(vendor: dict[str, Any]) -> dict[str, Any]:
    defaults = _load_shared_defaults()
    merged = list(defaults.get("url_from_exclude", []))
    for token in vendor.get("url_from_exclude", []):
        if token not in merged:
            merged.append(token)
    vendor["url_from_exclude"] = merged
    return vendor


def load_vendor(slug: str) -> dict[str, Any]:
    path = VENDORS_DIR / f"{slug}.json"
    if not path.is_file():
        available = ", ".join(list_vendor_slugs()) or "(none)"
        raise SystemExit(f"Unknown vendor {slug!r}. Available: {available}")
    vendor = json.loads(path.read_text(encoding="utf-8"))
    if vendor.get("vendor_slug") != slug:
        raise SystemExit(
            f"vendor_slug in {path.name} must be {slug!r}, got {vendor.get('vendor_slug')!r}"
        )
    return _apply_shared_defaults(vendor)


def list_vendor_slugs() -> list[str]:
    return sorted(
        p.stem for p in VENDORS_DIR.glob("*.json") if not p.stem.startswith("_")
    )


def vendors_for_menu(slugs: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """Sort vendors for menu: menu_order ascending (1 = largest competitor first)."""
    options = [(slug, load_vendor(slug)) for slug in slugs]
    options.sort(
        key=lambda item: (
            item[1].get("menu_order", 999),
            item[1].get("display_name", item[0]).lower(),
        )
    )
    return options


def _vendor_label(vendor: dict[str, Any], slug: str) -> str:
    return str(vendor.get("display_name") or slug.replace("-", " ").title())


def pick_vendor_interactively(slugs: list[str]) -> str:
    if not slugs:
        raise SystemExit(f"No vendor configs found in {VENDORS_DIR}/")

    options = vendors_for_menu(slugs)

    print()
    print("  Pick a competitor stack to hunt:")
    print()
    for index, (_, cfg) in enumerate(options, start=1):
        print(f"    {index}. {cfg.get('display_name', '')}")
    print()
    print("    0. Cancel")
    print()

    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit("Cancelled.") from None

        if raw == "0":
            raise SystemExit("Cancelled.")
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
        print("  Invalid choice — try again.")


def make_run_id(when: datetime) -> str:
    """Dash-separated id safe for filenames and pipeline keys (no slashes)."""
    return when.strftime("%Y%m%d-%H%M%S")


def default_output_path(vendor_slug: str, run_id: str, when: datetime) -> Path:
    """
    out/{vendor-slug}/{YYYY-MM-DD}/{run-id}.csv

    Slashes are only directory separators. Slug, date, and run_id use dashes.
    """
    date_folder = when.strftime("%Y-%m-%d")
    return OUT_DIR / vendor_slug / date_folder / f"{run_id}.csv"


def load_api_key() -> str:
    key = os.environ.get("AHREFS_API_KEY", "").strip()
    if key:
        return key
    if not ENV_FILE.is_file():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("AHREFS_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def fetch_backlinks(
    api_key: str,
    vendor: dict[str, Any],
    *,
    limit: int,
    history: str,
) -> list[dict[str, Any]]:
    where = build_where_filter(vendor)
    params = {
        "target": vendor["target"],
        "mode": vendor.get("mode", "subdomains"),
        "aggregation": vendor.get("aggregation", "1_per_domain"),
        "history": history,
        "where": json.dumps(where, separators=(",", ":")),
        "select": vendor["select"],
        "order_by": vendor.get("order_by", "domain_rating_source:desc"),
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
    if payload.get("error"):
        raise SystemExit(f"Ahrefs API returned error: {payload['error']}")
    return payload.get("backlinks") or []


def _url_from_blocked(url_from: str, exclude_tokens: list[str]) -> bool:
    plain = url_from.lower()
    return any(token.lower() in plain for token in exclude_tokens)


def filter_rows_by_url_from(
    rows: list[dict[str, Any]], exclude_tokens: list[str]
) -> list[dict[str, Any]]:
    if not exclude_tokens:
        return rows
    return [r for r in rows if not _url_from_blocked(r.get("url_from") or "", exclude_tokens)]


def _url_from_matches_require(url_from: str, require_tokens: list[str]) -> bool:
    if not require_tokens:
        return True
    plain = url_from.lower()
    return any(token.lower() in plain for token in require_tokens)


def filter_rows_by_url_from_require(
    rows: list[dict[str, Any]], require_tokens: list[str]
) -> list[dict[str, Any]]:
    if not require_tokens:
        return rows
    return [
        r
        for r in rows
        if _url_from_matches_require(r.get("url_from") or "", require_tokens)
    ]


def parse_tenant_id(vendor_slug: str, url_to: str) -> str:
    """Best-effort tenant key from vendor portal url (for dedupe downstream)."""
    if not url_to:
        return ""
    if vendor_slug == "workday":
        match = re.search(r"[?&]t=([^&#]+)", url_to, re.I)
        if match:
            return urllib.parse.unquote(match.group(1))
        match = re.search(
            r"https?://([^.]+)\.(?:wd\d+\.)?myworkdayjobs\.com", url_to, re.I
        )
        if match:
            return match.group(1).lower()
        match = re.search(r"myworkday\.com/([^/?#]+)/d/", url_to, re.I)
        if match:
            tenant = match.group(1).lower()
            if tenant not in ("www", "wday", "login", "authgwy") and not re.fullmatch(
                r"wd\d+", tenant
            ):
                return tenant
    elif vendor_slug == "adp":
        match = re.search(r"[?&]cid=([^&#]+)", url_to, re.I)
        if match:
            return urllib.parse.unquote(match.group(1))
    elif vendor_slug == "bamboohr":
        match = re.search(r"https?://([^.]+)\.bamboohr\.com", url_to, re.I)
        if match:
            return match.group(1).lower()
    elif vendor_slug == "gusto":
        match = re.search(r"jobs\.gusto\.com/boards/([^/?#]+)", url_to, re.I)
        if match:
            return match.group(1)
    elif vendor_slug == "deel":
        match = re.search(r"jobs\.deel\.com/([^/?#]+)", url_to, re.I)
        if match:
            return match.group(1)
    return ""


def rows_for_csv(
    backlinks: list[dict[str, Any]],
    *,
    vendor_slug: str,
    run_id: str,
    fetched_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in backlinks:
        url_to = item.get("url_to") or ""
        rows.append(
            {
                "run_id": run_id,
                "fetched_at": fetched_at,
                "vendor_slug": vendor_slug,
                "company_domain": item.get("root_name_source") or "",
                "url_from": item.get("url_from") or "",
                "url_to": url_to,
                "tenant_id": parse_tenant_id(vendor_slug, url_to),
                "domain_rating_source": item.get("domain_rating_source", ""),
                "traffic_domain": item.get("traffic_domain", ""),
                "title": item.get("title") or "",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(vendor_slugs: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export HR vendor backlink leads from Ahrefs to CSV.",
    )
    parser.add_argument(
        "--vendor",
        metavar="SLUG",
        help="Skip menu and use this vendor slug (e.g. adp)",
    )
    parser.add_argument(
        "--list-vendors",
        action="store_true",
        help="List available vendor slugs and exit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max companies to fetch (default: from vendor config)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Override output path (default: out/{vendor}/{date}/{run-id}.csv)",
    )
    parser.add_argument(
        "--history",
        default="live",
        choices=("live", "all_time"),
        help="Backlink history scope (default: live)",
    )
    return parser.parse_args()


def main() -> None:
    vendor_slugs = list_vendor_slugs()
    args = parse_args(vendor_slugs)

    if args.list_vendors:
        for slug, cfg in vendors_for_menu(vendor_slugs):
            print(f"{slug} — {cfg.get('display_name', slug)}")
        return

    vendor_slug = args.vendor or pick_vendor_interactively(vendor_slugs)
    if vendor_slug not in vendor_slugs:
        available = ", ".join(vendor_slugs)
        raise SystemExit(f"Unknown vendor {vendor_slug!r}. Available: {available}")

    vendor = load_vendor(vendor_slug)
    limit = args.limit if args.limit is not None else vendor.get("default_limit", 500)

    api_key = load_api_key()
    if not api_key:
        raise SystemExit(
            f"Add your Ahrefs API key to {ENV_FILE.name} (copy from .env.example)."
        )

    when = datetime.now(timezone.utc)
    run_id = make_run_id(when)
    fetched_at = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    output_path = args.output or default_output_path(vendor_slug, run_id, when)

    label = _vendor_label(vendor, vendor_slug)
    print()
    print(f"  Getting up to {limit} likely {label} customers from Ahrefs…")
    print()
    backlinks = fetch_backlinks(
        api_key, vendor, limit=limit, history=args.history
    )
    rows = rows_for_csv(
        backlinks,
        vendor_slug=vendor_slug,
        run_id=run_id,
        fetched_at=fetched_at,
    )
    defaults = _load_shared_defaults()
    exclude = vendor.get("url_from_exclude", [])
    require = vendor.get("url_from_require_any")
    if require is None:
        require = defaults.get("url_from_require_any", [])

    before = len(rows)
    rows = filter_rows_by_url_from(rows, exclude)
    dropped_block = before - len(rows)
    before = len(rows)
    rows = filter_rows_by_url_from_require(rows, require)
    dropped_require = before - len(rows)

    write_csv(output_path, rows)
    msg = f"  Done — {len(rows)} {label} leads saved to {output_path}"
    parts: list[str] = []
    if dropped_block:
        parts.append(f"{dropped_block} noisy referrers")
    if dropped_require:
        parts.append(f"{dropped_require} non-careers pages")
    if parts:
        msg += f" ({', '.join(parts)} filtered out)"
    print()
    print(msg)
    print()


if __name__ == "__main__":
    main()
