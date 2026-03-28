import asyncio
import json

from oumodulesbot.ou_sparql_utils import (
    is_really_active,
    query_oldcourses,
    query_xcri,
)

PAGES = 165


def dump_readable_json(dictionary):
    res = ["{"]
    comma = ""  # print comma after first module
    for k, v in sorted(dictionary.items()):
        res.append(
            "%s %s" % (comma or " ", json.dumps({k: [v[0], v[1]]})[1:-1])
        )
        comma = ","
    res.append("}")
    return "\n".join(res + [""])


async def main():
    results_xcri = await query_xcri()
    results_oldcourses = await query_oldcourses()
    oldcache = json.load(open("cache.json"))

    seen_codes = set()

    for c in results_oldcourses + results_xcri:
        code, title, url = c["id"], c["title"], c.get("url")
        seen_codes.add(code)
        if oldcache.get(code, ["", url])[1] != url:
            print(
                '"url" value different:',
                code,
                oldcache[code][1],
                url,
            )
            if not url:
                # Assume that API correctly returns inactive courses.
                print(
                    '"url" value mismatch:',
                    code,
                    oldcache[code][1],
                    url,
                    " - updating.",
                )
                oldcache[code][1] = None
            elif is_really_active(url, code):
                # However, some of the newcourses are in fact not active, so
                # we need the is_really_active check here.
                print(
                    '"url" value mismatch:',
                    code,
                    oldcache[code][1],
                    url,
                    " - updating.",
                )
                oldcache[code] = [title, url]
        elif oldcache.get(code, [title])[0] != title:
            print(
                '"title" value mismatch: ',
                oldcache[code][0],
                "!=",
                title,
                " - updating.",
            )
            oldcache[code] = (
                title,
                is_really_active(url, code) and url,
            )
        elif oldcache.get(code) != [title, url]:
            print(
                code,
                oldcache.get(code),
                [title, url],
                "mismatch - updating",
            )
            oldcache[code] = (title, is_really_active(url, code) and url)

    for code in oldcache:
        _, url = oldcache[code]
        if code in seen_codes or not url:
            continue
        # process unseen which have url set, which may be still valid
        print(code, "missing - trying old url", url)
        if not is_really_active(url, code):
            print(code, "cached url failed - setting null")
            oldcache[code][1] = None

    with open("newcache.json", "w") as f:
        f.write(dump_readable_json(oldcache))
    return

    # old scraping below, disabled for now:
    """print("[")
    regex = re.compile(
        r'<a href="/library/digital-archive/xcri:([a-zA-Z]{1,3}[0-9]{1,3})">'
        "(?!\1)(.+?)</a>"
    )
    comma = ""  # print comma after first module
    for i in range(1, PAGES + 1):
        print("Processing page {}/{}...".format(i, PAGES), file=sys.stderr)
        url_template = (
            "http://www.open.ac.uk/library/digital-archive/module/list/page{}"
        )
        html = httpx.get(url_template.format(i)).content
        for (code, module) in regex.findall(html):
            try_url = "http://www.open.ac.uk/courses/modules/{}".format(
                code.lower()
            )
            found = httpx.head(try_url).status_code == 200
            print(
                '%s {"%s": ["%s", %s]}'
                % (comma or " ", code, module, "true" if found else "false",)
            )
            comma = ","
            time.sleep(0.1)
    print("]")"""


if __name__ == "__main__":
    asyncio.run(main())
