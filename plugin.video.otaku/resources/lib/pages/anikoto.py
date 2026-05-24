import pickle
import re
import urllib.parse

from resources.lib.ui import control, database, source_utils
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.megaplay_extractor import extract_megaplay_sources


class Sources(BrowserBase):
    _MEGAPLAY_MAL = 'https://megaplay.buzz/stream/mal/{0}/{1}/{2}'
    _REFERER = 'https://anikototv.to/'

    def get_sources(self, mal_id, episode):
        control.log(f"Anikoto: Getting sources for MAL ID {mal_id}, Episode {episode}")
        show = database.get_show(mal_id)
        if not show:
            return []

        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = self._clean_title(kodi_meta.get('name') or '')

        try:
            ep_num = int(episode)
        except (TypeError, ValueError):
            control.log(f"Anikoto: Invalid episode number: {episode}")
            return []

        langs = ['sub', 'dub']
        if control.getInt('general.source') == 1:
            langs.remove('dub')
        elif control.getInt('general.source') == 2:
            langs.remove('sub')

        all_results = []
        for lang in langs:
            embed_url = self._MEGAPLAY_MAL.format(mal_id, ep_num, lang)
            source = self._build_source(embed_url, title, ep_num, lang)
            if source:
                all_results.append(source)

        control.log(f"Anikoto: Returning {len(all_results)} source(s)")
        return all_results

    def _build_source(self, embed_url, title, episode, lang):
        try:
            res = extract_megaplay_sources(embed_url, self._REFERER)
            if not res or not res.get('sources'):
                control.log(f"Anikoto: No stream for {embed_url}", level='info')
                return None

            srclink = res['sources'][0].get('file')
            if not srclink:
                return None

            subs = []
            sub_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
                'Referer': embed_url,
            }
            for idx, track in enumerate(res.get('tracks') or []):
                if track.get('kind') == 'captions' and track.get('file'):
                    label = track.get('label') or ''
                    subs.append({
                        'url': track.get('file'),
                        'lang': label,
                        'name': label,
                        'index': idx,
                        'headers': sub_headers,
                    })

            skip = {}
            intro = res.get('intro') or {}
            outro = res.get('outro') or {}
            if intro.get('end') and int(intro.get('end', 0)) > 0:
                skip['intro'] = intro
            if outro.get('end') and int(outro.get('end', 0)) > 0:
                skip['outro'] = outro

            netloc = urllib.parse.urljoin(embed_url, '/')
            headers = {'Referer': netloc, 'Origin': netloc.rstrip('/')}
            quality = 0
            m3u8_res = self._get_request(srclink, headers=headers)
            if m3u8_res:
                quals = re.findall(r'#EXT.+?RESOLUTION=\d+x(\d+).*\n(?!#)(.+)', m3u8_res)
                if quals:
                    qual = int(sorted(quals, key=lambda x: int(x[0]), reverse=True)[0][0])
                    if qual <= 480:
                        quality = 1
                    elif qual <= 720:
                        quality = 2
                    elif qual <= 1080:
                        quality = 3

            host = source_utils.get_embedhost(embed_url) or 'megaplay'
            source = {
                'release_title': '{0} - Ep {1}'.format(title, episode),
                'hash': srclink + '|User-Agent=iPad&{0}'.format(urllib.parse.urlencode(headers)),
                'type': 'direct',
                'quality': quality,
                'debrid_provider': '',
                'provider': 'anikoto',
                'size': 'NA',
                'seeders': 0,
                'byte_size': 0,
                'info': [host + (' DUB' if lang == 'dub' else ' SUB')],
                'lang': 3 if lang == 'dub' else 2,
                'channel': 3,
                'sub': 1,
            }
            if subs:
                source['subs'] = subs
            if skip:
                source['skip'] = skip
            return source
        except Exception as e:
            control.log(f"Anikoto: Failed to build source ({lang}): {e}", level='error')
            return None
