import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup, SoupStrainer
from resources.lib.ui import database, source_utils, control
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.endpoints import malsync
from resources.lib.ui import client

_ANIME_SESSION_PATH_RE = re.compile(r'/anime/([^/?#]+)', re.I)


class Sources(BrowserBase):
    _BASE_URL = 'https://animepahe-pw.translate.goog/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp/' if control.getBool('provider.animepahealt') else 'https://animepahe.pw/'

    _headers = {
        'Referer': _BASE_URL,
        'Cookie': '__ddg1_=PZYJSmACHBBQGP6auJU9; __ddg2_=hxAe1bBqtlUhMFik'
    }

    def _build_source(self, item, title, episode, embed_hosts):
        data_src = item.get('data-src') + f'|Referer={self._BASE_URL}'
        if not data_src or not any(host in data_src.lower() for host in embed_hosts):
            return None

        qual = int(item.get('data-resolution'))
        if qual <= 577:
            quality = 1
        elif qual <= 721:
            quality = 2
        elif qual <= 1081:
            quality = 3
        else:
            quality = 0

        return {
            'release_title': '{0} - Ep {1}'.format(title, episode),
            'hash': data_src,
            'type': 'embed',
            'quality': quality,
            'debrid_provider': '',
            'provider': 'animepahe',
            'size': 'NA',
            'seeders': 0,
            'byte_size': 0,
            'info': [source_utils.get_embedhost(data_src) + (' DUB' if item.get('data-audio').lower() == 'eng' else ' SUB')],
            'lang': 3 if item.get('data-audio') == 'eng' else 2,
            'channel': 3,
            'sub': 1
        }

    @staticmethod
    def _session_slug_from_animepahe_url(page_url):
        """Extract API session id from a canonical AnimePahe page URL (/anime/{session})."""
        if not page_url:
            return None
        match = _ANIME_SESSION_PATH_RE.search(urllib.parse.urlparse(page_url).path)
        return match.group(1) if match else None

    def _resolve_session_from_malsync(self, mal_id):
        """
        MAL Sync stores legacy links like https://animepahe.com/a/6231; the live site
        redirects to https://animepahe.pw/anime/{uuid}. Follow redirects and return that
        session slug for the API (m=release&id=...).
        """
        for raw in malsync.get_slugs(mal_id, site='animepahe'):
            if not raw:
                continue
            link = raw.strip()
            if link.startswith('//'):
                link = 'https:' + link
            elif link.startswith('/'):
                link = urllib.parse.urljoin(self._BASE_URL, link)
            final = client.request(
                link,
                output='geturl',
                headers=self._headers,
                referer=self._BASE_URL,
            )
            slug = self._session_slug_from_animepahe_url(final)
            if slug:
                return slug
        return None

    def get_sources(self, mal_id, episode):
        title = malsync.get_title(mal_id, site='animepahe')
        if not title:
            return []

        slug = self._resolve_session_from_malsync(mal_id)
        if slug:
            direct = self._process_ap(slug, title=title, episode=episode)
            if direct:
                return direct

        params = {'m': 'search', 'q': title}
        r = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'api',
            data=params,
            headers=self._headers
        )
        try:
            sitems = json.loads(r).get('data')
        except json.JSONDecodeError:
            return []

        if not sitems and ':' in title:
            title = title.split(':')[0]
            params.update({'q': title})
            r = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'api',
                data=params,
                headers=self._headers
            )
            sitems = json.loads(r).get('data')

        all_results = []
        if sitems:
            if title[-1].isdigit():
                items = [x for x in sitems if title.lower() in x.get('title').lower()]
            else:
                items = [x for x in sitems if (title.lower() + '  ') in (x.get('title').lower() + '  ')]
            if not items:
                items = sitems
            if items:
                slug = items[0].get('session')
                all_results = self._process_ap(slug, title=title, episode=episode)
        return all_results

    def _process_ap(self, slug, title, episode):
        sources = []
        e_num = int(episode)
        big_series = e_num > 30
        page = 1
        if big_series:
            page += int(e_num / 30)

        params = {
            'm': 'release',
            'id': slug,
            'sort': 'episode_asc',
            'page': page
        }
        r = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'api',
            data=params,
            headers=self._headers
        )
        r = json.loads(r)
        items = r.get('data')
        items = sorted(items, key=lambda x: x.get('episode'))

        if items[0].get('episode') > 1 and not big_series:
            e_num = e_num + items[0].get('episode') - 1

        items = [x for x in items if x.get('episode') == e_num]
        if items:
            eurl = self._BASE_URL + 'play/' + slug + '/' + items[0].get('session')
            html = self._get_request(eurl, headers=self._headers)
            mlink = SoupStrainer('div', {'id': 'resolutionMenu'})
            mdiv = BeautifulSoup(html, "html.parser", parse_only=mlink)
            items = mdiv.find_all('button')
            embed_hosts = self.embeds()
            max_workers = max(1, min(control.max_threads or 1, len(items)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                parsed = list(executor.map(lambda item: self._build_source(item, title, episode, embed_hosts), items))
            sources.extend([item for item in parsed if item is not None])

        return sources
