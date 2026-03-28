#!/usr/bin/env python3
"""Parse /courses/all/ and add any entries not already in cache.json."""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from oumodulesbot.cli_utils.make_cache import dump_readable_json

CACHE_FILE = Path(__file__).parent.parent / "cache.json"
HTML_FILE = Path(__file__).parent.parent / "qualifications.html"

MODULE_CODE_RE = re.compile(r"^[a-z]{1,6}[0-9]{3}(?:-[a-z]{1,5})?$", re.I)
QUAL_CODE_RE = re.compile(r"([a-z][0-9]{2}(?:-[a-z]{1,5})?|qd)$", re.I)


def parse_all_html():
    with open(HTML_FILE) as f:
        soup = BeautifulSoup(f, "html.parser")

    entries = {}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/courses/" not in href:
            continue
        title = link.get("aria-label", "").strip()
        if not title:
            continue
        slug = href.rstrip("/").split("/")[-1]
        if MODULE_CODE_RE.match(slug):
            code = slug.upper()
        else:
            m = QUAL_CODE_RE.search(slug)
            if not m:
                continue
            code = m.group(1).upper()
        title = re.sub(r"\s*\([A-Z][A-Z0-9]*(?:-[A-Z]{1,5})?\)\s*$", "", title)
        entries[code] = [title, href]

    return entries


def main():
    with open(CACHE_FILE) as f:
        cache = json.load(f)

    html_entries = parse_all_html()
    new_entries = {k: v for k, v in html_entries.items() if k not in cache}

    if not new_entries:
        print("No new entries found.")
        return

    for code, (title, url) in sorted(new_entries.items()):
        cache[code] = [title, url]
        print(f"Added {code}: {title} ({url})")

    with open(CACHE_FILE, "w") as f:
        f.write(dump_readable_json(cache))

    print(f"\nAdded {len(new_entries)} entry/entries to cache.json.")


if __name__ == "__main__":
    main()
