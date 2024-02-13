import itertools
import pickle
import re

from bs4 import BeautifulSoup, SoupStrainer
from functools import partial
from resources.lib.ui import database
from resources.lib.ui.BrowserBase import BrowserBase


class sources(BrowserBase):
    _BASE_URL = 'https://otakuanimess.cc/'

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)
        headers = {'Referer': self._BASE_URL}
        params = {'s': title}
        res = database.get(
            self._get_request,
            8,
            self._BASE_URL,
            data=params,
            headers=headers
        )
        if not res and ':' in title:
            title = title.split(':')[0]
            params.update({'s': title})
            res = database.get(
                self._get_request,
                8,
                self._BASE_URL,
                data=params,
                headers=headers
            )

        mlink = SoupStrainer('div', {'class': re.compile('^SectionBusca')})
        mdiv = BeautifulSoup(res, "html.parser", parse_only=mlink)
        sdivs = mdiv.find_all('div', {'class': 'ultAnisContainerItem'})
        sitems = []
        slugs = []
        for sdiv in sdivs:
            try:
                slug = sdiv.find('a').get('href')
                stitle = sdiv.find('a').get('title')
                lang = 'DUB' if 'dublado' in sdiv.find('div', {'class': 'aniNome'}).text.strip().lower() else 'SUB'
                sitems.append({'title': stitle, 'slug': slug, 'lang': lang})
            except AttributeError:
                pass

        if sitems:
            if title[-1].isdigit():
                slugs = [(x.get('slug'), x.get('lang')) for x in sitems if title.lower() in x.get('title').lower()]
            else:
                slugs = [(x.get('slug'), x.get('lang')) for x in sitems if (title.lower() + '  ') in (x.get('title').lower() + '  ')]
            if not slugs and ':' in title:
                title = title.split(':')[0]
                slugs = [(x.get('slug'), x.get('lang')) for x in sitems if (title.lower() + '  ') in (x.get('title').lower() + '  ')]

        all_results = []
        if slugs:
            mapfunc = partial(self._process_am, title=title, episode=episode)
            all_results = list(map(mapfunc, slugs))
            all_results = list(itertools.chain(*all_results))

        return all_results

    def _process_am(self, slug, title, episode):
        url, lang = slug
        sources = []
        headers = {'Referer': self._BASE_URL}
        res = database.get(
            self._get_request,
            8,
            url,
            headers=headers
        )
        elink = SoupStrainer('div', {'class': 'sectionEpiInAnime'})
        ediv = BeautifulSoup(res, "html.parser", parse_only=elink)
        items = ediv.find_all('a')
        e_id = [x.get('href') for x in items if x.text.split()[-1] == episode]
        if e_id:
            html = self._get_request(e_id[0], headers=headers)
            slink = re.search(r'<source\s*src="([^"]+)', html)
            if not slink:
                elink = re.search(r'<div\s*id="Link".+?href="([^"]+)', html, re.DOTALL)
                if elink:
                    html = self._get_request(elink.group(1), headers=headers)
                    slink = re.search(r'''file:\s*['"]([^'"]+)''', html)
            if slink:
                source = {
                    'release_title': '{0} - Ep {1}'.format(title, episode),
                    'hash': '{0}|Referer={1}'.format(slink.group(1), self._BASE_URL),
                    'type': 'direct',
                    'quality': 'EQ',
                    'debrid_provider': '',
                    'provider': 'otakuanimes',
                    'size': 'NA',
                    'info': [lang],
                    'lang': 2 if lang == 'DUB' else 0
                }
                sources.append(source)

        return sources
