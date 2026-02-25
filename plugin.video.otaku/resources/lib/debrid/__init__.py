import threading

from copy import deepcopy
from resources.lib.debrid import premiumize, torbox, easydebrid
from resources.lib.ui import control


class Debrid:
    def __init__(self):
        self.premiumizeCached = []
        self.torboxCached = []
        self.easydebridCached = []

        self.premiumizeUnCached = []
        self.realdebridUnCached = []
        self.alldebridUnCached = []
        self.debridlinkUnCached = []
        self.torboxUnCached = []
        self.threads = []

    def torrentCacheCheck(self, torrent_list):
        enabled_debrids = control.enabled_debrid()
        if enabled_debrids['realdebrid']:
            t = threading.Thread(target=self.real_debrid_worker, args=(deepcopy(torrent_list),))
            t.start()
            self.threads.append(t)

        if enabled_debrids['debridlink']:
            t = threading.Thread(target=self.debrid_link_worker, args=(deepcopy(torrent_list),))
            self.threads.append(t)
            t.start()

        if enabled_debrids['premiumize']:
            t = threading.Thread(target=self.premiumize_worker, args=(deepcopy(torrent_list),))
            t.start()
            self.threads.append(t)

        if enabled_debrids['alldebrid']:
            t = threading.Thread(target=self.all_debrid_worker, args=(deepcopy(torrent_list),))
            t.start()
            self.threads.append(t)

        if enabled_debrids['torbox']:
            t = threading.Thread(target=self.torbox_worker, args=(deepcopy(torrent_list),))
            t.start()
            self.threads.append(t)

        if enabled_debrids['easydebrid']:
            t = threading.Thread(target=self.easydebrid_worker, args=(deepcopy(torrent_list),))
            t.start()
            self.threads.append(t)

        for i in self.threads:
            i.join()

        cached_list = self.premiumizeCached + self.torboxCached + self.easydebridCached
        uncached_list = self.realdebridUnCached + self.premiumizeUnCached + self.alldebridUnCached + self.debridlinkUnCached + self.torboxUnCached
        return cached_list, uncached_list

    def all_debrid_worker(self, torrent_list):
        if len(torrent_list) > 0:
            for i in torrent_list:
                i['debrid_provider'] = 'Alldebrid'
                self.alldebridUnCached.append(i)

    def debrid_link_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            for torrent in torrent_list:
                torrent['debrid_provider'] = 'Debrid-Link'
                self.debridlinkUnCached.append(torrent)

    def real_debrid_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            for torrent in torrent_list:
                torrent['debrid_provider'] = 'Real-Debrid'
                self.realdebridUnCached.append(torrent)

    def premiumize_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            premiumizeCache = premiumize.Premiumize().hash_check(hash_list)
            if not premiumizeCache or 'response' not in premiumizeCache:
                for torrent in torrent_list:
                    torrent['debrid_provider'] = 'Premiumize'
                    self.premiumizeUnCached.append(torrent)
                return
            premiumizeCache = premiumizeCache['response']

            for index, torrent in enumerate(torrent_list):
                torrent['debrid_provider'] = 'Premiumize'
                if premiumizeCache[index] is True:
                    self.premiumizeCached.append(torrent)
                else:
                    self.premiumizeUnCached.append(torrent)

    def torbox_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            torbox_result = torbox.TorBox().hash_check(hash_list)
            if not torbox_result:
                for torrent in torrent_list:
                    torrent['debrid_provider'] = 'TorBox'
                    self.torboxUnCached.append(torrent)
                return
            cache_check = [i['hash'] for i in torbox_result]
            for torrent in torrent_list:
                torrent['debrid_provider'] = 'TorBox'
                if torrent['hash'] in cache_check:
                    self.torboxCached.append(torrent)
                else:
                    self.torboxUnCached.append(torrent)

    def easydebrid_worker(self, torrent_list):
        # Prepend the magnet prefix to each hash within torrent_list
        hash_list = ["magnet:?xt=urn:btih:" + i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            response = easydebrid.EasyDebrid().lookup_link(hash_list)
            if not response:
                return
            cached_flags = response.get("cached", [])
            for torrent, is_cached in zip(torrent_list, cached_flags):
                torrent['debrid_provider'] = 'EasyDebrid'
                if is_cached:
                    self.easydebridCached.append(torrent)
