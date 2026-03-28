import re
from collections import namedtuple
from typing import Iterable

Result = namedtuple("Result", "code,title,url")


MODULE_CODE_RE_TEMPLATE = r"[a-zA-Z]{1,6}[0-9]{3}(?:-[a-zA-Z]{1,5})?"
# QD = Open Degree:
QUALIFICATION_CODE_RE_TEMPLATE = (
    r"[a-zA-Z][0-9]{2}(?:-[a-zA-Z]{1,5})?|[qQ][dD]"
)
QUALIFICATION_CODE_RE = re.compile(rf"^({QUALIFICATION_CODE_RE_TEMPLATE})$")
MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE = (
    rf"(?:{MODULE_CODE_RE_TEMPLATE}|{QUALIFICATION_CODE_RE_TEMPLATE})"
)


def get_possible_qualification_urls(code: str) -> Iterable[str]:
    return [
        f"http://www.open.ac.uk/courses/qualifications/{code}",
        f"http://www.open.ac.uk/postgraduate/qualifications/{code}",
    ]


def get_module_level(module_code: str) -> int:
    for c in module_code:
        if c.isdigit():
            return int(c)
    raise ValueError(f"Invalid module code: {module_code}")


def get_module_urls(module_code: str) -> Iterable[str]:
    if get_module_level(module_code) == 0:
        templates = ["http://www.open.ac.uk/courses/short-courses/{}"]
    elif get_module_level(module_code) == 8:
        templates = ["http://www.open.ac.uk/postgraduate/modules/{}"]
    else:
        templates = [
            "http://www.open.ac.uk/courses/qualifications/details/{}",
            "http://www.open.ac.uk/courses/modules/{}",
        ]
    return [template.format(module_code.lower()) for template in templates]


def get_possible_urls_from_code(code: str) -> Iterable[str]:
    code = code.lower()
    if QUALIFICATION_CODE_RE.match(code):
        return get_possible_qualification_urls(code)
    return get_module_urls(code)
