import base64
import codecs
import json
import pickle
import re
import urllib.parse

from bs4 import BeautifulSoup, SoupStrainer
from resources.lib.ui import control, database, utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://aniwave.se/'
    EKEY = "ysJhV6U27FVIjjuk"
    DKEY = "hlPeNwkncH0fq9so"
    CHAR_SUBST_OFFSETS = (-3, 3, -4, 2, -2, 5, 4, 5)

    def get_sources(self, mal_id, episode):
        show = database.get_show(mal_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)

        all_results = []
        items = []
        srcs = ['sub', 'dub', 's-sub']
        if control.getInt('general.source') == 1:
            srcs.remove('dub')
        elif control.getInt('general.source') == 2:
            srcs.remove('sub')
            srcs.remove('s-sub')

        headers = {'Referer': self._BASE_URL}
        params = {'keyword': title}
        r = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'ajax/anime/search',
            data=params,
            headers=headers
        )
        if not r:
            control.log("AniWave: Empty search response")
            return []

        if 'NOT FOUND' in r:
            r1 = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'filter',
                data=params,
                headers=headers
            )

            mlink = SoupStrainer('div', {'class': 'ani items'})
            soup = BeautifulSoup(r1, "html.parser", parse_only=mlink)
            sitems = soup.find_all('div', {'class': 'item'})
            if sitems:
                items = [
                    urllib.parse.urljoin(self._BASE_URL, x.find('a', {'class': 'name'}).get('href'))
                    for x in sitems
                    if self.clean_embed_title(title) == self.clean_embed_title(x.find('a', {'class': 'name'}).get('data-jp'))
                ]
                if not items:
                    items = [
                        urllib.parse.urljoin(self._BASE_URL, x.find('a', {'class': 'name'}).get('href'))
                        for x in sitems
                        if self.clean_embed_title(title + 'dub') == self.clean_embed_title(x.find('a', {'class': 'name'}).get('data-jp'))
                    ]
        elif r:
            r = json.loads(r)
            r = BeautifulSoup(r.get('html') or r.get('result', {}).get('html'), "html.parser")
            sitems = r.find_all('a', {'class': 'item'})
            if sitems:
                items = [
                    urllib.parse.urljoin(self._BASE_URL, x.get('href'))
                    for x in sitems
                    if self.clean_embed_title(title) in self.clean_embed_title(x.find('div', {'class': 'name'}).text)
                ]

        if items:
            slug = items[0]
            all_results = self._process_aw(slug, title=title, episode=episode, langs=srcs)

        return all_results

    def _process_aw(self, slug, title, episode, langs):
        sources = []
        sources_found_per_lang = {}  # Track if we found sources for each language
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
            headers=headers, data=params
        )
        res = json.loads(r).get('result')
        try:
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
                    data=params, headers=headers
                )
                eres = json.loads(r).get('result')

                # Process each language sequentially (to respect user preferences)
                for lang in langs:
                    # Skip this language if we already found sources for it
                    if lang in sources_found_per_lang:
                        control.log(f"AniWave: Skipping '{lang}' - already have sources")
                        continue

                    elink = SoupStrainer('div', {'data-type': lang})
                    sdiv = BeautifulSoup(eres, "html.parser", parse_only=elink)
                    srcs = sdiv.find_all('li')

                    # Filter servers to only those in embeds
                    valid_servers = []
                    for src in srcs:
                        edata_id = src.get('data-link-id')
                        edata_name = src.text
                        if any(x in self.clean_embed_title(edata_name) for x in self.embeds()):
                            valid_servers.append({'id': edata_id, 'name': edata_name, 'lang': lang})

                    if not valid_servers:
                        control.log(f"AniWave: No valid servers found for '{lang}'")
                        continue

                    control.log(f"AniWave: Processing {len(valid_servers)} servers for '{lang}' in parallel")

                    # Process servers in parallel for this language
                    def process_server(server_info):
                        return self._extract_aniwave_source(server_info, title, episode, headers.copy())

                    # Process servers in parallel
                    server_sources = utils.parallel_process(valid_servers, process_server, max_workers=3)

                    # Add all sources from this language
                    for server_source in server_sources:
                        if server_source:
                            sources.extend(server_source)
                            # Mark that we found sources for this language
                            sources_found_per_lang[lang] = True

                    # If we found sources for this language, continue to next language
                    if sources:
                        control.log(f"AniWave: Found {len(sources)} sources for '{lang}'")
        except:
            import traceback
            traceback.print_exc()
            pass
        return sources

    def _extract_aniwave_source(self, server_info, title, episode, headers):
        """Extract sources from a single AniWave server"""
        sources = []
        edata_id = server_info['id']
        edata_name = server_info['name']
        lang = server_info['lang']

        try:
            control.log(f"AniWave: Processing server '{edata_name}' (ID: {edata_id})")
            vrf = self.generate_vrf(edata_id)
            params = {'vrf': vrf}
            r = self._get_request(
                '{0}ajax/server/{1}'.format(self._BASE_URL, edata_id),
                data=params,
                headers=headers
            )
            resp = json.loads(r).get('result')
            skip = {}
            if resp.get('skip_data'):
                skip_data = json.loads(self.decrypt_vrf(resp.get('skip_data')))
                intro = skip_data.get('intro')
                if intro:
                    skip.update({'intro': {'start': intro[0], 'end': intro[1]}})
                outro = skip_data.get('outro')
                if outro:
                    skip.update({'outro': {'start': outro[0], 'end': outro[1]}})
            slink = self.decrypt_vrf(resp.get('url'))

            if 'aniwave.' in slink:
                sresp = self.__extract_aniwave(slink)
                if sresp:
                    if isinstance(sresp, dict):
                        subs = sresp.get('subs')
                        skip = sresp.get('skip') or skip
                        srclink = sresp.get('url')
                    else:
                        srclink = sresp
                        subs = {}
                    headers.update({'Origin': self._BASE_URL[:-1]})
                    res = self._get_request(srclink, headers=headers)

                    # Check if request was successful
                    if not res:
                        control.log(f"AniWave: Failed to fetch m3u8 from {srclink}")
                        return sources

                    quals = re.findall(r'#EXT.+?RESOLUTION=\d+x(\d+).*\n(?!#)(.+)', res)
                    src_hdrs = {'User-Agent': 'iPad', 'Referer': urllib.parse.urljoin(srclink, '/')}
                    for qual, qlink in quals:
                        qual = int(qual)
                        if qual <= 577:
                            quality = 1
                        elif qual <= 721:
                            quality = 2
                        elif qual <= 1081:
                            quality = 3
                        else:
                            quality = 0
                        hlink = '{0}|{1}'.format(urllib.parse.urljoin(srclink, qlink), urllib.parse.urlencode(src_hdrs))
                        source = {
                            'release_title': '{0} - Ep {1}'.format(title, episode),
                            'hash': hlink,
                            'type': 'direct',
                            'quality': quality,
                            'debrid_provider': '',
                            'provider': 'aniwave',
                            'size': 'NA',
                            'seeders': 0,
                            'byte_size': 0,
                            'info': [edata_name + (' DUB' if lang == 'dub' else ' SUB')],
                            'lang': 3 if lang == 'dub' else 2,
                            'channel': 3,
                            'sub': 1
                        }
                        if subs:
                            source.update({'subs': subs})
                        if skip:
                            source.update({'skip': skip})
                        sources.append(source)
            else:
                source = {
                    'release_title': '{0} - Ep {1}'.format(title, episode),
                    'hash': slink,
                    'type': 'embed',
                    'quality': 0,
                    'debrid_provider': '',
                    'provider': 'aniwave',
                    'size': 'NA',
                    'seeders': 0,
                    'byte_size': 0,
                    'info': [edata_name + (' DUB' if lang == 'dub' else ' SUB')],
                    'lang': 3 if lang == 'dub' else 2,
                    'channel': 3,
                    'sub': 1
                }
                if skip:
                    source.update({'skip': skip})
                sources.append(source)
        except Exception as e:
            control.log(f"AniWave: Failed to process server '{edata_name}': {str(e)}")

        return sources

    @staticmethod
    def vrf_shift(t, offsets=CHAR_SUBST_OFFSETS):
        o = ''
        for s in range(len(t)):
            o += chr(ord(t[s]) + offsets[s % 8])
        return o

    def generate_vrf(self, content_id, key=EKEY):
        vrf = control.arc4(control.bin(key), control.bin(urllib.parse.quote(content_id)))
        vrf = (base64.urlsafe_b64encode(control.bin(vrf))).decode('latin-1')
        vrf = (base64.b64encode(control.bin(vrf))).decode('latin-1')
        vrf = self.vrf_shift(vrf)
        vrf = (base64.b64encode(control.bin(vrf))).decode('latin-1')
        vrf = codecs.encode(vrf, 'rot_13')
        return vrf.replace('/', '_').replace('+', '-')

    @staticmethod
    def decrypt_vrf(text, key=DKEY):
        data = control.arc4(control.bin(key), base64.urlsafe_b64decode(control.bin(text)))
        data = urllib.parse.unquote(data)
        return data

    def __extract_aniwave(self, url):
        page_content = self._get_request(url, headers={'Referer': self._BASE_URL})
        r = re.search(r'''sources["\s]?[:=]\s*\[\{"?file"?:\s*"([^"]+)''', page_content)
        if r:
            subs = []
            skip = {}
            surl = r.group(1)
            if 'vipanicdn.net' in surl:
                surl = surl.replace('vipanicdn.net', 'anzeat.pro')

            s = re.search(r'''tracks:\s*(\[[^\]]+])''', page_content)
            if s:
                s = json.loads(s.group(1))
                subs = [
                    {'url': x.get('file'), 'lang': x.get('label')}
                    for x in s if x.get('kind') == 'captions'
                    and x.get('file') is not None
                ]

            s = re.search(r'''var\s*intro_begin\s*=\s*(\d+);\s*var\s*introEnd\s*=\s*(\d+);\s*var\s*outroStart\s*=\s*(\d+);\s*var\s*outroEnd\s*=\s*(\d+);''', page_content)
            if s:
                if int(s.group(2)) > 0:
                    skip = {
                        "intro": {"start": int(s.group(1)), "end": int(s.group(2))},
                        "outro": {"start": int(s.group(3)), "end": int(s.group(4))}
                    }
            if subs or skip:
                surl = {'url': surl, 'subs': subs, 'skip': skip}

            return surl
