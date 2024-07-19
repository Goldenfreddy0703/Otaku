import json
import pickle
import re

from bs4 import BeautifulSoup, SoupStrainer
from six.moves import urllib_parse
from resources.lib.ui import control, database
from resources.lib.ui.jscrypto import jscrypto
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.indexers.malsync import MALSYNC


class sources(BrowserBase):
    _BASE_URL = 'https://hianime.sx/' if control.getSetting('provider.hianimealt') == 'true' else 'https://hianime.to/'
    js_file = 'https://megacloud.tv/js/player/a/prod/e1-player.min.js'

    def get_sources(self, anilist_id, episode, get_backup):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)
        keyword = title

        all_results = []
        srcs = ['sub', 'dub']
        if control.getSetting('general.source') == 'Sub':
            srcs.remove('dub')
        elif control.getSetting('general.source') == 'Dub':
            srcs.remove('sub')

        items = MALSYNC().get_slugs(anilist_id=anilist_id, site='Zoro')
        if not items:
            if kodi_meta.get('start_date'):
                year = kodi_meta.get('start_date').split('-')[0]
                keyword += ' {0}'.format(year)

            headers = {'Referer': self._BASE_URL}
            params = {'keyword': keyword}
            res = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'search',
                data=params,
                headers=headers
            )

            mlink = SoupStrainer('div', {'class': 'flw-item'})
            mdiv = BeautifulSoup(res, "html.parser", parse_only=mlink)
            sdivs = mdiv.find_all('h3')
            sitems = []
            for sdiv in sdivs:
                try:
                    slug = sdiv.find('a').get('href').split('?')[0]
                    stitle = sdiv.find('a').get('data-jname')
                    sitems.append({'title': stitle, 'slug': slug})
                except AttributeError:
                    pass

            if sitems:
                if title[-1].isdigit():
                    items = [x.get('slug') for x in sitems if title.lower() in x.get('title').lower()]
                else:
                    items = [x.get('slug') for x in sitems if (title.lower() + '  ') in (x.get('title').lower() + '  ')]
                if not items and ':' in title:
                    title = title.split(':')[0]
                    items = [x.get('slug') for x in sitems if (title.lower() + '  ') in (x.get('title').lower() + '  ')]

        if items:
            slug = items[0]
            all_results = self._process_aw(slug, title=title, episode=episode, langs=srcs)

        return all_results

    def _process_aw(self, slug, title, episode, langs):
        sources = []
        headers = {'Referer': self._BASE_URL}
        r = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'ajax/v2/episode/list/' + slug.split('-')[-1],
            headers=headers,
            XHR=True
        )
        res = json.loads(r).get('html')
        elink = SoupStrainer('div', {'class': re.compile('^ss-list')})
        ediv = BeautifulSoup(res, "html.parser", parse_only=elink)
        items = ediv.find_all('a')
        e_id = [x.get('data-id') for x in items if x.get('data-number') == episode]
        if e_id:
            params = {'episodeId': e_id[0]}
            r = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'ajax/v2/episode/servers',
                data=params,
                headers=headers,
                XHR=True
            )
            eres = json.loads(r).get('html')
            for lang in langs:
                elink = SoupStrainer('div', {'data-type': lang})
                sdiv = BeautifulSoup(eres, "html.parser", parse_only=elink)
                srcs = sdiv.find_all('div', {'class': 'item'})
                for src in srcs:
                    edata_id = src.get('data-id')
                    edata_name = src.text.strip().lower()
                    if edata_name.lower() in control.enabled_embeds():
                        params = {'id': edata_id}
                        r = self._get_request(
                            self._BASE_URL + 'ajax/v2/episode/sources',
                            data=params,
                            headers=headers,
                            XHR=True
                        )
                        slink = json.loads(r).get('link')
                        if edata_name == 'streamtape':
                            source = {
                                'release_title': '{0} - Ep {1}'.format(title, episode),
                                'hash': slink,
                                'type': 'embed',
                                'quality': 'EQ',
                                'debrid_provider': '',
                                'provider': 'h!anime',
                                'size': 'NA',
                                'info': ['DUB' if lang == 'dub' else 'SUB', edata_name],
                                'lang': 2 if lang == 'dub' else 0,
                                'skip': {}
                            }
                            sources.append(source)
                        else:
                            headers = {'Referer': slink}
                            sl = urllib_parse.urlparse(slink)
                            spath = sl.path.split('/')
                            spath.insert(2, 'ajax')
                            sid = spath.pop(-1)
                            eurl = '{}://{}{}/getSources'.format(sl.scheme, sl.netloc, '/'.join(spath))
                            params = {'id': sid}
                            res = self._get_request(
                                eurl,
                                data=params,
                                headers=headers,
                                XHR=True
                            )
                            res = json.loads(res)
                            subs = res.get('tracks')
                            if subs:
                                subs = [{'url': x.get('file'), 'lang': x.get('label')} for x in subs if x.get('kind') == 'captions']
                            skip = {}
                            if res.get('intro'):
                                skip.update({'intro': res.get('intro')})
                            if res.get('outro'):
                                skip.update({'outro': res.get('outro')})
                            if res.get('encrypted'):
                                slink = self._process_link(res.get('sources'))
                            else:
                                slink = res.get('sources')[0].get('file')
                            if not slink:
                                continue
                            res = self._get_request(slink, headers=headers)
                            quals = re.findall(r'#EXT.+?RESOLUTION=\d+x(\d+).+\n(?!#)(.+)', res)

                            for qual, qlink in quals:
                                qual = int(qual)
                                if qual < 577:
                                    quality = 'EQ'
                                elif qual < 721:
                                    quality = '720p'
                                elif qual < 1081:
                                    quality = '1080p'
                                else:
                                    quality = '4K'

                                source = {
                                    'release_title': '{0} - Ep {1}'.format(title, episode),
                                    'hash': urllib_parse.urljoin(slink, qlink) + '|User-Agent=iPad',
                                    'type': 'direct',
                                    'quality': quality,
                                    'debrid_provider': '',
                                    'provider': 'h!anime',
                                    'size': 'NA',
                                    'info': ['DUB' if lang == 'dub' else 'SUB', edata_name],
                                    'lang': 2 if lang == 'dub' else 0,
                                    'subs': subs,
                                    'skip': skip
                                }
                                sources.append(source)
        return sources

    def get_keyhints(self):
        def to_int(num):
            if num.startswith('0x'):
                return int(num, 16)
            return int(num)

        def chunked(varlist, count):
            return [varlist[i:i + count] for i in range(0, len(varlist), count)]

        js = self._get_request(self.js_file)
        cases = re.findall(r'switch\(\w+\){([^}]+?)partKey', js)[0]
        vars = re.findall(r"\w+=(\w+)", cases)
        consts = re.findall(r"((?:[,;\s]\w+=0x\w{1,2}){%s,})" % len(vars), js)[0]
        indexes = []
        for var in vars:
            var_value = re.search(r',{0}=(\w+)'.format(var), consts)
            if var_value:
                indexes.append(to_int(var_value.group(1)))

        return chunked(indexes, 2)

    def _process_link(self, sources):
        keyhints = database.get(self.get_keyhints, 0.2)
        try:
            key = ''
            orig_src = sources
            y = 0
            for m, p in keyhints:
                f = m + y
                x = f + p
                key += orig_src[f:x]
                sources = sources.replace(orig_src[f:x], '')
                y += p
            sources = json.loads(jscrypto.decode(sources, key))
            return sources[0].get('file')
        except:
            database.remove(self.get_keyhints)
            control.log('decryption key not working')
            return ''
