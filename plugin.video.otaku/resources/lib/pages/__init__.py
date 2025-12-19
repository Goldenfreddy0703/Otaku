import threading
import time

from resources.lib.pages import nyaa, animetosho, debrid_cloudfiles, animixplay, aniwave, animepahe, hianime, watchnixtoons2, localfiles
from resources.lib.ui import control, database
from resources.lib.windows.get_sources_window import GetSources
from resources.lib.windows import sort_select


# Filter structure for source filtering UI (similar to Seren)
INFO_STRUCT = {
    "videocodec": {
        "AVC", "HEVC", "XVID", "DIVX", "WMV", "MP4", "MPEG", "VP9", "AV1",
    },
    "hdrcodec": {
        "DV", "HDR", "HYBRID", "SDR",
    },
    "audiocodec": {
        "AAC", "DTS", "DTS-HDMA", "DTS-HDHR", "DTS-X", "ATMOS", "TRUEHD",
        "DD+", "DD", "MP3", "WMA", "OPUS",
    },
    "audiochannels": {
        "2.0", "5.1", "7.1",
    },
    "misc": {
        "CAM", "HDTV", "PDTV", "REMUX", "HDRIP", "BLURAY", "DVDRIP", "WEB",
        "HC", "SCR", "3D", "60-FPS", "BATCH"
    },
}


def getSourcesHelper(actionArgs):
    if control.getInt('general.dialog') in (5, 6):
        sources_window = Sources('get_sources_alt.xml', control.ADDON_PATH, actionArgs=actionArgs)
    else:
        sources_window = Sources('get_sources.xml', control.ADDON_PATH, actionArgs=actionArgs)
    sources = sources_window.doModal()
    return sources


class Sources(GetSources):
    def __init__(self, xml_file, location, actionArgs=None):
        super(Sources, self).__init__(xml_file, location, actionArgs)
        self.torrentProviders = ['nyaa', 'animetosho']
        self.embedProviders = ['animepahe', 'animix', 'aniwave', 'hianime', 'watchnixtoons2']
        self.CloudProviders = ['Cloud Inspection']
        self.localProviders = ['Local Inspection']
        self.remainingProviders = self.embedProviders + self.torrentProviders + self.localProviders + self.CloudProviders

        self.torrents_qual_len = [0, 0, 0, 0, 0]
        self.embeds_qual_len = [0, 0, 0, 0, 0]
        self.return_data = []
        self.progress = 1
        self.threads = []

        self.torrentSources = []
        self.torrentCacheSources = []
        self.torrentUnCacheSources = []
        self.embedSources = []
        self.cloud_files = []
        self.local_files = []

    def getSources(self, args):
        query = args['query']
        mal_id = args['mal_id']
        episode = args['episode']
        status = args['status']
        media_type = args['media_type']
        duration = args['duration']
        rescrape = args['rescrape']
        # source_select = args['source_select']

        self.setProperty('process_started', 'true')

        # set skipintro times to -1 before scraping
        control.setInt('hianime.skipintro.start', -1)
        control.setInt('hianime.skipintro.end', -1)
        control.setInt('aniwave.skipintro.start', -1)
        control.setInt('aniwave.skipintro.end', -1)

        # set skipoutro times to -1 before scraping
        control.setInt('hianime.skipoutro.start', -1)
        control.setInt('hianime.skipoutro.end', -1)
        control.setInt('aniwave.skipoutro.start', -1)
        control.setInt('aniwave.skipoutro.end', -1)

        enabled_debrids = control.enabled_debrid()
        enabled_clouds = control.enabled_cloud()

        # Activate cloud inspection only if the same debrid service is enabled for both
        common_debrids = [
            service for service, is_enabled in enabled_debrids.items()
            if is_enabled and enabled_clouds.get(service, False)
        ]

        if any(enabled_debrids.values()):
            if control.getBool('provider.nyaa'):
                t = threading.Thread(target=self.nyaa_worker, args=(query, mal_id, episode, status, media_type, rescrape))
                t.start()
                self.threads.append(t)
            else:
                self.remainingProviders.remove('nyaa')

            if control.getBool('provider.animetosho'):
                t = threading.Thread(target=self.animetosho_worker, args=(query, mal_id, episode, status, media_type, rescrape))
                t.start()
                self.threads.append(t)
            else:
                self.remainingProviders.remove('animetosho')

        else:
            for provider in self.torrentProviders:
                self.remainingProviders.remove(provider)

        # cloud #
        if common_debrids:
            t = threading.Thread(target=self.user_cloud_inspection, args=(query, mal_id, episode))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('Cloud Inspection')

        # local #
        if control.getBool('provider.localfiles'):
            t = threading.Thread(target=self.user_local_inspection, args=(query, mal_id, episode))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('Local Inspection')

        # embeds #
        if control.getBool('provider.animepahe'):
            t = threading.Thread(target=self.animepahe_worker, args=(mal_id, episode, rescrape))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('animepahe')

        if control.getBool('provider.animix'):
            t = threading.Thread(target=self.animix_worker, args=(mal_id, episode, rescrape))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('animix')

        if control.getBool('provider.aniwave'):
            t = threading.Thread(target=self.aniwave_worker, args=(mal_id, episode, rescrape))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('aniwave')

        # if control.getBool('provider.gogo'):
        #     t = threading.Thread(target=self.gogo_worker, args=(mal_id, episode, rescrape))
        #     t.start()
        #     self.threads.append(t)
        # else:
        #     self.remainingProviders.remove('gogo')

        if control.getBool('provider.hianime'):
            t = threading.Thread(target=self.hianime_worker, args=(mal_id, episode, rescrape))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('hianime')

        if control.getBool('provider.watchnixtoons2'):
            t = threading.Thread(target=self.watchnixtoons2_worker, args=(mal_id, episode, media_type, rescrape))
            t.start()
            self.threads.append(t)
        else:
            self.remainingProviders.remove('watchnixtoons2')

        timeout = 60 if rescrape else control.getInt('general.timeout')
        start_time = time.perf_counter()
        runtime = 0

        while runtime < timeout:
            if not self.silent:
                self.updateProgress()
                self.update_properties("4K: %s | 1080: %s | 720: %s | SD: %s| EQ: %s" % (
                    control.colorstr(self.torrents_qual_len[0] + self.embeds_qual_len[0]),
                    control.colorstr(self.torrents_qual_len[1] + self.embeds_qual_len[1]),
                    control.colorstr(self.torrents_qual_len[2] + self.embeds_qual_len[2]),
                    control.colorstr(self.torrents_qual_len[3] + self.embeds_qual_len[3]),
                    control.colorstr(self.torrents_qual_len[4] + self.embeds_qual_len[4])
                ))
            control.sleep(500)

            if (
                self.canceled
                or not self.remainingProviders
                or (control.getBool('general.terminate.oncloud') and len(self.cloud_files) > 0)
                or (control.getBool('general.terminate.onlocal') and len(self.local_files) > 0)
            ):
                break

            runtime = time.perf_counter() - start_time
            self.progress = runtime / timeout * 100

        if len(self.torrentSources) + len(self.embedSources) + len(self.cloud_files) + len(self.local_files) == 0:
            self.return_data = []
        else:
            self.return_data = self.sortSources(self.torrentSources, self.embedSources, self.cloud_files, self.local_files, media_type, duration)
        self.close()
        return self.return_data

    # Torrents #
    def nyaa_worker(self, query, mal_id, episode, status, media_type, rescrape):
        if rescrape:
            all_sources = nyaa.Sources().get_sources(query, mal_id, episode, status, media_type)
        else:
            all_sources = database.get(nyaa.Sources().get_sources, 8, query, mal_id, episode, status, media_type, key='nyaa')

        # Defensive check to ensure all_sources is not None
        if all_sources is None:
            all_sources = {'cached': [], 'uncached': []}

        self.torrentUnCacheSources += all_sources['uncached']
        self.torrentCacheSources += all_sources['cached']
        self.torrentSources += all_sources['cached'] + all_sources['uncached']
        self.remainingProviders.remove('nyaa')

    def animetosho_worker(self, query, mal_id, episode, status, media_type, rescrape):
        if rescrape:
            all_sources = animetosho.Sources().get_sources(query, mal_id, episode, status, media_type)
        else:
            all_sources = database.get(animetosho.Sources().get_sources, 8, query, mal_id, episode, status, media_type, key='animetosho')

        # Defensive check to ensure all_sources is not None
        if all_sources is None:
            all_sources = {'cached': [], 'uncached': []}

        self.torrentUnCacheSources += all_sources['uncached']
        self.torrentCacheSources += all_sources['cached']
        self.torrentSources += all_sources['cached'] + all_sources['uncached']
        self.remainingProviders.remove('animetosho')

    # embeds #
    def animepahe_worker(self, mal_id, episode, rescrape):
        if rescrape:
            self.embedSources += animepahe.Sources().get_sources(mal_id, episode)
        else:
            self.embedSources += database.get(animepahe.Sources().get_sources, 8, mal_id, episode, key='animepahe')
        self.remainingProviders.remove('animepahe')

    def animix_worker(self, mal_id, episode, rescrape):
        if rescrape:
            self.embedSources += animixplay.Sources().get_sources(mal_id, episode)
        else:
            self.embedSources += database.get(animixplay.Sources().get_sources, 8, mal_id, episode, key='animix')
        self.remainingProviders.remove('animix')

    def aniwave_worker(self, mal_id, episode, rescrape):
        if rescrape:
            aniwave_sources = aniwave.Sources().get_sources(mal_id, episode)
        else:
            aniwave_sources = database.get(aniwave.Sources().get_sources, 8, mal_id, episode, key='aniwave')
        self.embedSources += aniwave_sources
        for x in aniwave_sources:
            if x.get('skip'):
                if x['skip'].get('intro') and x['skip']['intro']['start'] != 0:
                    control.setInt('aniwave.skipintro.start', int(x['skip']['intro']['start']))
                    control.setInt('aniwave.skipintro.end', int(x['skip']['intro']['end']))
                if x['skip'].get('outro') and x['skip']['outro']['start'] != 0:
                    control.setInt('aniwave.skipoutro.start', int(x['skip']['outro']['start']))
                    control.setInt('aniwave.skipoutro.end', int(x['skip']['outro']['end']))
        self.remainingProviders.remove('aniwave')

    # def gogo_worker(self, mal_id, episode, rescrape):
    #     if rescrape:
    #         self.embedSources += gogoanime.Sources().get_sources(mal_id, episode)
    #     else:
    #         self.embedSources += database.get(gogoanime.Sources().get_sources, 8, mal_id, episode, key='gogoanime')
    #     self.remainingProviders.remove('gogo')

    def hianime_worker(self, mal_id, episode, rescrape):
        if rescrape:
            hianime_sources = hianime.Sources().get_sources(mal_id, episode)
        else:
            hianime_sources = database.get(hianime.Sources().get_sources, 8, mal_id, episode, key='hianime')
        self.embedSources += hianime_sources
        for x in hianime_sources:
            if x.get('skip'):
                if x['skip'].get('intro') and x['skip']['intro']['start'] != 0:
                    control.setInt('hianime.skipintro.start', int(x['skip']['intro']['start']))
                    control.setInt('hianime.skipintro.end', int(x['skip']['intro']['end']))
                if x['skip'].get('outro') and x['skip']['outro']['start'] != 0:
                    control.setInt('hianime.skipoutro.start', int(x['skip']['outro']['start']))
                    control.setInt('hianime.skipoutro.end', int(x['skip']['outro']['end']))
        self.remainingProviders.remove('hianime')

    def watchnixtoons2_worker(self, mal_id, episode, media_type, rescrape):
        if rescrape:
            self.embedSources += watchnixtoons2.Sources().get_sources(mal_id, episode, media_type)
        else:
            self.embedSources += database.get(watchnixtoons2.Sources().get_sources, 8, mal_id, episode, media_type, key='watchnixtoons2')
        self.remainingProviders.remove('watchnixtoons2')

    # Local & Cloud #
    def user_local_inspection(self, query, mal_id, episode):
        episode_data = database.get_episode(mal_id)
        season = episode_data.get('season') if episode_data else None
        self.local_files += localfiles.Sources().get_sources(query, mal_id, episode, season)
        self.remainingProviders.remove('Local Inspection')

    def user_cloud_inspection(self, query, mal_id, episode):
        episode_data = database.get_episode(mal_id)
        season = episode_data.get('season') if episode_data else None
        self.cloud_files += debrid_cloudfiles.Sources().get_sources(query, mal_id, episode, season)
        self.remainingProviders.remove('Cloud Inspection')

    @staticmethod
    def sortSources(torrent_list, embed_list, cloud_files, local_files, media_type, duration):
        all_list = torrent_list + embed_list + cloud_files + local_files
        sortedList = [x for x in all_list if control.getInt('general.minResolution') <= x['quality'] <= control.getInt('general.maxResolution')]

        # Filter by size
        filter_option = control.getInt('general.fileFilter')

        if filter_option == 1:
            # web speed limit
            webspeed = control.getInt('general.webspeed')
            len_in_sec = int(duration) * 60

            _torrent_list = torrent_list
            torrent_list = [i for i in _torrent_list if i['size'] != 'NA' and ((float(i['size'][:-3]) * 8000) / len_in_sec) <= webspeed]

        elif filter_option == 2:
            # hard limit
            _torrent_list = torrent_list

            if media_type == 'movie':
                max_GB = float(control.getInt('general.movie.maxGB'))
                min_GB = control.getNumber('general.movie.minGB')
            else:
                max_GB = float(control.getInt('general.episode.maxGB'))
                min_GB = control.getNumber('general.episode.minGB')

            torrent_list = []
            for i in _torrent_list:
                if i['size'] != 'NA':
                    size = float(i['size'][:-3])
                    unit = i['size'][-2:].strip()

                    if unit == 'MB':
                        size /= 1024  # convert MB to GB for comparison

                    if min_GB <= size <= max_GB:
                        torrent_list.append(i)

        # Filter by release title
        if control.getBool('general.release_title_filter.enabled'):
            release_title_filter1 = control.getSetting('general.release_title_filter.value1')
            release_title_filter2 = control.getSetting('general.release_title_filter.value2')
            release_title_filter3 = control.getSetting('general.release_title_filter.value3')
            release_title_filter4 = control.getSetting('general.release_title_filter.value4')
            release_title_filter5 = control.getSetting('general.release_title_filter.value5')

            # Get the new settings
            exclude_filter1 = control.getBool('general.release_title_filter.exclude1')
            exclude_filter2 = control.getBool('general.release_title_filter.exclude2')
            exclude_filter3 = control.getBool('general.release_title_filter.exclude3')
            exclude_filter4 = control.getBool('general.release_title_filter.exclude4')
            exclude_filter5 = control.getBool('general.release_title_filter.exclude5')

            _torrent_list = torrent_list
            release_title_logic = control.getInt('general.release_title_filter.logic')
            if release_title_logic == 0:
                # AND filter (case-insensitive)
                torrent_list = [
                    i for i in _torrent_list
                    if (not exclude_filter1 or release_title_filter1.lower() not in i['release_title'].lower())
                    and (not exclude_filter2 or release_title_filter2.lower() not in i['release_title'].lower())
                    and (not exclude_filter3 or release_title_filter3.lower() not in i['release_title'].lower())
                    and (not exclude_filter4 or release_title_filter4.lower() not in i['release_title'].lower())
                    and (not exclude_filter5 or release_title_filter5.lower() not in i['release_title'].lower())
                ]
            if release_title_logic == 1:
                # OR filter (case-insensitive)
                torrent_list = [
                    i for i in _torrent_list
                    if (release_title_filter1 != "" and (exclude_filter1 ^ (release_title_filter1.lower() in i['release_title'].lower())))
                    or (release_title_filter2 != "" and (exclude_filter2 ^ (release_title_filter2.lower() in i['release_title'].lower())))
                    or (release_title_filter3 != "" and (exclude_filter3 ^ (release_title_filter3.lower() in i['release_title'].lower())))
                    or (release_title_filter4 != "" and (exclude_filter4 ^ (release_title_filter4.lower() in i['release_title'].lower())))
                    or (release_title_filter5 != "" and (exclude_filter5 ^ (release_title_filter5.lower() in i['release_title'].lower())))
                ]

        # Update sortedList to include the filtered torrent_list
        sortedList = [x for x in sortedList if x in torrent_list or x in embed_list or x in cloud_files or x in local_files]

        # Apply general.filters (comprehensive filtering like Seren)
        filter_list = control.getStringList("general.filters")
        if filter_list:
            current_filters = set(filter_list)
            # Special HDR/DV handling (like Seren does for HYBRID sources)
            disable_dv = "DV" in current_filters
            disable_hdr = "HDR" in current_filters
            filter_set = current_filters.difference({"HDR", "DV"})

            filtered = []
            for source in sortedList:
                # Skip if ANY filtered tag is in source info (set intersection)
                if filter_set & set(source['info']):
                    continue
                # DV filter: exclude DV sources unless they're HYBRID
                if disable_dv and "DV" in source['info'] and "HYBRID" not in source['info']:
                    continue
                # HDR filter: exclude HDR sources unless they're HYBRID
                if disable_hdr and "HDR" in source['info'] and "HYBRID" not in source['info']:
                    continue
                # Hybrid filter: if both DV and HDR are disabled, exclude HYBRID too
                if disable_dv and disable_hdr and "HYBRID" in source['info']:
                    continue
                filtered.append(source)
            sortedList = filtered

        # Filter by language source
        source = control.getInt("general.source")
        if source != 0:
            if source == 1:
                sortedList = [i for i in sortedList if i['lang'] in [0, 1, 2]]
            elif source == 2:
                sortedList = [i for i in sortedList if i['lang'] in [0, 1, 3]]

        # Sort Sources
        SORT_METHODS = sort_select.SORT_METHODS
        sort_options = sort_select.sort_options

        for x in range(len(SORT_METHODS), 0, -1):
            reverse = sort_options[f'sortmethod.{x}.reverse']
            method = SORT_METHODS[int(sort_options[f'sortmethod.{x}'])]
            # Replace spaces with underscores in the method name
            method = method.replace(' ', '_')
            sortedList = getattr(sort_select, f'sort_by_{method}')(sortedList, not reverse)

        return sortedList

    def updateProgress(self):
        self.torrents_qual_len = [
            len([i for i in self.torrentSources if i['quality'] == 4]),
            len([i for i in self.torrentSources if i['quality'] == 3]),
            len([i for i in self.torrentSources if i['quality'] == 2]),
            len([i for i in self.torrentSources if i['quality'] == 1]),
            len([i for i in self.torrentSources if i['quality'] == 0])
        ]

        self.embeds_qual_len = [
            len([i for i in self.embedSources if i['quality'] == 4]),
            len([i for i in self.embedSources if i['quality'] == 3]),
            len([i for i in self.embedSources if i['quality'] == 2]),
            len([i for i in self.embedSources if i['quality'] == 1]),
            len([i for i in self.embedSources if i['quality'] == 0])
        ]
