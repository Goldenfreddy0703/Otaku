import copy
import threading
from resources.lib.debrid import (all_debrid, debrid_link, premiumize,
                                  real_debrid, torbox)
from resources.lib.ui import control


class TorrentCacheCheck:
    def __init__(self):
        self.premiumizeCached = []
        self.realdebridCached = []
        self.all_debridCached = []
        self.debrid_linkCached = []
        self.torboxCached = []
        self.threads = []

        self.episodeStrings = None
        self.seasonStrings = None

    def torrentCacheCheck(self, torrent_list):
        if control.real_debrid_enabled():
            self.threads.append(
                threading.Thread(target=self.real_debrid_worker, args=(copy.deepcopy(torrent_list),)))

        if control.debrid_link_enabled():
            self.threads.append(
                threading.Thread(target=self.debrid_link_worker, args=(copy.deepcopy(torrent_list),)))

        if control.premiumize_enabled():
            self.threads.append(threading.Thread(target=self.premiumize_worker, args=(copy.deepcopy(torrent_list),)))

        if control.all_debrid_enabled():
            self.threads.append(
                threading.Thread(target=self.all_debrid_worker, args=(copy.deepcopy(torrent_list),)))
            
        if control.torbox_enabled():
            self.threads.append(
                threading.Thread(target=self.torbox_worker, args=(copy.deepcopy(torrent_list),)))

        for i in self.threads:
            i.start()
        for i in self.threads:
            i.join()

        cachedList = self.realdebridCached + self.premiumizeCached + self.all_debridCached + self.debrid_linkCached + self.torboxCached
        return cachedList

    # Function to check cache on 'all_debrid'
    def all_debrid_worker(self, torrent_list):

        api = all_debrid.AllDebrid()

        if len(torrent_list) == 0:
            return

        cache_check = api.check_hash([i['hash'] for i in torrent_list])
        if not cache_check:
            return

        cache_list = []
        cached_items = [m.get('hash') for m in cache_check if m.get('instant') is True]

        for i in torrent_list:
            if i['hash'] in cached_items:
                i['debrid_provider'] = 'all_debrid'
                cache_list.append(i)

        self.all_debridCached = cache_list

    # Function to check cache on 'debrid_link'
    def debrid_link_worker(self, torrent_list):

        api = debrid_link.DebridLink()

        if len(torrent_list) == 0:
            return

        cache_check = api.check_hash([i['hash'] for i in torrent_list])

        if not cache_check:
            return

        cache_list = []

        for i in torrent_list:
            if i['hash'] in list(cache_check.keys()):
                i['debrid_provider'] = 'debrid_link'
                cache_list.append(i)

        self.debrid_linkCached = cache_list

    # Function to check cache on 'real_debrid'
    def real_debrid_worker(self, torrent_list):
        cache_list = []

        hash_list = [i['hash'] for i in torrent_list]

        if len(hash_list) == 0:
            return
        api = real_debrid.RealDebrid()
        realDebridCache = api.checkHash(hash_list)

        for i in torrent_list:
            try:
                if 'rd' not in realDebridCache.get(i['hash'], {}):
                    continue
                if len(realDebridCache[i['hash']]['rd']) >= 1:
                    i['debrid_provider'] = 'real_debrid'
                    cache_list.append(i)
                else:
                    pass
            except KeyError:
                pass

        self.realdebridCached = cache_list

    # Function to check cache on 'premiumize'
    def premiumize_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) == 0:
            return
        premiumizeCache = premiumize.Premiumize().hash_check(hash_list)
        premiumizeCache = premiumizeCache['response']
        cache_list = []
        count = 0
        for i in torrent_list:
            if premiumizeCache[count] is True:
                i['debrid_provider'] = 'premiumize'
                cache_list.append(i)
            count += 1

        self.premiumizeCached = cache_list

    # Function to check cache on 'torbox'
    def torbox_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) == 0:
            return
        
        torboxCache = torbox.Torbox().hash_check(hash_list)
        torboxCache = torboxCache['data']
        cache_list = []

        for i in torrent_list:
            if i['hash'] in torboxCache:
                i['debrid_provider'] = 'torbox'
                cache_list.append(i)

        self.torboxCached = cache_list
