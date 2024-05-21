import threading
import time

from resources.lib.pages import nyaa, animetosho, animixplay, debrid_cloudfiles, \
    aniwave, gogoanime, animepahe, hianime, animess, animelatino, animecat, aniplay, \
    local_localfiles
from resources.lib.ui import control
from resources.lib.windows.get_sources_window import GetSources as DisplayWindow


class CancelProcess(Exception):
    pass


def getSourcesHelper(actionArgs):
    if control.getSetting('general.dialog') == '4':
        sources_window = Sources(*('get_sources_az.xml', control.ADDON_PATH),
                                 actionArgs=actionArgs)
    else:
        sources_window = Sources(*('get_sources.xml', control.ADDON_PATH),
                                 actionArgs=actionArgs)

    sources = sources_window.doModal()
    try:
        del sources_window
    except:
        pass
    return sources


class Sources(DisplayWindow):
    def __init__(self, xml_file, location, actionArgs=None):

        try:
            super(Sources, self).__init__(xml_file, location, actionArgs)
        except:
            self.args = actionArgs
            self.canceled = False

        self.torrent_threads = []
        self.hoster_threads = []
        self.torrentProviders = []
        self.hosterProviders = []
        self.language = 'en'
        self.torrentCacheSources = []
        self.embedSources = []
        self.hosterSources = []
        self.cloud_files = []
        self.local_files = []
        self.remainingProviders = [
            'nyaa', 'animetosho', 'aniwave', 'gogo', 'animix',
            'animepahe', 'h!anime', 'otakuanimes', 'animelatino',
            'nekosama', 'aniplay', 'Local Inspection', 'Cloud Inspection'
        ]
        self.allTorrents = {}
        self.allTorrents_len = 0
        self.hosterDomains = {}
        self.torrents_qual_len = [0, 0, 0, 0]
        self.hosters_qual_len = [0, 0, 0, 0]
        self.trakt_id = ''
        self.silent = False
        self.return_data = (None, None, None)
        self.basic_windows = True
        self.progress = 1
        self.duplicates_amount = 0
        self.domain_list = []
        self.display_style = 0
        self.background_dialog = None
        self.running_providers = []

        self.line1 = ''
        self.line2 = ''
        self.line3 = ''

        self.host_domains = []
        self.host_names = []

        self.remainingSources = ['1', '2', '3']
        self.nyaaSources = []
        self.animetoshoSources = []
        self.gogoSources = []
        self.aniwaveSources = []
        self.animixplaySources = []
        self.animepaheSources = []
        self.hianimeSources = []
        self.animessSources = []
        self.animelatinoSources = []
        self.animecatSources = []
        self.aniplaySources = []
        self.threads = []
        self.usercloudSources = []
        self.userlocalSources = []
        self.terminate_on_cloud = control.getSetting('general.terminate.oncloud') == 'true'
        self.terminate_on_local = control.getSetting('general.terminate.onlocal') == 'true'

    def getSources(self, args):
        query = args['query']
        anilist_id = args['anilist_id']
        episode = args['episode']
        status = args['status']
        filter_lang = args['filter_lang']
        media_type = args['media_type']
        rescrape = args['rescrape']
        get_backup = args['get_backup']
        self.setProperty('process_started', 'true')
        duration = args['duration']

        if control.real_debrid_enabled() or control.all_debrid_enabled() or control.debrid_link_enabled() or control.premiumize_enabled():
            if control.getSetting('provider.nyaa') == 'true':
                self.threads.append(
                    threading.Thread(target=self.nyaa_worker, args=(query, anilist_id, episode, status, media_type, rescrape)))
            else:
                self.remainingProviders.remove('nyaa')

            if control.getSetting('provider.animetosho') == 'true':
                self.threads.append(
                    threading.Thread(target=self.animetosho_worker, args=(query, anilist_id, episode, status, media_type, rescrape)))
            else:
                self.remainingProviders.remove('animetosho')

        else:
            self.remainingProviders.remove('nyaa')
            self.remainingProviders.remove('animetosho')

        if control.getSetting('provider.gogo') == 'true':
            self.threads.append(
                threading.Thread(target=self.gogo_worker, args=(anilist_id, episode, get_backup, rescrape)))
        else:
            self.remainingProviders.remove('gogo')

        if control.getSetting('provider.aniwave') == 'true':
            self.threads.append(
                threading.Thread(target=self.aniwave_worker, args=(anilist_id, episode, get_backup, rescrape)))
        else:
            self.remainingProviders.remove('aniwave')

        if control.getSetting('provider.animix') == 'true':
            self.threads.append(
                threading.Thread(target=self.animixplay_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('animix')

        if control.getSetting('provider.animepahe') == 'true':
            self.threads.append(
                threading.Thread(target=self.animepahe_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('animepahe')

        if control.getSetting('provider.hianime') == 'true':
            self.threads.append(
                threading.Thread(target=self.hianime_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('h!anime')

        if control.getSetting('provider.animess') == 'true':
            self.threads.append(
                threading.Thread(target=self.animess_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('otakuanimes')

        if control.getSetting('provider.animelatino') == 'true':
            self.threads.append(
                threading.Thread(target=self.animelatino_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('animelatino')

        if control.getSetting('provider.animecat') == 'true':
            self.threads.append(
                threading.Thread(target=self.animecat_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('nekosama')

        if control.getSetting('provider.aniplay') == 'true':
            self.threads.append(
                threading.Thread(target=self.aniplay_worker, args=(anilist_id, episode, get_backup, rescrape,)))
        else:
            self.remainingProviders.remove('aniplay')

        if control.getSetting('scraping.localInspection') == 'true':
            self.threads.append(
                threading.Thread(target=self.user_local_inspection, args=(query, anilist_id, episode, rescrape)))
        else:
            self.remainingProviders.remove('Local Inspection')

        self.threads.append(
            threading.Thread(target=self.user_cloud_inspection, args=(query, anilist_id, episode, media_type, rescrape)))

        cloud_thread = threading.Thread(target=self.user_cloud_inspection, args=(query, anilist_id, episode, media_type, rescrape))

        for i in self.threads:
            i.start()
        cloud_thread.start()

        timeout = 60 if rescrape else int(control.getSetting('general.timeout'))
        start_time = time.perf_counter() if control.PY3 else time.time()
        runtime = 0

        while runtime < timeout:
            if (self.canceled
                    or len(self.remainingProviders) < 1
                    and runtime > 5
                    or self.terminate_on_cloud
                    and len(self.cloud_files) > 0
                    or self.terminate_on_local
                    and len(self.local_files) > 0):
                self.updateProgress()
                self.setProgress()
                self.setText("4K: %s | 1080: %s | 720: %s | SD: %s" % (
                    control.colorString(self.torrents_qual_len[0] + self.hosters_qual_len[0]),
                    control.colorString(self.torrents_qual_len[1] + self.hosters_qual_len[1]),
                    control.colorString(self.torrents_qual_len[2] + self.hosters_qual_len[2]),
                    control.colorString(self.torrents_qual_len[3] + self.hosters_qual_len[3]),
                ))
                time.sleep(.5)
                break
            self.updateProgress()
            self.setProgress()
            self.setText("4K: %s | 1080: %s | 720: %s | SD: %s" % (
                control.colorString(self.torrents_qual_len[0] + self.hosters_qual_len[0]),
                control.colorString(self.torrents_qual_len[1] + self.hosters_qual_len[1]),
                control.colorString(self.torrents_qual_len[2] + self.hosters_qual_len[2]),
                control.colorString(self.torrents_qual_len[3] + self.hosters_qual_len[3]),
            ))

            # Update Progress
            time.sleep(.5)
            runtime = (time.perf_counter() if control.PY3 else time.time()) - start_time
            self.progress = runtime / timeout * 100

        # make sure cloud sources thread finishes before moving on
        cloud_thread.join()

        if len(self.torrentCacheSources) + len(self.embedSources) + len(self.cloud_files) + len(self.local_files) == 0:
            self.return_data = []
            self.close()
            return
        
        sourcesList = self.sortSources(self.torrentCacheSources, self.embedSources, filter_lang, media_type, duration)
        self.return_data = sourcesList
        self.close()
        # control.log('Sorted sources :\n {0}'.format(sourcesList), 'info')
        return

    def nyaa_worker(self, query, anilist_id, episode, status, media_type, rescrape):
        self.nyaaSources = nyaa.sources().get_sources(query, anilist_id, episode, status, media_type, rescrape)
        self.torrentCacheSources += self.nyaaSources
        self.remainingProviders.remove('nyaa')

    def animetosho_worker(self, query, anilist_id, episode, status, media_type, rescrape):
        self.animetoshoSources = animetosho.sources().get_sources(query, anilist_id, episode, status, media_type, rescrape)
        self.torrentCacheSources += self.animetoshoSources
        self.remainingProviders.remove('animetosho')

    def gogo_worker(self, anilist_id, episode, get_backup, rescrape):
        if not rescrape:
            self.gogoSources = gogoanime.sources().get_sources(anilist_id, episode, get_backup)
            self.embedSources += self.gogoSources
        self.remainingProviders.remove('gogo')

    def aniwave_worker(self, anilist_id, episode, get_backup, rescrape):
        if not rescrape:
            self.aniwaveSources = aniwave.sources().get_sources(anilist_id, episode, get_backup)
            self.embedSources += self.aniwaveSources
        self.remainingProviders.remove('aniwave')

    def animixplay_worker(self, anilist_id, episode, get_backup, rescrape):
        if not rescrape:
            self.animixplaySources = animixplay.sources().get_sources(anilist_id, episode, get_backup)
            self.embedSources += self.animixplaySources
        self.remainingProviders.remove('animix')

    def animepahe_worker(self, anilist_id, episode, get_backup, rescrape):
        if not rescrape:
            self.animepaheSources = animepahe.sources().get_sources(anilist_id, episode, get_backup)
            self.embedSources += self.animepaheSources
        self.remainingProviders.remove('animepahe')

    def hianime_worker(self, anilist_id, episode, get_backup, rescrape):
        if not rescrape:
            self.hianimeSources = hianime.sources().get_sources(anilist_id, episode, get_backup)
            self.embedSources += self.hianimeSources
        self.remainingProviders.remove('h!anime')

    def animess_worker(self, anilist_id, episode, get_backup, rescrape):
        self.animessSources = animess.sources().get_sources(anilist_id, episode, get_backup)
        self.embedSources += self.animessSources
        self.remainingProviders.remove('otakuanimes')

    def animelatino_worker(self, anilist_id, episode, get_backup, rescrape):
        self.animelatinoSources = animelatino.sources().get_sources(anilist_id, episode, get_backup)
        self.embedSources += self.animelatinoSources
        self.remainingProviders.remove('animelatino')

    def animecat_worker(self, anilist_id, episode, get_backup, rescrape):
        self.animecatSources = animecat.sources().get_sources(anilist_id, episode, get_backup)
        self.embedSources += self.animecatSources
        self.remainingProviders.remove('nekosama')

    def aniplay_worker(self, anilist_id, episode, get_backup, rescrape):
        self.aniplaySources = aniplay.sources().get_sources(anilist_id, episode, get_backup)
        self.embedSources += self.aniplaySources
        self.remainingProviders.remove('aniplay')

    def user_local_inspection(self, query, anilist_id, episode, rescrape):
        if not rescrape:
            self.userlocalSources += local_localfiles.sources().get_sources(query, anilist_id, episode)
            self.local_files += self.userlocalSources
        self.remainingProviders.remove('Local Inspection')

    def user_cloud_inspection(self, query, anilist_id, episode, media_type, rescrape):
        if not rescrape:
            debrid = {}

            if control.real_debrid_enabled() and control.getSetting('rd.cloudInspection') == 'true':
                debrid['real_debrid'] = True

            if control.premiumize_enabled() and control.getSetting('premiumize.cloudInspection') == 'true':
                debrid['premiumize'] = True

            self.usercloudSources = debrid_cloudfiles.sources().get_sources(debrid, query, episode)
            self.cloud_files += self.usercloudSources

        self.remainingProviders.remove('Cloud Inspection')

    @staticmethod
    def resolutionList():
        resolutions = []
        max_res = int(control.getSetting('general.maxResolution'))
        if max_res <= 3:
            resolutions.append('NA')
            resolutions.append('EQ')
        if max_res < 3:
            resolutions.append('720p')
        if max_res < 2:
            resolutions.append('1080p')
        if max_res < 1:
            resolutions.append('4K')

        return resolutions

    @staticmethod
    def debrid_priority():
        p = []

        if control.getSetting('premiumize.enabled') == 'true':
            p.append({'slug': 'premiumize', 'priority': int(control.getSetting('premiumize.priority'))})
        if control.getSetting('realdebrid.enabled') == 'true':
            p.append({'slug': 'real_debrid', 'priority': int(control.getSetting('rd.priority'))})
        if control.getSetting('alldebrid.enabled') == 'true':
            p.append({'slug': 'all_debrid', 'priority': int(control.getSetting('alldebrid.priority'))})
        if control.getSetting('dl.enabled') == 'true':
            p.append({'slug': 'debrid_link', 'priority': int(control.getSetting('dl.priority'))})

        p.append({'slug': '', 'priority': 11})

        p = sorted(p, key=lambda i: i['priority'])

        return p

    def sortSources(self, torrent_list, embed_list, filter_lang, media_type, duration):
        sort_method = int(control.getSetting('general.sortsources'))

        sortedList = []

        resolutions = self.resolutionList()

        resolutions.reverse()

        for i in self.cloud_files:
            sortedList.append(i)

        for i in self.local_files:
            sortedList.append(i)

        if filter_lang:
            filter_lang = int(filter_lang)
            _torrent_list = torrent_list

            torrent_list = [i for i in _torrent_list if i['lang'] != filter_lang]

            embed_list = [i for i in embed_list if i['lang'] != filter_lang]

        filter_option = control.getSetting('general.fileFilter')

        if filter_option == '1':
            # web speed limit
            webspeed = int(control.getSetting('general.webspeed'))
            len_in_sec = int(duration) * 60

            _torrent_list = torrent_list
            torrent_list = [i for i in _torrent_list if i['size'] != 'NA' and ((float(i['size'][:-3]) * 8000) / len_in_sec) <= webspeed]

        elif filter_option == '2':
            # hard limit
            _torrent_list = torrent_list

            if media_type == 'movie':
                max_GB = float(control.getSetting('general.movie.maxGB'))
                min_GB = float(control.getSetting('general.movie.minGB'))
            else:
                max_GB = float(control.getSetting('general.episode.maxGB'))
                min_GB = float(control.getSetting('general.episode.minGB'))

            torrent_list = [i for i in _torrent_list if i['size'] != 'NA' and min_GB <= float(i['size'][:-3]) <= max_GB]

        if control.getSetting('general.release_title_filter.enabled') == 'true':
            release_title_filter1 = control.getSetting('general.release_title_filter.value1')
            release_title_filter2 = control.getSetting('general.release_title_filter.value2')
            release_title_filter3 = control.getSetting('general.release_title_filter.value3')
            release_title_filter4 = control.getSetting('general.release_title_filter.value4')
            release_title_filter5 = control.getSetting('general.release_title_filter.value5')
            _torrent_list = torrent_list
            release_title_logic = control.getSetting('general.release_title_filter.logic')
            if release_title_logic == '0':
                # AND filter
                torrent_list = [i for i in _torrent_list if release_title_filter1 in i['release_title'] and release_title_filter2 in i['release_title'] and release_title_filter3 in i['release_title'] and release_title_filter4 in i['release_title'] and release_title_filter5 in i['release_title']]
            if release_title_logic == '1':
                # OR filter
                torrent_list = [i for i in _torrent_list if (release_title_filter1 != "" and release_title_filter1 in i['release_title']) or (release_title_filter2 != "" and release_title_filter2 in i['release_title']) or (release_title_filter3 != "" and release_title_filter3 in i['release_title']) or (release_title_filter4 != "" and release_title_filter4 in i['release_title']) or (release_title_filter5 != "" and release_title_filter5 in i['release_title'])]

        # Get the value of the 'sourcesort.menu' setting
        sort_option = control.getSetting('general.sourcesort')

        # Apply sorting based on the selected option
        if sort_option == 'Sub':
            # Sort by dubs (modified code)
            torrent_list = sorted(torrent_list, key=lambda x: x['lang'] == 0, reverse=True)
            embed_list = sorted(embed_list, key=lambda x: x['lang'] == 0, reverse=True)
        elif sort_option == 'Dub':
            # Sort by subs (original code)
            torrent_list = sorted(torrent_list, key=lambda x: x['lang'] > 0, reverse=True)
            embed_list = sorted(embed_list, key=lambda x: x['lang'] > 0, reverse=True)
        else:
            # No sorting needed (default behavior)
            pass

        prioritize_dualaudio = False
        prioritize_multisubs = False
        prioritize_batches = False
        prioritize_season = False
        prioritize_part = False
        prioritize_episode = False 
        prioritize_consistently = False
        keyword = None

        if control.getSetting('general.sortsources') == '0':  # Torrents selected
            prioritize_dualaudio = control.getSetting('general.prioritize_dualaudio') == 'true'
            prioritize_multisubs = control.getSetting('general.prioritize_multisubs') == 'true'
            prioritize_batches = control.getSetting('general.prioritize_batches') == 'true'
            prioritize_consistently = control.getSetting('consistent.torrentInspection') == 'true'
   
            if prioritize_consistently:
                prioritize_season = control.getSetting('consistent.prioritize_season') == 'true'
                prioritize_part = control.getSetting('consistent.prioritize_part') == 'true'
                prioritize_episode = control.getSetting('consistent.prioritize_episode') == 'true'
            else:
                prioritize_season = control.getSetting('general.prioritize_season') == 'true'
                prioritize_part = control.getSetting('general.prioritize_part') == 'true'
                prioritize_episode = control.getSetting('general.prioritize_episode') == 'true'
            
            from itertools import chain, combinations
    
            # Define the order of the keys
            key_order = ['SEASON', 'PART', 'EPISODE', 'DUAL-AUDIO', 'MULTI-SUBS', 'BATCH']
    
            # Define the user's selected priorities
            selected_priorities = [prioritize_season, prioritize_part, prioritize_episode, prioritize_dualaudio, prioritize_multisubs, prioritize_batches]
    
            # Generate all possible combinations of the selected priorities
            selected_combinations = list(chain(*map(lambda x: combinations([key for key, selected in zip(key_order, selected_priorities) if selected], x), range(0, len(selected_priorities)+1))))
    
            # Initialize keyword as an empty list
            keyword = []
            
            for combination in selected_combinations:
                # Skip the empty combination
                if not combination:
                    continue
            
                # Join the keys in the combination with '_OR_' and append to the keyword list
                keyword.append('_OR_'.join(combination))
            
            # Keep only the last combination in the keyword list
            keyword = [keyword[-1]] if keyword else []
            
            # Convert the keyword list to a string
            keyword = ' '.join(keyword) if keyword else ''

        debrid_priorities = self.debrid_priority()

        if keyword:
            # Filter the torrent list based on the keyword
            torrent_list_filtered = [i for i in torrent_list if keyword in i['info']]
            torrent_list_not_filtered = [i for i in torrent_list if keyword not in i['info']]

            # Sort and append torrents based on resolution and debrid provider
            for resolution in resolutions:
                for debrid in self.debrid_priority():
                    for torrent in torrent_list_filtered:
                        if debrid['slug'] == torrent['debrid_provider'] and torrent['quality'] == resolution:
                            sortedList.append(torrent)
                    for torrent in torrent_list_not_filtered:
                        if debrid['slug'] == torrent['debrid_provider'] and torrent['quality'] == resolution:
                            sortedList.append(torrent)
                # Append files from embed_list based on resolution
                for file in embed_list:
                    if file['quality'] == resolution:
                        sortedList.append(file)
        else:
            # Sort Souces Medthod: Torrents
            # Torrents: Sub or Dub
            # - Helps Gets Torrents
            if sort_method == 0 or sort_method == 2:
                for resolution in resolutions:
                    for debrid in debrid_priorities:
                        for torrent in torrent_list:
                            if debrid['slug'] == torrent['debrid_provider']:
                                if torrent['quality'] == resolution:
                                    sortedList.append(torrent)

            # Sort Souces Medthod: Embeds
            # Emebeds: Dual Audio or Dub
            # - Helps Gets Embeds
            if sort_method == 1 or sort_method == 2:
                for resolution in resolutions:
                    for file in embed_list:
                        if file['quality'] == resolution:
                            sortedList.append(file)

            # Sort Souces Medthod: Embeds
            # Torrents: Dual Audio
            # - Helps Gets Torrents
            if sort_method == 1:
                for resolution in resolutions:
                    for debrid in debrid_priorities:
                        for torrent in torrent_list:
                            if torrent['debrid_provider'] == debrid['slug']:
                                if torrent['quality'] == resolution:
                                    sortedList.append(torrent)

            # Sort Souces Medthod: Torrents
            # Emebeds: Sub
            # - Helps Gets Embeds
            if sort_method == 0:
                for resolution in resolutions:
                    for file in embed_list:
                        if file['quality'] == resolution:
                            sortedList.append(file)

        if control.getSetting('torrent.disable265') == 'true':
            sortedList = [i for i in sortedList if 'HEVC' not in i['info']]

        if control.getSetting('torrent.batch') == 'true':
            sortedList = [i for i in sortedList if 'BATCH' not in i['info']]

        preferences = control.getSetting("general.source")
        lang_preferences = {'Dub': 0, 'Sub': 2}
        if preferences in lang_preferences:
            sortedList = [i for i in sortedList if i['lang'] != lang_preferences[preferences]]

        return sortedList

    @staticmethod
    def colorNumber(number):
        return control.colorString(number, 'green') if int(number) > 0 else control.colorString(number, 'red')

    def updateProgress(self):

        list1 = [
            len([i for i in self.nyaaSources if i['quality'] == '4K']),
            len([i for i in self.nyaaSources if i['quality'] == '1080p']),
            len([i for i in self.nyaaSources if i['quality'] == '720p']),
            len([i for i in self.nyaaSources if i['quality'] == 'NA']),
        ]

        self.torrents_qual_len = list1

        list2 = [
            len([i for i in self.embedSources if i['quality'] == '4K']),
            len([i for i in self.embedSources if i['quality'] == '1080p']),
            len([i for i in self.embedSources if i['quality'] == '720p']),
            len([i for i in self.embedSources if i['quality'] == 'NA']),
        ]

        self.hosters_qual_len = list2

        return
