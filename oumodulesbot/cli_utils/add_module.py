#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from oumodulesbot.cli_utils.make_cache import dump_readable_json

CACHE_FILE = Path(__file__).parent.parent / "cache.json"


def main():
    parser = argparse.ArgumentParser(description="Add a module to cache.json")
    parser.add_argument("code", help="Module code (e.g. A111)")
    parser.add_argument("title", help="Module title")
    parser.add_argument("url", help="Module URL (use 'null' for no URL)")
    args = parser.parse_args()

    url = None if args.url.lower() == "null" else args.url

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    cache[args.code] = [args.title, url]

    with open(CACHE_FILE, "w") as f:
        f.write(dump_readable_json(cache))

    print(f"Added {args.code}: {args.title} ({url})")


if __name__ == "__main__":
    main()
