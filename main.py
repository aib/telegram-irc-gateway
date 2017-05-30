#!/usr/bin/env python3

import logging
logging.basicConfig(level=1)
_logger = logging.getLogger(__name__)

import configparser

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

conf = MyConfigParser('config.cfg')

#tgr = tgrunner.TGRunner(conf)
#tgr.run()
#ircr = ircrunner.IRCRunner(conf)
#ircr.run()
