import re
from concurrent.futures import ThreadPoolExecutor

from resources.lib.ui import source_utils, control
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.debrid import real_debrid, premiumize, all_debrid, torbox


class Sources(BrowserBase):
    def __init__(self):
        self.cloud_files = []
        self.threads = []

    def get_sources(self, query, mal_id, episode, season=None):
        debrid = control.enabled_debrid()
        cloud = control.enabled_cloud()
        tasks = []
        if debrid.get('realdebrid') and cloud.get('realdebrid'):
            tasks.append(self.rd_cloud_inspection)
        if debrid.get('premiumize') and cloud.get('premiumize'):
            tasks.append(self.premiumize_cloud_inspection)
        if debrid.get('alldebrid') and cloud.get('alldebrid'):
            tasks.append(self.alldebrid_cloud_inspection)
        if debrid.get('torbox') and cloud.get('torbox'):
            tasks.append(self.torbox_cloud_inspection)

        if tasks:
            max_workers = max(1, min(control.max_threads or 1, len(tasks)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(task, query, mal_id, episode, season) for task in tasks]
                for future in futures:
                    future.result()
        return self.cloud_files

    def rd_cloud_inspection(self, query, mal_id, episode, season=None):
        api = real_debrid.RealDebrid()
        torrents = api.list_torrents()
        torrents = source_utils.filter_sources('realdebrid', torrents, mal_id, season, episode)
        filenames = [re.sub(r'\[.*?]\s*', '', i['filename'].replace(',', '')) for i in torrents]
        resp = source_utils.get_fuzzy_match(query, filenames)

        for i in resp:
            torrent = torrents[i]
            torrent_info = api.torrentInfo(torrent['id'])
            torrent_files = [selected for selected in torrent_info['files'] if selected['selected'] == 1]

            if len(torrent_files) > 1 and len(torrent_info['links']) == 1:
                continue

            if not any(source_utils.is_file_ext_valid(tor_file['path'].lower()) for tor_file in torrent_files):
                continue

            self.cloud_files.append(
                {
                    'quality': source_utils.getQuality(torrent['filename']),
                    'lang': source_utils.getAudio_lang(torrent['filename']),
                    'channel': source_utils.getAudio_channel(torrent['filename']),
                    'sub': source_utils.getSubtitle_lang(torrent['filename']),
                    'hash': torrent_info['links'],
                    'provider': 'Cloud',
                    'type': 'cloud',
                    'release_title': torrent['filename'],
                    'info': source_utils.getInfo(torrent['filename']),
                    'debrid_provider': 'Real-Debrid',
                    'size': source_utils.get_size(torrent['bytes']),
                    'seeders': 0,
                    'byte_size': torrent['bytes'],
                    'torrent': torrent,
                    'torrent_files': torrent_files,
                    'torrent_info': torrent_info,
                    'episode': episode
                }
            )

    def premiumize_cloud_inspection(self, query, mal_id, episode, season=None):
        cloud_items = premiumize.Premiumize().list_folder()
        cloud_items = source_utils.filter_sources('premiumize', cloud_items, mal_id, season, episode)
        filenames = [re.sub(r'\[.*?]\s*', '', i['name'].replace(',', '')) for i in cloud_items]
        resp = source_utils.get_fuzzy_match(query, filenames)

        for i in resp:
            torrent = cloud_items[i]
            filename = re.sub(r'\[.*?]', '', torrent['name']).lower()

            if torrent['type'] == 'file':
                if not source_utils.is_file_ext_valid(filename):
                    continue

            self.cloud_files.append(
                {
                    'id': torrent['id'],
                    'torrent_type': torrent['type'],
                    'quality': source_utils.getQuality(torrent['name']),
                    'lang': source_utils.getAudio_lang(torrent['name']),
                    'channel': source_utils.getAudio_channel(torrent['name']),
                    'sub': source_utils.getSubtitle_lang(torrent['name']),
                    'hash': torrent.get('link', ''),
                    'provider': 'Cloud',
                    'type': 'cloud',
                    'release_title': torrent['name'],
                    'info': source_utils.getInfo(torrent['name']),
                    'debrid_provider': 'Premiumize',
                    'size': source_utils.get_size(int(torrent.get('size', 0))),
                    'seeders': 0,
                    'byte_size': int(torrent.get('size', 0)),
                    'episode': episode
                }
            )

    def torbox_cloud_inspection(self, query, mal_id, episode, season=None):
        cloud_items = torbox.TorBox().list_torrents()
        cloud_items = source_utils.filter_sources('torbox', cloud_items, mal_id, season, episode)
        filenames = [re.sub(r'\[.*?]\s*', '', i['name'].replace(',', '')) for i in cloud_items]
        resp = source_utils.get_fuzzy_match(query, filenames)

        for i in resp:
            torrent = cloud_items[i]
            if not torrent['cached'] or not torrent['download_finished'] or len(torrent['files']) < 1:
                continue
            if not any(source_utils.is_file_ext_valid(tor_file['short_name'].lower()) for tor_file in torrent['files']):
                continue

            self.cloud_files.append(
                {
                    'id': torrent['id'],
                    'quality': source_utils.getQuality(torrent['name']),
                    'lang': source_utils.getAudio_lang(torrent['name']),
                    'channel': source_utils.getAudio_channel(torrent['name']),
                    'sub': source_utils.getSubtitle_lang(torrent['name']),
                    'hash': torrent['files'],
                    'provider': 'Cloud',
                    'type': 'cloud',
                    'release_title': torrent['name'],
                    'info': source_utils.getInfo(torrent['name']),
                    'debrid_provider': 'TorBox',
                    'size': source_utils.get_size(torrent['size']),
                    'seeders': 0,
                    'byte_size': torrent['size'],
                    'torrent': torrent,
                    'episode': episode
                }
            )

    def alldebrid_cloud_inspection(self, query, mal_id, episode, season=None):
        api = all_debrid.AllDebrid()
        torrents = api.list_torrents()['links']
        torrents = source_utils.filter_sources('alldebrid', torrents, mal_id, season, episode)
        filenames = [re.sub(r'\[.*?]\s*', '', i['filename'].replace(',', '')) for i in torrents]
        resp = source_utils.get_fuzzy_match(query, filenames)

        for i in resp:
            torrent = torrents[i]
            torrent_info = api.link_info(torrent['link'])
            torrent_files = torrent_info['infos']

            if len(torrent_files) > 1 and len(torrent_info['links']) == 1:
                continue

            if not any(source_utils.is_file_ext_valid(tor_file['filename'].lower()) for tor_file in torrent_files):
                continue

            url = api.resolve_hoster(torrent['link'])
            self.cloud_files.append(
                {
                    'quality': source_utils.getQuality(torrent['filename']),
                    'lang': source_utils.getAudio_lang(torrent['filename']),
                    'channel': source_utils.getAudio_channel(torrent['filename']),
                    'sub': source_utils.getSubtitle_lang(torrent['filename']),
                    'hash': url,
                    'provider': 'Cloud',
                    'type': 'cloud',
                    'release_title': torrent['filename'],
                    'info': source_utils.getInfo(torrent['filename']),
                    'debrid_provider': 'Alldebrid',
                    'size': source_utils.get_size(torrent['size']),
                    'seeders': 0,
                    'byte_size': int(torrent['size']),
                    'episode': episode
                }
            )
