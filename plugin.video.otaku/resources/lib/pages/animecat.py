import itertools
import json
import pickle
import re

from functools import partial
from resources.lib.ui import database, source_utils
from resources.lib.ui.BrowserBase import BrowserBase


class sources(BrowserBase):
    _BASE_URL = 'https://animecat.net/'

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)
        headers = {'Referer': self._BASE_URL}
        res = database.get(
            self._get_request,
            8,
            self._BASE_URL,
            headers=headers
        )
        cid = re.findall(r'<script\s*src="[^"]+\?([^"]+)', res)[0]
        sub_items = database.get(
            self._get_request,
            168,
            self._BASE_URL + 'animes-search-vostfr.json?' + cid,
            headers=headers
        )
        sub_items = json.loads(sub_items)
        dub_items = database.get(
            self._get_request,
            168,
            self._BASE_URL + 'animes-search-vf.json?' + cid,
            headers=headers
        )
        dub_items = json.loads(dub_items)

        slugs = []

        if title[-1].isdigit():
            slugs = [(x.get('url'), 'SUB') for x in sub_items if x.get('title_romanji') and title.lower() in x.get('title_romanji').lower()]
            slugs += [(x.get('url'), 'DUB') for x in dub_items if x.get('title_romanji') and title.lower() in x.get('title_romanji').lower()]
        else:
            slugs = [(x.get('url'), 'SUB') for x in sub_items if x.get('title_romanji') and (title.lower() + '  ') in (x.get('title_romanji').lower() + '  ')]
            slugs += [(x.get('url'), 'DUB') for x in dub_items if x.get('title_romanji') and (title.lower() + '  ') in (x.get('title_romanji').lower() + '  ')]
        if not slugs and ':' in title:
            title = title.split(':')[0]
            slugs = [(x.get('url'), 'SUB') for x in sub_items if x.get('title_romanji') and (title.lower() + '  ') in (x.get('title_romanji').lower() + '  ')]
            slugs += [(x.get('url'), 'DUB') for x in dub_items if x.get('title_romanji') and (title.lower() + '  ') in (x.get('title_romanji').lower() + '  ')]

        all_results = []
        if slugs:
            mapfunc = partial(self._process_ac, title=title, episode=episode)
            all_results = list(map(mapfunc, slugs))
            all_results = list(itertools.chain(*all_results))

        return all_results

    def _process_ac(self, slug, title, episode):
        url, lang = slug
        sources = []
        headers = {'Referer': self._BASE_URL}
        res = database.get(
            self._get_request,
            8,
            self._BASE_URL + url[1:],
            headers=headers
        )
        items = re.search(r'var\s*episodes\s*=\s*([^;]+)', res)
        if items:
            items = json.loads(items.group(1))
        e_id = [x.get('url') for x in items if x.get('num') == int(episode)]
        if e_id:
            html = self._get_request(
                self._BASE_URL + e_id[0][1:],
                headers=headers
            )
            slink = re.search(r"video\[\d*\]\s*=\s*'([^']+)", html)
            if slink:
                slink = slink.group(1)
                source = {
                    'release_title': '{0} - Ep {1}'.format(title, episode),
                    'hash': slink,
                    'type': 'embed',
                    'quality': 'EQ',
                    'debrid_provider': '',
                    'provider': 'animecat',
                    'size': 'NA',
                    'info': [lang, source_utils.get_embedhost(slink)],
                    'lang': 2 if lang == 'DUB' else 0
                }
                sources.append(source)

        return sources
