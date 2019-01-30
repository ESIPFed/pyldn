#!/usr/bin/env python

# config.py: An object to manage pyldn's config

from configparser import SafeConfigParser
import logging

clog = logging.getLogger(__name__)

class Pyldnconfig(object):
    def __init__(self):
        '''
        Class constructor
        '''
        CONFIG_INI = 'config.ini'
        config = SafeConfigParser()
        config.read(CONFIG_INI)

        self._base_path = config.get('ldn', 'basePath')
        self._inbox_path = config.get('ldn', 'inboxPath')
        self._port = int(config.get('ldn', 'port'))
        self._storage = config.get('ldn', 'storage')

        if not self._base_path:
            self._base_path = 'http://127.0.0.1'
        if not self._inbox_path:
            self._inbox_path = '/inbox/'
        if self._storage is not 'mem':
            self._cor_user = config.get('esip_cor', 'cor_user')
            self._cor_pass = config.get('esip_cor', 'cor_pass')
            self._cor_org = config.get('esip_cor', 'cor_org')
        if not self._port:
            self._port = 80

        # port_str = ":" + str(self._port) if self._port != 80 else ""
        # self._inbox_url = self._base_path + port_str + self._inbox_path
        #self._inbox_url = self._base_path + self._inbox_path
        self._inbox_url = 'http://cor.esipfed.org/ont/ldn/inbox'

    def log_config(self):
        clog.info('Current pyldn configuration')
        clog.info('Base path: {}'.format(self._base_path))
        clog.info('Inbox path: {}'.format(self._inbox_path))
        clog.info('Storage implementation: {}'.format(self._storage))
