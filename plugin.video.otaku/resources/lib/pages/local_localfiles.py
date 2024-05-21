import os
import re

from functools import partial
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui import source_utils, control

PATH = control.getSetting('download.location')


class sources(BrowserBase):

    def get_sources(self, query, anilist_id, episode):
        title1, title2 = self._clean_title(query).lower().split('|')
        first1 = self.get_title_clean(title1).split(' ')[0]
        first2 = self.get_title_clean(title2).split(' ')[0]

        files = [f for f in os.listdir(PATH) if os.path.isfile(os.path.join(PATH, f)) and source_utils.is_file_ext_valid(f)]
        match_files = []
        for f in files:
            filename_ = re.sub(r'\[.*?]', '', f.lower())
            filename = filename_.replace('-', '')
            if (first1 in filename) or (first2 in filename) and episode in filename:
                match_files.append(f)
        mapfunc = partial(self.process_local_search, episode=episode)
        all_results = list(map(mapfunc, match_files))
        return all_results

    def process_local_search(self, f, episode):
        source = {
            'release_title': f,
            'hash': os.path.join(PATH, f),
            'type': 'local',
            'quality': source_utils.getQuality(f),
            'debrid_provider': 'local_files',
            'provider': 'Local',
            'episode_re': episode,
            'size': self._get_size(os.path.getsize(os.path.join(PATH, f))),
            'info': source_utils.getInfo(f),
            'lang': source_utils.getAudio_lang(f)
        }
        return source

    @staticmethod
    def get_title_clean(title):
        title = title.replace('(', '')
        title = title.replace(')', '')
        title = title.replace('-', '')
        title = f'{title} '
        return title
