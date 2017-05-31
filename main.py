#!/usr/bin/env python3

import logging
logging.basicConfig(level=1)
_logger = logging.getLogger(__name__)

import configparser
import threading
import time

import ircrunner
import tgrunner

class MyConfigParser(configparser.ConfigParser):
	def __init__(self, filename, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._filename = filename
		_logger.info("Using configuration file %s", filename)
		self.read(filename)

	def save(self):
		_logger.debug("Saving configuration")

def main():
	conf = MyConfigParser('config.cfg')
	tgr = tgrunner.TGRunner(conf)
	ircr = ircrunner.IRCRunner(conf)

	tgr.set_irc_messager(ircr.forward_message)
	ircr.set_telegram_messager(tgr.forward_message)

	_logger.debug("Starting TGRunner thread")
	threading.Thread(target=tgr.run).start()

	_logger.debug("Starting IRCRunner thread")
	threading.Thread(target=ircr.run).start()

	while True:
		time.sleep(1)

if __name__ == '__main__':
	main()
