import json
import pickle

from resources.lib.ui import database
from resources.lib.ui.BrowserBase import BrowserBase


class sources(BrowserBase):
    _BASE_URL = 'https://aniplay.co/'

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)

        params = {'query': title}
        res = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'api/anime/advanced-search',
            data=params
        )
        items = json.loads(res)
        all_results = []
        if items:

            ids = [
                item.get("id") for item in items
                if any(
                    "https://anilist.co/anime/{}".format(anilist_id) in website["url"]
                    for website in item.get("listWebsites", [])
                )
            ]

            all_results = self._process_al(ids, title=title, episode=episode)

        return all_results

    def _process_al(self, ids, title, episode):
        sources = []

        for id in ids:
            url = '{0}api/anime/{1}'.format(
                self._BASE_URL, id
            )

            res = database.get(
                self._get_request,
                8,
                url
            )

            lang = "DUB" if "(ITA)" in json.loads(res).get('title') else "SUB"

            items = json.loads(res).get('episodes')
            if (items):
                e_id = [x["id"] for x in items if str(x.get('episodeNumber')) == str(episode)]

            else:
                items = json.loads(res).get('seasons')
                season_id = next(
                    season["id"] for season in sorted(items, key=lambda x: -x["episodeStart"])
                    if int(episode) >= int(season["episodeStart"])
                )
                url = '{0}api/anime/{1}/season/{2}'.format(
                    self._BASE_URL, id, season_id
                )
                res = database.get(
                    self._get_request,
                    8,
                    url
                )
                items = json.loads(res)
                e_id = [x["id"] for x in items if str(x.get('episodeNumber')) == str(episode)]

            if e_id:
                url = '{0}api/episode/{1}'.format(
                    self._BASE_URL, e_id[0]
                )
                res = database.get(
                    self._get_request,
                    8,
                    url
                )
                slink = json.loads(res).get('videoUrl')
                source = {
                    'release_title': '{0} - Ep {1}'.format(title, episode),
                    'hash': slink,
                    'type': 'direct',
                    'quality': 'EQ',
                    'debrid_provider': '',
                    'provider': 'aniplay',
                    'size': 'NA',
                    'info': [lang],
                    'lang': 2 if lang == 'DUB' else 0
                }
                sources.append(source)

        return sources
