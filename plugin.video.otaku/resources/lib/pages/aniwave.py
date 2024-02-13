import base64
import codecs
import json
import pickle
import re
import six

from bs4 import BeautifulSoup, SoupStrainer
from six.moves import urllib_parse
from resources.lib.ui import control, database
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.indexers.malsync import MALSYNC


class sources(BrowserBase):
    _BASE_URL = 'https://aniwave.to/'
    EKEY = 'ysJhV6U27FVIjjuk'
    DKEY = 'hlPeNwkncH0fq9so'
    CHAR_SUBST_OFFSETS = (-3, 3, -4, 2, -2, 5, 4, 5)

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)

        all_results = []
        srcs = ['sub', 'dub']
        if control.getSetting('general.source') == 'Sub':
            srcs.remove('dub')
        elif control.getSetting('general.source') == 'Dub':
            srcs.remove('sub')

        items = MALSYNC().get_slugs(anilist_id=anilist_id, site='9anime')
        if not items:
            headers = {'Referer': self._BASE_URL}
            params = {'keyword': title}
            r = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'ajax/anime/search',
                data=params,
                headers=headers,
                XHR=True
            )
            if not r and ':' in title:
                title = title.split(':')[0]
                params.update({'keyword': title})
                r = database.get(
                    self._get_request,
                    8,
                    self._BASE_URL + 'ajax/anime/search',
                    data=params,
                    headers=headers,
                    XHR=True
                )
            if not r:
                return all_results

            r = json.loads(r)
            r = BeautifulSoup(r.get('html') or r.get('result', {}).get('html'), "html.parser")
            sitems = r.find_all('a', {'class': 'item'})
            if sitems:
                if title[-1].isdigit():
                    items = [urllib_parse.urljoin(self._BASE_URL, x.get('href'))
                             for x in sitems
                             if title.lower() in x.find('div', {'class': 'name'}).get('data-jp').lower()]
                else:
                    items = [urllib_parse.urljoin(self._BASE_URL, x.get('href'))
                             for x in sitems
                             if (title.lower() + '  ') in (x.find('div', {'class': 'name'}).get('data-jp').lower() + '  ')]

        if items:
            slug = items[0]
            all_results = self._process_aw(slug, title=title, episode=episode, langs=srcs)

        return all_results

    def _process_aw(self, slug, title, episode, langs):
        sources = []
        headers = {'Referer': self._BASE_URL}
        r = database.get(
            self._get_request, 8,
            slug, headers=headers
        )
        sid = re.search(r'id="watch-main.+?data-id="([^"]+)', r)
        if not sid:
            return sources

        sid = sid.group(1)
        vrf = self.generate_vrf(sid)
        params = {'vrf': vrf}
        r = database.get(
            self._get_request, 8,
            '{0}ajax/episode/list/{1}'.format(self._BASE_URL, sid),
            headers=headers, data=params,
            XHR=True
        )
        res = json.loads(r).get('result')

        elink = SoupStrainer('div', {'class': re.compile('^episodes')})
        ediv = BeautifulSoup(res, "html.parser", parse_only=elink)
        items = ediv.find_all('a')
        e_id = [x.get('data-ids') for x in items if x.get('data-num') == episode]
        if e_id:
            e_id = e_id[0]
            vrf = self.generate_vrf(e_id)
            params = {'vrf': vrf}
            r = database.get(
                self._get_request, 8,
                '{0}ajax/server/list/{1}'.format(self._BASE_URL, e_id),
                data=params, headers=headers,
                XHR=True
            )
            eres = json.loads(r).get('result')
            for lang in langs:
                elink = SoupStrainer('div', {'data-type': lang})
                sdiv = BeautifulSoup(eres, "html.parser", parse_only=elink)
                srcs = sdiv.find_all('li')
                for src in srcs:
                    edata_id = src.get('data-link-id')
                    edata_name = src.text
                    if edata_name.lower() in control.enabled_embeds():
                        vrf = self.generate_vrf(edata_id)
                        params = {'vrf': vrf}
                        r = self._get_request(
                            '{0}ajax/server/{1}'.format(self._BASE_URL, edata_id),
                            data=params,
                            headers=headers,
                            XHR=True
                        )
                        resp = json.loads(r).get('result')
                        slink = self.decrypt_vrf(resp.get('url'))

                        skip = {}
                        if resp.get('skip_data'):
                            skip_data = json.loads(self.decrypt_vrf(resp.get('skip_data')))
                            intro = skip_data.get('intro')
                            if intro:
                                skip.update({'intro': {'start': intro[0], 'end': intro[1]}})
                            outro = skip_data.get('outro')
                            if outro:
                                skip.update({'outro': {'start': outro[0], 'end': outro[1]}})

                        source = {
                            'release_title': '{0} - Ep {1}'.format(title, episode),
                            'hash': slink,
                            'type': 'embed',
                            'quality': 'EQ',
                            'debrid_provider': '',
                            'provider': 'aniwave',
                            'size': 'NA',
                            'info': ['DUB' if lang == 'dub' else 'SUB', edata_name],
                            'lang': 2 if lang == 'dub' else 0,
                            'skip': skip
                        }
                        sources.append(source)
        return sources

    @staticmethod
    def arc4(key, data):
        l_key = len(key)
        S = [i for i in range(256)]
        j = 0
        out = bytearray()
        app = out.append

        for i in range(256):
            j = (j + S[i] + key[i % l_key]) % 256
            S[i], S[j] = S[j], S[i]

        i = j = 0
        for c in data:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            app(c ^ S[(S[i] + S[j]) % 256])

        return out

    @staticmethod
    def vrf_shift(t, offset=CHAR_SUBST_OFFSETS):
        o = ''
        for s in range(len(t)):
            o += chr(ord(t[s]) + offset[s % 8])
        return o

    def generate_vrf(self, content_id, key=EKEY):
        vrf = self.arc4(six.b(key), six.b(urllib_parse.quote(content_id)))
        vrf = base64.urlsafe_b64encode(vrf)
        vrf = six.ensure_str(base64.b64encode(vrf))
        vrf = self.vrf_shift(vrf)
        vrf = six.ensure_str(base64.b64encode(six.b(vrf)))
        vrf = codecs.encode(vrf, 'rot_13')
        return vrf.replace('/', '_').replace('+', '-')

    def decrypt_vrf(self, text, key=DKEY):
        data = self.arc4(six.b(key), base64.urlsafe_b64decode(six.b(text)))
        data = urllib_parse.unquote(data.decode())
        return data
