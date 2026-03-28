#!/usr/bin/env python3
"""Parse modules.html and add any modules not already in cache.json."""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from oumodulesbot.make_cache import dump_readable_json

CACHE_FILE = Path(__file__).parent.parent / "cache.json"
HTML_FILE = Path(__file__).parent.parent / "modules.html"


def parse_modules_html():
    with open(HTML_FILE) as f:
        soup = BeautifulSoup(f, "html.parser")

    modules = {}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not re.search(r"/courses/modules/[a-z]", href):
            continue
        code = href.rstrip("/").split("/")[-1].upper()
        title = link.get("aria-label", "").strip()
        if not title:
            continue
        modules[code] = [title, href]

    return modules


def main():
    with open(CACHE_FILE) as f:
        cache = json.load(f)

    html_modules = parse_modules_html()
    new_modules = {k: v for k, v in html_modules.items() if k not in cache}

    if not new_modules:
        print("No new modules found.")
        return

    for code, (title, url) in sorted(new_modules.items()):
        cache[code] = [title, url]
        print(f"Added {code}: {title} ({url})")

    with open(CACHE_FILE, "w") as f:
        f.write(dump_readable_json(cache))

    print(f"\nAdded {len(new_modules)} module(s) to cache.json.")


if __name__ == "__main__":
    main()
