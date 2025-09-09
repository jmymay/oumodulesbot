import json
from collections import namedtuple
from unittest import mock

import discord
import pytest

from oumodulesbot.main import OUModulesBot

pytestmark = pytest.mark.asyncio


QUALIFICATION_URL_TPL = "http://www.open.ac.uk/courses/qualifications/{code}"
RESPONSE_SUFFIX = (
    "\nNote: !codes are being retired. Please use /oulookup, or skip !"
    " and right-click/long-touch a message → Apps → OU Lookup."
)


@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    def mock_load(f):
        return {
            "A123": ["Mocked active module", "fake_url1"],
            "A012": ["Mocked active short course", "fake_url2"],
            "A888": ["Mocked active postgrad module", "fake_url3"],
            "B321": ["Mocked inactive module", None],
            "B31": ["Mocked inactive-actually-active qualification", None],
        }

    monkeypatch.setattr(json, "load", mock_load)


ModuleExample = namedtuple("ModuleExample", "code,active,result")
E2E_EXAMPLES = [
    ModuleExample(
        "A123",
        True,
        "A123: [Mocked active module](<fake_url1>)" + RESPONSE_SUFFIX,
    ),
    ModuleExample(
        "B321",
        False,
        "B321: Mocked inactive module" + RESPONSE_SUFFIX,
    ),
    ModuleExample(
        "B31",
        False,
        "B31: [Mocked inactive-actually-active qualification](<{url}>)".format(
            url=QUALIFICATION_URL_TPL.format(code="b31")
        )
        + RESPONSE_SUFFIX,
    ),
    ModuleExample(
        "A012",
        True,
        "A012: [Mocked active short course](<fake_url2>)" + RESPONSE_SUFFIX,
    ),
    ModuleExample(
        "A888",
        True,
        "A888: [Mocked active postgrad module](<fake_url3>)" + RESPONSE_SUFFIX,
    ),
]


def create_mock_message(contents, send_result="foo", id_override=None):
    message = mock.Mock(spec=discord.Message)
    message.content = contents
    message.reply = mock.AsyncMock()
    message.reply.return_value = send_result
    message.id = id_override or contents
    return message


async def process_message(bot, message, result, client_mock):
    """
    Pass the message to the bot, optionally verifying that appropriate checks
    are made for inactive modules.
    """
    if "actually-active" in result.result:
        client_mock.get.return_value.status_code = 200
        client_mock.get.return_value.url = QUALIFICATION_URL_TPL.format(
            code=result.code.lower()
        )
    await bot.on_message(message)
    if not result.active:
        code = result.code.lower()
        # inactive results are double-checked with http to provide a link
        # in case the inactive cache.json status is no longer valid:
        if "qualification" not in result.result:
            prefix = "http://www.open.ac.uk/courses"
            urls = [
                f"{prefix}/qualifications/details/{code}",
                f"{prefix}/modules/{code}",
            ]
        else:
            urls = [QUALIFICATION_URL_TPL.format(code=code)]
        client_mock.assert_has_calls(
            [
                mock.call.get(url, follow_redirects=True, timeout=3)
                for url in urls
            ],
            any_order=True,
        )


@pytest.mark.parametrize("module", E2E_EXAMPLES)
async def test_end_to_end_create(module):
    """
    Basic test to make sure matching modules are processed correctly.

    Runs with each example from E2E_EXAMPLES independently.
    """
    bot = OUModulesBot()
    message = create_mock_message(f"foo !{module.code}")
    with mock.patch(
        "httpx.AsyncClient", autospec=True, spec_set=True
    ) as client_class_mock:
        await process_message(
            bot,
            message,
            module,
            client_class_mock.return_value.__aenter__.return_value,
        )
    message.reply.assert_called_once_with(module.result, embeds=[])


async def test_end_to_end_update():
    """
    Ensure `message.edit` on the original reply is called, instead of
    `channel.send`, if the triggering message is edited, as opposed to new.

    Processes E2E_EXAMPLES sequentially with a single bot instance.
    First message is the first example, which is subsequently edited
    by replacing its contents with further examples.
    """
    first_post, updates = E2E_EXAMPLES[0], E2E_EXAMPLES[1:]
    bot = OUModulesBot()
    result_message = mock.Mock(spec=discord.Message)
    message = create_mock_message(
        f"foo !{first_post.code}",
        # result_message is our bot's response here:
        send_result=result_message,
        # the id must be the same to trigger `edit`:
        id_override="original_id",
    )
    with mock.patch(
        "httpx.AsyncClient", autospec=True, spec_set=True
    ) as client_class_mock:
        await process_message(
            bot,
            message,
            first_post,
            client_class_mock.return_value.__aenter__.return_value,
        )

    for update in updates:
        update_message = create_mock_message(
            f"foo !{update.code}",
            id_override="original_id",
        )
        with mock.patch(
            "httpx.AsyncClient", autospec=True, spec_set=True
        ) as client_class_mock:
            await process_message(
                bot,
                update_message,
                update,
                client_class_mock.return_value.__aenter__.return_value,
            )
        # verify that the bot's response is updated:
        result_message.edit.assert_called_once_with(
            content=update.result, embeds=[]
        )
        result_message.edit.reset_mock()


@mock.patch("httpx.AsyncClient", autospec=True, spec_set=True)
async def test_end_to_end_missing_module(client_class_mock):
    client_mock = client_class_mock.return_value.__aenter__.return_value
    bot = OUModulesBot()
    fake_module = ModuleExample(
        "XYZ999", False, "XYZ999: Some Random Module" + RESPONSE_SUFFIX
    )
    message = create_mock_message(f"foo !{fake_module.code}")
    expected_url = (
        "http://www.open.ac.uk/library/digital-archive/module/"
        f"xcri:{fake_module.code}"
    )

    # return matching data from httpx:
    client_mock.get.side_effect = lambda url, **kw: {
        expected_url: mock.Mock(
            # OUDA HTML:
            content=(
                "not really html but matches the regex:"
                f"<title>{fake_module.code} Some Random Module"
                " - Open University Digital Archive</title>"
            ).encode(),
        )
    }.get(
        url,
        mock.Mock(
            # Empty SPARQL:
            json=lambda: {"results": {"bindings": []}},
        ),
    )

    # ensure module name is returned to Discord:
    await process_message(bot, message, fake_module, client_mock)
    message.reply.assert_called_once_with(fake_module.result, embeds=[])

    # ensure httpx was called with appropriate URL:
    client_mock.get.assert_any_call(
        # ignore SPARQL calls
        expected_url
    )
