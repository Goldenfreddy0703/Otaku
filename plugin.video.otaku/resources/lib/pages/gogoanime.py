import itertools
import json
import pickle
import re

from functools import partial
from bs4 import BeautifulSoup
from resources.lib.ui import control, client, database, source_utils, utils
from resources.lib.ui.BrowserBase import BrowserBase


def get_backup(mal_id, source):
    params = {
        "type": "myanimelist",
        "id": mal_id
    }
    result = client.get("https://arm2.vercel.app/api/kaito-b", params=params)
    if result:
        result = result.json()
        result = result.get('Pages', {}).get(source, {})
    return result


class Sources(BrowserBase):
    _BASE_URL = 'https://anitaku.bz' if control.getBool('provider.gogoalt') else 'https://gogoanime3.cc/'

    def get_sources(self, mal_id, episode):
        show = database.get_show(mal_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)
        slugs = []

        headers = {'Referer': self._BASE_URL}
        params = {
            'keyword': title,
            'id': -1,
            'link_web': self._BASE_URL
        }
        r = database.get(
            self._get_request,
            8,
            'https://ajax.gogocdn.net/site/loadAjaxSearch',
            data=params,
            headers=headers
        )
        r = json.loads(r).get('content')

        if not r and ':' in title:
            title = title.split(':')[0]
            params.update({'keyword': title})
            r = database.get(
                self._get_request,
                8,
                'https://ajax.gogocdn.net/site/loadAjaxSearch',
                data=params,
                headers=headers
            )
            r = json.loads(r).get('content')

        soup = BeautifulSoup(r, 'html.parser')
        items = soup.find_all('div', {'class': 'list_search_ajax'})
        if len(items) == 1:
            slugs = [items[0].find('a').get('href').split('/')[-1]]
        else:
            slugs = [
                item.find('a').get('href').split('/')[-1]
                for item in items
                if ((item.a.text.strip() + '  ').lower()).startswith((title + '  ').lower())
                or ((item.a.text.strip() + '  ').lower()).startswith((title + ' (Dub)  ').lower())
                or ((item.a.text.strip() + '  ').lower()).startswith((title + ' (TV)  ').lower())
                or ((item.a.text.strip() + '  ').lower()).startswith((title + ' (TV) (Dub)  ').lower())
                or ((item.a.text.strip().replace(' - ', ' ') + '  ').lower()).startswith((title + '  ').lower())
                or (item.a.text.strip().replace(':', ' ') + '   ').startswith(title + '   ')
            ]
        if not slugs:
            slugs = database.get(get_backup, 168, mal_id, 'Gogoanime')
            if not slugs:
                return []
        slugs = list(slugs.keys()) if isinstance(slugs, dict) else slugs

        # Process slugs in parallel for faster scraping
        control.log(f"GogoAnime: Processing {len(slugs)} slugs in parallel")
        mapfunc = partial(self._process_gogo, show_id=mal_id, episode=episode)
        all_results = utils.parallel_process(slugs, mapfunc)
        all_results = list(itertools.chain(*all_results))
        return all_results

    def _process_gogo(self, slug, show_id, episode):
        if slug.startswith('http'):
            slug = slug.split('/')[-1]
        lang = 'dub' if '-dub' in slug else 'sub'
        url = "{0}{1}-episode-{2}".format(self._BASE_URL, slug, episode)
        headers = {'Referer': self._BASE_URL}
        title = (slug.replace('-', ' ')).title() + ' - Ep {0}'.format(episode)
        r = database.get(
            self._send_request,
            8,
            url,
            headers=headers
        )

        if not r:
            url = '{0}category/{1}'.format(self._BASE_URL, slug)
            html = database.get(
                self._send_request,
                8,
                url,
                headers=headers
            )
            mid = re.findall(r'value="([^"]+)"\s*id="movie_id"', html)
            if mid:
                params = {'ep_start': episode,
                          'ep_end': episode,
                          'id': mid[0],
                          'alias': slug}
                eurl = 'https://ajax.gogocdn.net/ajax/load-list-episode'
                r2 = self._get_request(eurl, data=params, headers=headers)
                soup2 = BeautifulSoup(r2, 'html.parser')
                eslug = soup2.find('a')
                if eslug:
                    eslug = eslug.get('href').strip()
                    url = "{0}{1}".format(self._BASE_URL[:-1], eslug)
                    r = self._send_request(url, headers=headers)

        soup = BeautifulSoup(r, 'html.parser')
        sources = []
        elements = soup.select('.anime_muti_link > ul > li')
        control.log(f"GogoAnime: Found {len(elements)} servers for episode {episode}")

        for element in elements:
            server = element.get('class')[0]
            link = element.a.get('data-video')

            if server.lower() in self.embeds():
                if link.startswith('//'):
                    link = 'https:' + link

                source = {
                    'release_title': title,
                    'hash': link,
                    'type': 'embed',
                    'quality': 0,
                    'debrid_provider': '',
                    'provider': 'gogo',
                    'size': 'NA',
                    'seeders': 0,
                    'byte_size': 0,
                    'info': [f"{server.upper()} {lang.upper()}"],
                    'lang': 3 if lang == 'dub' else 2,
                    'channel': source_utils.getAudio_channel(title),
                    'sub': source_utils.getSubtitle_lang(title),
                }
                sources.append(source)
                control.log(f"GogoAnime: Found source from server '{server}'")
                # Early exit - we found a working source, no need to check more servers
                break

        return sources
