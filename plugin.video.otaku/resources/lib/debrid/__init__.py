import threading

from copy import deepcopy
from resources.lib.debrid import premiumize, torbox, easydebrid, debrid_cache
from resources.lib.ui import control


class Debrid:
    def __init__(self):
        self.premiumizeCached = []
        self.realdebridCached = []
        self.alldebridCached = []
        self.torboxCached = []
        self.easydebridCached = []

        self.premiumizeUnCached = []
        self.realdebridUnCached = []
        self.alldebridUnCached = []
        self.debridlinkUnCached = []
        self.torboxUnCached = []
        self.threads = []

    def torrentCacheCheck(self, torrent_list, mal_id=None, episode=None, media_type=None):
        enabled_debrids = control.enabled_debrid()
        if enabled_debrids['realdebrid']:
            t = threading.Thread(target=self.real_debrid_worker, args=(deepcopy(torrent_list), mal_id, episode, media_type))
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
            t = threading.Thread(target=self.all_debrid_worker, args=(deepcopy(torrent_list), mal_id, episode, media_type))
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

        cached_list = self.realdebridCached + self.alldebridCached + self.premiumizeCached + self.torboxCached + self.easydebridCached
        uncached_list = self.realdebridUnCached + self.premiumizeUnCached + self.alldebridUnCached + self.debridlinkUnCached + self.torboxUnCached
        return cached_list, uncached_list

    def _get_imdb_and_season(self, mal_id, episode, media_type):
        """Get IMDB ID and season info for external cache checking."""
        imdb_id = None
        season = None
        try:
            if mal_id:
                from resources.lib.ui import database
                mappings = database.get_mappings(mal_id, 'mal_id')
                if mappings:
                    imdb_id = mappings.get('imdb_id')
                    db_media_type = mappings.get('anime_media_type') or mappings.get('global_media_type') or media_type
                    if db_media_type and 'movie' in str(db_media_type).lower():
                        season = None  # Movies don't use season/episode
                    else:
                        from resources.lib.ui.utils import get_season
                        title = mappings.get('mal_title', '')
                        season = get_season([title], mal_id) if title else 1
        except Exception as e:
            control.log(f'Failed to get IMDB ID for cache check: {e}', 'warning')
        return imdb_id, season

    def all_debrid_worker(self, torrent_list, mal_id=None, episode=None, media_type=None):
        if not torrent_list:
            return
        hash_list = [i['hash'] for i in torrent_list]

        # First check local debrid cache DB
        cached_from_db = debrid_cache.get_cached_hashes(hash_list)
        db_cached = {r['hash'] for r in cached_from_db if r['debrid'] == 'ad' and r['cached'] == 'True'}
        db_uncached = {r['hash'] for r in cached_from_db if r['debrid'] == 'ad' and r['cached'] == 'False'}
        db_known = db_cached | db_uncached
        unknown_hashes = [h for h in hash_list if h not in db_known]

        # External check for unknown hashes
        external_cached = set()
        if unknown_hashes:
            imdb_id, season = self._get_imdb_and_season(mal_id, episode, media_type)
            if imdb_id:
                external_cached = set(debrid_cache.check_ad_cache(imdb_id, season, episode))
                # Save results to local DB
                hashes_to_cache = []
                for h in unknown_hashes:
                    status = 'True' if h in external_cached else 'False'
                    hashes_to_cache.append((h, status))
                threading.Thread(target=debrid_cache.set_cached_hashes, args=(hashes_to_cache, 'ad')).start()

        all_cached = db_cached | external_cached
        for torrent in torrent_list:
            torrent['debrid_provider'] = 'Alldebrid'
            if torrent['hash'] in all_cached:
                self.alldebridCached.append(torrent)
            else:
                self.alldebridUnCached.append(torrent)

    def debrid_link_worker(self, torrent_list):
        hash_list = [i['hash'] for i in torrent_list]
        if len(hash_list) > 0:
            for torrent in torrent_list:
                torrent['debrid_provider'] = 'Debrid-Link'
                self.debridlinkUnCached.append(torrent)

    def real_debrid_worker(self, torrent_list, mal_id=None, episode=None, media_type=None):
        if not torrent_list:
            return
        hash_list = [i['hash'] for i in torrent_list]

        # First check local debrid cache DB
        cached_from_db = debrid_cache.get_cached_hashes(hash_list)
        db_cached = {r['hash'] for r in cached_from_db if r['debrid'] == 'rd' and r['cached'] == 'True'}
        db_uncached = {r['hash'] for r in cached_from_db if r['debrid'] == 'rd' and r['cached'] == 'False'}
        db_known = db_cached | db_uncached
        unknown_hashes = [h for h in hash_list if h not in db_known]

        # External check for unknown hashes
        external_cached = set()
        if unknown_hashes:
            imdb_id, season = self._get_imdb_and_season(mal_id, episode, media_type)
            if imdb_id:
                external_cached = set(debrid_cache.check_rd_cache(unknown_hashes, imdb_id, season, episode))
                # Save results to local DB
                hashes_to_cache = []
                for h in unknown_hashes:
                    status = 'True' if h in external_cached else 'False'
                    hashes_to_cache.append((h, status))
                threading.Thread(target=debrid_cache.set_cached_hashes, args=(hashes_to_cache, 'rd')).start()

        all_cached = db_cached | external_cached
        for torrent in torrent_list:
            torrent['debrid_provider'] = 'Real-Debrid'
            if torrent['hash'] in all_cached:
                self.realdebridCached.append(torrent)
            else:
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
