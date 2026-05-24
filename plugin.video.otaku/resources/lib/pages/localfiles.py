import os
import re
from concurrent.futures import ThreadPoolExecutor

from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui import source_utils, control

PATH = control.getSetting('folder.location')


class Sources(BrowserBase):
    def __init__(self):
        self.local_files = []

    @staticmethod
    def _build_local_source(file_info, episode):
        filename = re.sub(r'\[.*?]', '', file_info['name']).lower()
        if not source_utils.is_file_ext_valid(filename):
            return None

        full_path = file_info['path']
        file_size = os.path.getsize(full_path)
        return {
            'release_title': file_info['name'],
            'hash': full_path,
            'provider': 'Local',
            'type': 'local',
            'quality': source_utils.getQuality(file_info['name']),
            'debrid_provider': 'Local-Debrid',
            'episode': episode,
            'size': source_utils.get_size(file_size),
            'seeders': 0,
            'byte_size': file_size,
            'info': source_utils.getInfo(file_info['name']),
            'lang': source_utils.getAudio_lang(file_info['name']),
            'channel': source_utils.getAudio_channel(file_info['name']),
            'sub': source_utils.getSubtitle_lang(file_info['name'])
        }

    def get_sources(self, query, mal_id, episode, season=None):
        filenames = []
        for root, dirs, files in os.walk(PATH):
            for file in files:
                if source_utils.is_file_ext_valid(file):
                    full_path = os.path.join(root, file)
                    filenames.append({
                        'name': file,
                        'path': full_path
                    })

        filenames = source_utils.filter_sources('local', filenames, mal_id, season, episode)
        clean_filenames = [re.sub(r'\[.*?]\s*', '', i['name'].replace(',', '')) for i in filenames]
        resp = source_utils.get_fuzzy_match(query, clean_filenames)
        match_files = [filenames[i] for i in resp]
        max_workers = max(1, min(control.max_threads or 1, len(match_files) or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            sources = list(executor.map(lambda file_info: self._build_local_source(file_info, episode), match_files))
        self.local_files.extend([source for source in sources if source is not None])
        return self.local_files
