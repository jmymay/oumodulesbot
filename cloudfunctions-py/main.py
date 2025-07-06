import asyncio
import base64
import dataclasses
import json
import logging
import os
import re
from typing import List

import httpx
from flask import Flask, request  # type: ignore
from google.cloud import pubsub_v1  # type: ignore

from oumodulesbot.main import (
    OUModulesBackend,
    OUModulesBot,
    Result,
    claim_message,
)
from oumodulesbot.ou_utils import MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE

MODULE_OR_QUALIFICATION_CODE_RE = re.compile(
    MODULE_OR_QUALIFICATION_CODE_RE_TEMPLATE
)
APPLICATION_ID = 511181619785236500
backend = OUModulesBackend()
pubsub_client = pubsub_v1.PublisherClient()
topic_path = pubsub_client.topic_path("ou-modules-bot", "interactions")

log = logging.getLogger("main")
event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)


def handle_pubsub(data):
    logging.basicConfig(level=logging.INFO)
    decoded = base64.b64decode(data["message"]["data"])
    log.info("Received request: %s", decoded)
    event_loop.run_until_complete(find_modules(json.loads(decoded)))


async def find_modules(data):
    message = data["message"]
    content = message["content"]
    results = []
    calls = []
    codes = MODULE_OR_QUALIFICATION_CODE_RE.findall(content)[
        : OUModulesBot.MODULES_COUNT_LIMIT
    ]
    async with claim_message(
        f'{data["target_id"]}_{data["interaction_id"]}'
    ) as claimed:
        if not claimed:
            # Avoid replying twice by two instances.
            return
        seen = set()
        for code in codes:
            if code in seen:  # Avoid duplicates.
                continue
            seen.add(code)
            calls.append(backend.find_result_for_code(code.upper()))
        for code, result in zip(codes, await asyncio.gather(*calls)):
            if result:
                results.append(result)
            else:
                results.append(Result(code.upper(), "Not found", None))
        response = FoundModules(results).as_response_json(data)
        log.info("Sending response: %s", response)
        result = httpx.patch(
            "https://discord.com/api/v10/webhooks/"
            f"{APPLICATION_ID}/{data['token']}/messages/@original",
            json=response,
        )
        log.info("Result: %s", result.text)


@dataclasses.dataclass
class FoundModules:
    modules_list: List[Result]

    def as_response_json(self, input_data):
        guild_id = input_data["guild_id"]
        channel_id = input_data["message"]["channel_id"]
        target_id = input_data.get("target_id")
        data = {}
        if target_id:
            url = (
                "https://discord.com/channels/"
                f"{guild_id}/{channel_id}/{target_id}"
            )
            data = {
                "components": [
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "style": 5,
                                "label": "Jump to referenced message",
                                "url": url,
                            }
                        ],
                    }
                ],
            }
        if len(self.modules_list) > 1:
            data["content"] = "Multiple results found."
            data["embeds"] = self._multiple_modules_embeds()
        else:
            data["content"] = OUModulesBot.format_result(self.modules_list[0])
        return data

    def _multiple_modules_embeds(self):
        return [
            {
                "fields": [
                    {
                        "name": m.code,
                        "value": OUModulesBot.format_result(m, for_embed=True),
                    }
                    for m in self.modules_list
                ],
            }
        ]


app = Flask(__name__)


@app.route("/", methods=["POST"])
def interaction():
    handle_pubsub(request.get_json())
    return "OK"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
