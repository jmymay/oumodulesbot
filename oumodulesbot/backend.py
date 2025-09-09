import asyncio
import importlib
import json
import logging
import re
from typing import Dict, Optional, Tuple

import httpx

import oumodulesbot
from oumodulesbot.ou_sparql_utils import find_module_or_qualification
from oumodulesbot.ou_utils import (
    MODULE_CODE_RE_TEMPLATE,
    MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE,
    Result,
    get_possible_urls_from_code,
)

MODULE_TITLE_OUDA_RE = re.compile(
    r"<title>" + MODULE_CODE_RE_TEMPLATE + r" (.*?)"
    r" - Open University Digital Archive</title>"
)
OUDA_URL_TEMPLATE = (
    "http://www.open.ac.uk/library/digital-archive/module/xcri:{}"
)


TITLE_SEPARATOR = r"[^\s]"
MAX_MODULE_NAME_LEN = 100
MODULE_NAME_RE = rf"[A-Z][a-zA-Z0-9,.:;\(\) \-]{{1,{MAX_MODULE_NAME_LEN}}}?"

HTML_TITLE_TEXT_RE_TEMPLATES = (
    (
        rf"{MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE}"
        rf"\s*{TITLE_SEPARATOR}\s*(?P<name>{MODULE_NAME_RE})\s*"
        # the trailing '.*' allows ' Course' after 'Open University':
        rf"({TITLE_SEPARATOR}\s*Open University.*)?"
    ),
    (
        rf"(?P<name>{MODULE_NAME_RE})"
        # the trailing '.*' allows ' Course' after 'Open University':
        rf"\s*({TITLE_SEPARATOR}\s*Open University.*)?\s*"
        rf"{TITLE_SEPARATOR}\s{MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE}"
    ),
)
HTML_TITLE_TAG_RES = [
    re.compile(rf"<title>\s*(?:{title_template})\s*</title>")
    for title_template in HTML_TITLE_TEXT_RE_TEMPLATES
]


logger = logging.getLogger(__name__)

CacheItem = Tuple[str, Optional[str]]  # title, url


def find_title_in_html(html: str) -> Optional[str]:
    for regex in HTML_TITLE_TAG_RES:
        if found := regex.search(html):
            return found.group("name")
    return None


def make_client():
    headers = {
        "User-Agent": (
            "ou-modules-bot / 0.0.0 (https://modules-bot.ou-stem.club/)"
        )
    }
    return httpx.AsyncClient(headers=headers)


def get_cache_json() -> dict[str, list[str | None]]:
    cache_file = importlib.resources.files(oumodulesbot) / "cache.json"
    return json.load(cache_file.open("r"))


class OUModulesBackend:
    def __init__(self):
        self.cache: Dict[str, CacheItem] = {
            k: tuple(v) for k, v in get_cache_json().items()
        }

    async def _try_cache(self, code) -> Optional[Result]:
        if code not in self.cache:
            logger.info(f"{code} not in cache")
            return None
        cached_result = self.cache[code]
        title = cached_result[0]
        url = cached_result[1]
        # try to make sure URL really isn't reachable, by autogenerating one:
        if (not url) and (response := await self._get_if_active(code)):
            url = str(response.url)
            logger.info(f"{code} has no url in cache, but {url} is reachable")
            self.cache[code] = (title, url)
        return Result(code, title, url)

    async def _try_url(self, code) -> Optional[Result]:
        if response := await self._get_if_active(code):
            if found_title := find_title_in_html(response.text):
                logger.info(f"{code} found via {response.url}")
                return Result(code, found_title, response.url)
        logger.info(f"{code} can't be found via module URL")
        return None

    async def _try_ouda(self, code) -> Optional[Result]:
        ouda_url = OUDA_URL_TEMPLATE.format(code)
        try:
            logger.info(f"Trying {ouda_url}")
            async with make_client() as client:
                try:
                    response = await client.get(ouda_url)
                except httpx.ReadTimeout:
                    logger.warning("OUDA timeout")
                    return None
            html = response.content.decode("utf-8")
        except Exception:
            logger.exception(f"Failed fetching {ouda_url}")
            return None

        if titles := MODULE_TITLE_OUDA_RE.findall(html):
            logger.info(f"{code} found via OUDA")
            return Result(code, titles[0], None)
        logger.info(f"{code} can't be found via {ouda_url}")
        return None

    async def find_result_for_code(self, code: str) -> Optional[Result]:
        """
        Returns a module title for given code, if available.

        Tries a lookup in cache, and if it fails then it attempts to query
        the Open University Digital Archive.
        """
        code = code.upper()

        # 1. Try cached title:
        if cached_result := await self._try_cache(code):
            return cached_result

        async with asyncio.TaskGroup() as tg:  # type: ignore
            unfinished = {
                # 2. Try SPARQL queries:
                tg.create_task(find_module_or_qualification(code)),
                # 3. Try scraping URL with HTML description
                #    (some results used to be missing from SPARQL results):
                tg.create_task(self._try_url(code)),
                # 4. Try OUDA for old modules:
                tg.create_task(self._try_ouda(code)),
            }

            while unfinished:
                finished, unfinished = await asyncio.wait(
                    unfinished, return_when=asyncio.FIRST_COMPLETED
                )
                for task in finished:
                    result = task.result()
                    if isinstance(result, Exception):
                        continue
                    if result:
                        for task in unfinished:
                            task.cancel()
                        self.cache[code] = (result.title, result.url)
                        return result

        return result

    async def _is_active_url(
        self, url: str, code: str
    ) -> tuple[bool, httpx.Response | None]:
        """
        Check if given URL looks like a valid URL for a given code, i.e.
        resolves to 200, and doesn't redirect away to a different page.

        OU used to redirect to places like /courses/ sometimes which was
        a masked way of saying '404'. However 301 redirects don't always
        indicate that modules aren't available, because they sometimes point
        to a different page for the same module/qualification.

        Thus a compromise is used here by allowing redirects, but only if the
        destination page URL includes the module code.
        """
        async with make_client() as client:
            try:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=3,
                )
            except httpx.ReadTimeout:
                logger.warning("_is_active_url timeout")
                return False, None
            correct_redirect = code.lower() in str(response.url).lower()
            if correct_redirect and response.status_code == 200:
                return True, response
            else:
                logger.warning(
                    f"URL {url} for {code} gave "
                    f"{response.status_code} at {response.url}"
                )
                return False, None

    async def _get_if_active(self, code: str) -> Optional[httpx.Response]:
        """
        Return module's URL for given uncached module code, if available.

        Tries to provide a validated Response using well-known template URLs
        (see get_module_url from ou_utils).
        """
        # 1. Try constructing it from code
        for try_url in get_possible_urls_from_code(code):
            active, response = await self._is_active_url(try_url, code)
            if active:
                return response

        return None
