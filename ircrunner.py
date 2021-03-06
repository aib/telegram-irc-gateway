import logging
_logger = logging.getLogger(__name__)

import base64
import socket
import ssl
import threading
import time

class NoNicksLeft(Exception):
	pass

class DisconnectAndRetry(Exception):
	pass

class IRCRunner:
	CONFIG_SECTION = 'irc'
	HOSTNAME = b'hostname'
	SERVERNAME = b'servername'

	def __init__(self, config):
		self.config = config
		self.socket = None
		self.recv_buffer = b''
		self.nicks = self.get_config('nicks').split()
		self.nick_index = None
		self.channels = self.get_config('channels').split()
		self.telegram_messager = None
		self.irc_ready = threading.Event()

	def get_config(self, name, default=None):
		return self.config.get(self.CONFIG_SECTION, name, fallback=default)

	def set_config(self, name, value):
		self.config.set(self.CONFIG_SECTION, name, value)
		self.config.save()

	def set_telegram_messager(self, telegram_messager):
		self.telegram_messager = telegram_messager

	def recvline(self):
		while b'\n' not in self.recv_buffer:
			self.recv_buffer += self.socket.recv()

		(line, self.recv_buffer) = self.recv_buffer.split(b'\n', 1)
		_logger.debug("<- %s", line)
		return line

	def sendline(self, line):
		_logger.debug("-> %s", line)
		self.socket.send(line + b'\n')

	def forward_message(self, message):
		self.irc_ready.wait()
		for channel in self.channels:
			self.sendline(b'PRIVMSG %s :%s' % (channel.encode('ascii'), message.encode('utf-8')))

	def irc_send_user(self):
		self.sendline(b'USER %s %s %s :%s' %
			(self.get_config('username').encode('ascii'), self.HOSTNAME, self.SERVERNAME, self.get_config('realname').encode('ascii')))

	def irc_send_next_nick(self):
		if self.nick_index is None:
			self.nick_index = 0
		else:
			self.nick_index += 1

		if self.nick_index >= len(self.nicks):
			raise NoNicksLeft

		nick = self.nicks[self.nick_index]
		_logger.info("Using nickname %s", nick)
		self.sendline(b'NICK %s' % nick.encode('ascii'))

	def irc_send_authenticate(self):
		auth = base64.b64encode(b'%s\0%s\0%s' % (
			self.get_config('sasl_username').encode('utf-8'),
			self.get_config('sasl_username').encode('utf-8'),
			self.get_config('sasl_password').encode('utf-8')
		))
		self.sendline(b'AUTHENTICATE %s' % (auth,))

	def irc_start_session(self):
		self.irc_ready.set()
		_logger.info("IRC session started")
		for channel in self.channels:
			self.sendline(b'JOIN %s' % (channel.encode('ascii')))

	def run(self):
		_logger.info("IRCRunner running")

		while True:
			try:
				ssl_context = ssl.create_default_context()

				(server, port) = (self.get_config('server'), int(self.get_config('port')))
				_logger.info("Connecting to %s:%d", server, port)

				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket = ssl_context.wrap_socket(s, server_hostname=server)
				self.socket.connect((server, port))

				_logger.debug("Connected")

				self.sendline(b'CAP REQ :sasl')
				self.irc_send_next_nick()
				self.irc_send_user()

				while True:
					msg = self.recvline()
					self.process_message(msg)

			except DisconnectAndRetry:
				self.socket.close()

			except Exception as e:
				_logger.error("Exception:", exc_info=e)
				self.socket.close()

			self.irc_ready.clear()
			reconnect_delay = int(self.get_config('reconnect_delay'))
			_logger.warn("Disconnected. Waiting %d seconds and trying again.", reconnect_delay)
			time.sleep(reconnect_delay)

	def process_message(self, message):
		if message.startswith(b':'):
			(prefix, command, params) = message.split(maxsplit=2)
			prefix = prefix.decode('ascii')
		else:
			prefix = None
			(command, params) = message.split(maxsplit=1)

		command = command.decode('ascii')

		if command.startswith('4') or command.startswith('5'):
			_logger.warning("Server error: %s %s", command, params)

		if command == 'AUTHENTICATE' and params.strip() == b'+':
			self.irc_send_authenticate()

		if command == 'CAP':
			(client_id, reply) = params.split(maxsplit=1)
			rs = reply.split()
			if rs[0] == b'ACK' and rs[1] == b':sasl':
				self.sendline(b'AUTHENTICATE PLAIN')

		if command == 'PING':
			self.sendline(b'PONG ' + params)

		if command == 'PRIVMSG':
			(target, msg) = params.split(maxsplit=1)
			if target.decode('ascii') in self.channels:
				if self.telegram_messager is not None:
					msg = msg[1:].decode('utf-8', errors='replace')
					nick = prefix[1:].split('!', 1)[0]
					message = "<%s@irc> %s" % (nick, msg)
					self.telegram_messager(message)

		if command == '433': # nick in use
			self.irc_send_next_nick()
			return

		if command in ['372', '375']: # MOTD stuff we can ignore
			return

		if command in ['376', '422']: # end of MOTD or no MOTD, we're connected
			self.irc_start_session()
			return

		if command in ['900', '901']: # [SASL] logged in/out
			return

		if command == '903': # SASL successful
			self.sendline(b'CAP END')

		if command in ['904', '905']: # SASL failed
			_logger.error("SASL authentication failed")
			raise DisconnectAndRetry()
