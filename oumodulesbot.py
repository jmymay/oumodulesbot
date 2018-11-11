import json
import logging
import os
import re

from disco.api.client import APIClient
from disco.api.http import Routes
from disco.client import ClientConfig,  Client
from disco.bot import Plugin, BotConfig, Bot
from disco.types.message import MessageEmbed, Message
import requests
import pylru
from gevent import monkey

monkey.patch_all()

embeds_cache = pylru.lrucache(1000)

COMMAND_NAME = 'modulename'

class OUModulesBotPlugin(Plugin):

    MODULE_RE = re.compile(
        r'<title>[a-zA-Z]{1,3}[0-9]{1,3} (.*) - Open University Digital Archive</title>'
    )

    EMBED_RE = re.compile(r'![a-zA-Z]{1,3}[0-9]{1,3}')
    MODULES_COUNT_LIMIT = 5

    @property
    def api_client(self):
        if getattr(self, '_api_client', None):
            return self._api_client
        self._api_client = APIClient(self.client.config.token, self.client)
        return self._api_client

    def get_module_title(self, code):
        try:
            html = requests.get(
                'http://www.open.ac.uk/library/digital-archive/module/xcri:{}'.format(code)
            ).content
        except Exception as e:
            return
        title = self.MODULE_RE.findall(html)
        return title[0] if title else None

    def command_modulename(self, event, message):
        codes = message.content.split()[1:]
        modules = []
        any_found = False
        for code in codes[:self.MODULES_COUNT_LIMIT]:
            replies = []
            code = code.upper().replace('!', '')
            if code.isalnum() and 4 <= len(code) <= 6:
                title = self.get_module_title(code)
                if title:
                    any_found = True
                    modules.append((code, title))
                else:
                    replies.append((code, 'not found'))
        if any_found or len(codes) == 1:
            # don't spam just to say multiple not found
            self.post_modules(event, message, modules)

    @Plugin.listen('MessageUpdate')
    def on_message_update(self, event):
        if not event.message.content:
            return
        expression = "!{}".format(COMMAND_NAME)
        if event.message.content.startswith(expression):
            self.command_modulename(
                event,
                event.message
            )
        else:
            self.do_embeds(event)

    def do_embeds(self, event):
        message = getattr(event, 'msg', None) or event.message
        if not message.content:
            return
        if message.content.startswith("!{}".format(COMMAND_NAME)):
            self.command_modulename(event, message)
            return
        modules = []
        any_found = False
        for module in self.EMBED_RE.findall(event.message.content)[:self.MODULES_COUNT_LIMIT]:
            title = self.get_module_title(module[1:])
            if title:
                any_found = True
                modules.append((module[1:].upper(), title))
        if any_found:
            # don't spam unless we're sure we at least foudn some modules to return
            # (different from 'command' mode, where we always reply if there's just one module)
            self.post_modules(event, message, modules)

    def post_modules(self, event, reply_to, modules):
        modify_c = None
        if event.message.id in embeds_cache:
            modify_c, modify_m = embeds_cache[event.message.id]

        embed = MessageEmbed()
        if len(modules) > 1:
            content = ''
            for (code, title) in modules:
                embed.add_field(name=code, value=' * {} '.format(title), inline=True)
        else:
            code, title = modules[0]
            content = '{}: {}'.format(code, title)

        if modify_c:
            self.api_client.channels_messages_modify(modify_c.id, modify_m.id, content, embed=embed or {})
        else:
            embeds_cache[reply_to.id] = (
                event.channel,
                reply_to.reply(content, embed=embed if len(modules) > 1 else None)
            )


    @Plugin.listen('MessageCreate')
    def on_message_create(self, event):
        self.do_embeds(event)

def main():
    logging.basicConfig(level='INFO')
    client_config = ClientConfig()
    client_config.token = os.getenv('OU_BOT_TOKEN')
    if not client_config.token:
        with open('config.json', 'r') as f:
            client_config.token = json.load(f)['token']
    bot_config = BotConfig()
    bot_config.plugins = ['oumodulesbot']
    bot_config.commands_require_mention = False
    client = Client(client_config)
    bot = Bot(client, bot_config)
    bot.run_forever()

if __name__ == '__main__':
    main()
