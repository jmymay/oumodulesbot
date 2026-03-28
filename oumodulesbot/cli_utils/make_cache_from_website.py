import json
import re
import sys

import httpx
from bs4 import BeautifulSoup  # type: ignore

from oumodulesbot.make_cache import dump_readable_json
from oumodulesbot.ou_utils import MODULE_CODE_RE_TEMPLATE

MODULE_RE = re.compile(
    rf"([A-Z](?:.(?!{MODULE_CODE_RE_TEMPLATE}))+)"
    rf" \(({MODULE_CODE_RE_TEMPLATE})\)"
)


def find_codes(s: str):
    bs = BeautifulSoup(s, "html.parser")
    text = bs.get_text()
    for match in MODULE_RE.finditer(text):
        yield match.group(2), match.group(1)


def main():
    oldcache = json.load(open("cache.json"))
    for code, name in find_codes(httpx.get(sys.argv[1]).text):
        if code not in oldcache:
            oldcache[code] = [name, sys.argv[1]]
        else:
            # Repeated modules
            oldcache[code] = [
                name,
                "https://info1.open.ac.uk/digital-apprenticeship-resources",
            ]
    with open("newcache.json", "w") as f:
        f.write(dump_readable_json(oldcache))


if __name__ == "__main__":
    main()
