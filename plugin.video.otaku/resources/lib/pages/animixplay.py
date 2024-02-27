import itertools
import pickle
import re
from functools import partial

from bs4 import BeautifulSoup, SoupStrainer
from six.moves import urllib_parse
from resources.lib.ui import control, database, client
from resources.lib.ui.BrowserBase import BrowserBase


class sources(BrowserBase):
    _BASE_URL = 'https://animixplay.fun/' if control.getSetting('provider.animixalt') == 'true' else 'https://animixplay.best/'

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('ename') or kodi_meta.get('name')
        title = self._clean_title(title)

        headers = {'Origin': self._BASE_URL[:-1],
                   'Referer': self._BASE_URL}
        r = database.get(
            client.request,
            8,
            self._BASE_URL + 'search',
            params={'keyword': title},
            headers=headers
        )

        soup = BeautifulSoup(r, 'html.parser')
        items = soup.find_all('div', {'class': re.compile('^post')})
        slugs = []

        for item in items:
            ititle = item.find('h5')
            if ititle:
                ititle = ititle.text.strip()
                if (ititle.lower() + '  ').startswith(title.lower() + '  '):
                    slugs.append(item.find('a').get('href'))
        if not slugs:
            if len(items) > 1:
                slugs = [items[0].find('a').get('href')]
        all_results = []
        if slugs:
            slugs = list(slugs.keys()) if isinstance(slugs, dict) else slugs
            mapfunc = partial(self._process_animixplay, title=title, episode=episode)
            all_results = list(map(mapfunc, slugs))
            all_results = list(itertools.chain(*all_results))
        return all_results

    def _process_animixplay(self, slug, title, episode):
        sources = []
        r = database.get(client.request, 8, slug, referer=self._BASE_URL)
        eurl = re.search(r'id="showstreambtn"\s*href="([^"]+)', r)
        if eurl:
            eurl = eurl.group(1)
            resp = database.get(client.request, 8, eurl, referer=self._BASE_URL, output='extended')
            s = resp[0]
            cookie = resp[4]
            referer = urllib_parse.urljoin(eurl, '/')
            if episode:
                esurl = re.findall(r'src="(/ajax/stats.js[^"]+)', s)[0]
                esurl = urllib_parse.urljoin(eurl, esurl)
                epage = database.get(client.request, 8, esurl, referer=eurl)
                soup = BeautifulSoup(epage, "html.parser")
                epurls = soup.find_all('a', {'class': 'playbutton'})
                ep_not_found = True
                for epurl in epurls:
                    try:
                        if int(epurl.text) == int(episode):
                            ep_not_found = False
                            epi_url = epurl.get('href')
                            resp = database.get(client.request, 8, epi_url, referer=eurl, output='extended')
                            cookie = resp[4]
                            s = resp[0]
                            break
                    except:
                        continue
                if ep_not_found:
                    return sources

            csrf_token = re.search(r'name="csrf-token"\s*content="([^"]+)', s)
            if csrf_token:
                csrf_token = csrf_token.group(1)
            else:
                return sources
            mlink = SoupStrainer('div', {'class': re.compile('sv_container$')})
            mdiv = BeautifulSoup(s, "html.parser", parse_only=mlink)
            mitems = mdiv.find_all('li')
            for mitem in mitems:
                if any(x in mitem.text.lower() for x in control.enabled_embeds()):
                    type_ = 'direct'
                    server = mitem.a.get('data-name')
                    qual = mitem.a.get('title')
                    if '1080p' in qual:
                        qual = '1080p'
                    elif 'HD' in qual:
                        qual = '720p'
                    else:
                        qual = 'NA'
                    lang = 2 if mitem.a.get('id').endswith('dub') else 0

                    data = {
                        'name_server': server,
                        'data_play': mitem.a.get('data-play'),
                        'id': mitem.a.get('data-id'),
                        'server_id': mitem.a.get('data-serverid'),
                        'expired': mitem.a.get('data-expired')
                    }
                    headers = {
                        'Origin': referer[:-1],
                        'X-CSRF-TOKEN': csrf_token
                    }
                    r = client.request(
                        urllib_parse.urljoin(eurl, '/ajax/embed'),
                        post=data,
                        headers=headers,
                        XHR=True,
                        referer=eurl,
                        cookie=cookie
                    )
                    embed_url = urllib_parse.urljoin(eurl, re.findall(r'<iframe.+?src="([^"]+)', r)[0])
                    subs = ''
                    slink = ''
                    s = client.request(embed_url, referer=eurl)
                    sdiv = re.search(r'<source.+?src="([^"]+)', s)
                    if sdiv:
                        slink = sdiv.group(1)
                    else:
                        sdiv = re.search(r'sources:.+?file:\s*"([^"]+)', s, re.DOTALL)
                        if sdiv:
                            slink = sdiv.group(1)
                    subdiv = re.search(r'captions:\s*\[.+?file:\s*"([^"]+)', s, re.DOTALL)
                    if subdiv:
                        subs = subdiv.group(1)

                    if slink:
                        source = {
                            'release_title': '{0} Ep{1}'.format(title, episode),
                            'hash': slink,  # + '|Referer={0}&Origin={1}&User-Agent=iPad'.format(referer, referer[:-1]),
                            'type': type_,
                            'quality': qual,
                            'debrid_provider': '',
                            'provider': 'animix',
                            'size': 'NA',
                            'info': [server, 'DUB' if lang == 2 else 'SUB'],
                            'lang': lang
                        }

                        if subs:
                            source.update({'subs': [{'url': subs, 'lang': 'English'}]})

                        sources.append(source)

        return sources
