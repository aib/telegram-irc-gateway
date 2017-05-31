import logging
_logger = logging.getLogger(__name__)

import telegram

class TGRunner:
	CONFIG_SECTION = 'telegram'

	def __init__(self, config):
		self.config = config
		self.groups = self.get_config('groups').split()
		self.irc_messager = None

	def get_config(self, name, default=None):
		return self.config.get(self.CONFIG_SECTION, name, fallback=default)

	def set_config(self, name, value):
		self.config.set(self.CONFIG_SECTION, name, value)
		self.config.save()

	def set_irc_messager(self, irc_messager):
		self.irc_messager = irc_messager

	def send_message(self, message):
		_logger.debug("-> sendMessage %s", message)
		telegram.makeRequest(self.get_config('token'), 'sendMessage', message)

	def forward_message(self, message):
		for group in self.groups:
			self.send_message({ 'chat_id': int(group), 'text': message })

	def run(self):
		_logger.info("TGRunner running, bot token is %s", self.get_config('token'))
		last_update_id = 0
		while True:
			_logger.debug("Looking for updates >= %d", last_update_id)
			update = telegram.getOneUpdate(self.get_config('token'), last_update_id)
			_logger.debug("<- %s", update)
			last_update_id = update['update_id'] + 1
			self.process_update(update)

	def process_update(self, update):
		if 'message' in update:
			message = update['message']
			chat = message['chat']

			if chat['type'] in ['group', 'supergroup']:
				if str(chat['id']) in self.groups:
					if self.irc_messager is not None:
						msg = "<%s@tg> %s" % (message['from']['username'], message['text'])
						self.irc_messager(msg)
