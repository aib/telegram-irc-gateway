import logging
_logger = logging.getLogger(__name__)

import socket
import ssl

class NoNicksLeft(Exception):
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

	def get_config(self, name, default=None):
		return self.config.get(self.CONFIG_SECTION, name, fallback=default)

	def set_config(self, name, value):
		self.config.set(self.CONFIG_SECTION, name, value)
		self.config.save()

	def recvline(self):
		while b'\n' not in self.recv_buffer:
			self.recv_buffer += self.socket.recv()

		(line, self.recv_buffer) = self.recv_buffer.split(b'\n', 1)
		_logger.debug("<- %s", line)
		return line

	def sendline(self, line):
		_logger.debug("-> %s", line)
		self.socket.send(line + b'\n')

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

	def run(self):
		_logger.info("IRCRunner running")

		while True:
			ssl_context = ssl.SSLContext()
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket = ssl_context.wrap_socket(s)

			(server, port) = (self.get_config('server'), int(self.get_config('port')))
			_logger.info("Connecting to %s:%d", server, port)
			self.socket.connect((server, port))

			_logger.debug("Connected")

			self.irc_send_next_nick()
			self.irc_send_user()

			while True:
				msg = self.recvline()
				self.process_message(msg)

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

		if command == 'PING':
			self.sendline(b"PONG " + params)

		if command == '433': # nick in use
			self.irc_send_next_nick()
			return

		if command in ['372', '375']: # MOTD stuff we can ignore
			return

		if command in ['376', '422']: # end of MOTD or no MOTD, we're connected
			return
