import base64
import json
import pickle
import re
import urllib.parse

from bs4 import BeautifulSoup
from resources.lib.endpoints import malsync
from resources.lib.ui import control, database, utils
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.megaplay_extractor import extract_megaplay_sources


class Sources(BrowserBase):
    _BASE_URL = 'https://hianime.ms/'

    _MEGAPLAY_S2 = 'https://megaplay.buzz/stream/s-2/{0}/{1}'
    _MEGAPLAY_ANI = 'https://megaplay.buzz/stream/ani/{0}/{1}/{2}'
    _MEGAPLAY_MAL = 'https://megaplay.buzz/stream/mal/{0}/{1}/{2}'
    _PROXY_VOLT = 'https://megacloud.animanga.fun'
    _PROXY_AYAME = 'https://upcloud.animanga.fun'
    _MEGAPLAY_REF = 'https://megaplay.buzz/'
    _VIDNEST_REF = 'https://vidnest.fun/'

    _SERVER_NAMES = ('ryu', 'volt', 'ayame')

    def get_sources(self, mal_id, episode):
        control.log(f"HiAnime: Getting sources for MAL ID {mal_id}, Episode {episode}")
        show = database.get_show(mal_id)
        if not show:
            return []

        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = self._clean_title(kodi_meta.get('name') or '')

        try:
            ep_num = int(episode)
        except (TypeError, ValueError):
            control.log(f"HiAnime: Invalid episode number: {episode}")
            return []

        langs = ['sub', 'dub']
        if control.getInt('general.source') == 1:
            langs.remove('dub')
        elif control.getInt('general.source') == 2:
            langs.remove('sub')

        enabled = self._enabled_servers()
        if not enabled:
            control.log("HiAnime: No embed servers enabled (ryu/volt/ayame)")
            return []

        meta = self._resolve_show_meta(title, kodi_meta, mal_id, ep_num)
        if not meta:
            control.log(f"HiAnime: Could not resolve show '{title}' on hianime.ms")
            return []

        tasks = []
        for lang in langs:
            for server in enabled:
                tasks.append((server, lang, meta, title, ep_num))

        results = utils.parallel_process(tasks, self._extract_server_source)
        sources = [src for src in results if src]
        control.log(f"HiAnime: Returning {len(sources)} source(s)")
        return sources

    def _enabled_servers(self):
        allowed = set(self.embeds())
        enabled = [name for name in self._SERVER_NAMES if name in allowed]
        if not enabled:
            control.log(
                'HiAnime: ryu/volt/ayame not in embed settings; using all HiAnime servers',
                level='info',
            )
            return list(self._SERVER_NAMES)
        return enabled

    def _resolve_show_meta(self, title, kodi_meta, mal_id, episode):
        headers = {'Referer': self._BASE_URL}
        details_url = self._resolve_details_url(title, mal_id, headers)
        if not details_url:
            return None

        parsed = self._parse_details_slug(details_url)
        if not parsed:
            return None

        show_path, short_id = parsed
        watch_url = '{0}watch-{1}-episode-{2}-{3}'.format(
            self._BASE_URL, show_path, episode, short_id
        )
        watch_html = database.get(self._get_request, 8, watch_url, headers=headers)
        if not watch_html:
            control.log(f"HiAnime: Watch page not found: {watch_url}", level='info')
            return None

        meta = self._parse_watch_meta(watch_html, episode, mal_id)
        if meta and not meta.get('anilist_id'):
            details_html = database.get(self._get_request, 8, details_url, headers=headers)
            if details_html:
                ani = re.search(r'anilist\.co/anime/(\d+)', details_html)
                if ani:
                    meta['anilist_id'] = ani.group(1)
        return meta

    def _search_keywords(self, title, mal_id):
        keywords = []
        seen = set()

        def add(value):
            value = (value or '').strip()
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                keywords.append(value)

        add(title)
        if ':' in title:
            add(title.split(':', 1)[1].strip())
            add(title.split(':', 1)[0].strip())
        words = [w for w in re.split(r'\s+', title) if len(w) > 2]
        if len(words) >= 2:
            add(words[-1])
        zoro_title = malsync.get_title(mal_id, site='Zoro')
        add(zoro_title)
        return keywords

    @staticmethod
    def _parse_search_results(html):
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        for block in soup.select('.flw-item'):
            link = block.select_one('a[href*="/details/"]')
            if not link:
                continue
            href = link.get('href', '').split('?')[0]
            if href.startswith('/'):
                href = 'https://hianime.ms' + href
            name_el = block.select_one('.film-name')
            name = name_el.get_text(strip=True) if name_el else ''
            if not name:
                name = link.get('title') or link.get('data-jname') or ''
            if href and name:
                items.append({'href': href, 'name': name})
        return items

    def _collect_search_candidates(self, title, mal_id, headers):
        candidates = {}
        for keyword in self._search_keywords(title, mal_id):
            res = database.get(
                self._get_request,
                8,
                self._BASE_URL + 'search',
                data={'q': keyword},
                headers=headers,
            )
            if not res:
                continue
            for item in self._parse_search_results(res):
                candidates[item['href']] = item['name']
        return candidates

    def _details_mal_id(self, details_url, headers):
        html = self._get_request(details_url, headers=headers)
        if not html:
            return None
        match = re.search(r'myanimelist\.net/anime/(\d+)', html)
        return match.group(1) if match else None

    def _details_mal_id_cached(self, details_url, headers):
        return database.get(self._details_mal_id, 24, details_url, headers)

    @staticmethod
    def _season_number(text):
        if not text:
            return None
        match = re.search(r'(?:season|part)\s*(\d+)', text, re.I)
        if match:
            return int(match.group(1))
        match = re.search(r'(\d+)(?:st|nd|rd|th)\s+season', text, re.I)
        if match:
            return int(match.group(1))
        return None

    def _score_candidate(self, candidate_name, title):
        name_lower = candidate_name.lower()
        title_lower = title.lower()
        score = 0

        if title_lower in name_lower or name_lower in title_lower:
            score += 100

        title_tokens = [w for w in re.split(r'[^a-z0-9]+', title_lower) if len(w) > 2]
        name_tokens = set(re.split(r'[^a-z0-9]+', name_lower))
        overlap = sum(1 for token in title_tokens if token in name_tokens)
        score += overlap * 10

        wanted_season = self._season_number(title)
        candidate_season = self._season_number(candidate_name)
        if wanted_season is None:
            if candidate_season not in (None, 1):
                score -= 40
        elif candidate_season != wanted_season:
            score -= 50

        if 'season' in name_lower and wanted_season is None and candidate_season not in (None, 1):
            score -= 20

        return score

    def _resolve_details_url(self, title, mal_id, headers):
        candidates = self._collect_search_candidates(title, mal_id, headers)
        if not candidates:
            control.log(f"HiAnime: No search results for '{title}'", level='info')
            return None

        for href, name in candidates.items():
            page_mal = self._details_mal_id_cached(href, headers)
            if page_mal and str(page_mal) == str(mal_id):
                control.log(f"HiAnime: Matched '{name}' via MAL ID {mal_id}", level='info')
                return href

        ranked = sorted(
            candidates.items(),
            key=lambda row: self._score_candidate(row[1], title),
            reverse=True,
        )
        if ranked:
            best_href, best_name = ranked[0]
            control.log(
                "HiAnime: Using best search match '{0}' (score {1})".format(
                    best_name,
                    self._score_candidate(best_name, title),
                ),
                level='info',
            )
            return best_href
        return None

    @staticmethod
    def _parse_details_slug(details_url):
        match = re.search(r'/details/(.+)-([a-z0-9]{4,8})$', details_url)
        if not match:
            return None
        return match.group(1), match.group(2)

    @staticmethod
    def _parse_watch_meta(html, episode, mal_id):
        anilist_match = re.search(r'var anilistId = (\d+);', html)
        mal_match = re.search(r'var malId = (\d+);', html)
        token_match = re.search(
            r'class="ws-ep[^"]*"[^>]*data-episode="{0}"[^>]*data-stream-token="([^"]+)"'.format(episode),
            html,
        )
        if not token_match:
            token_match = re.search(
                r'data-episode="{0}"[^>]*data-stream-token="([^"]+)"'.format(episode),
                html,
            )

        anilist_id = anilist_match.group(1) if anilist_match else None
        page_mal_id = mal_match.group(1) if mal_match else None
        stream_token = token_match.group(1) if token_match else None

        if not anilist_id and not page_mal_id and not stream_token:
            return None

        return {
            'anilist_id': anilist_id,
            'mal_id': page_mal_id or str(mal_id),
            'stream_token': stream_token,
            'episode': int(episode),
        }

    @staticmethod
    def _decode_stream_token(token):
        if not token:
            return None
        try:
            padded = token.replace('-', '+').replace('_', '/')
            padded += '=' * (-len(padded) % 4)
            decoded = base64.b64decode(padded).decode('utf-8', errors='replace')
            return decoded.split(':')[0]
        except (ValueError, TypeError):
            return None

    def _megaplay_embed_url(self, meta, lang):
        token_id = self._decode_stream_token(meta.get('stream_token'))
        if token_id:
            return self._MEGAPLAY_S2.format(token_id, lang)
        if meta.get('anilist_id'):
            return self._MEGAPLAY_ANI.format(meta['anilist_id'], meta['episode'], lang)
        return self._MEGAPLAY_MAL.format(meta['mal_id'], meta['episode'], lang)

    @staticmethod
    def _proxy_playlist(m3u8_url, proxy_base, referer=None):
        referer = referer or Sources._MEGAPLAY_REF
        stream_headers = json.dumps({
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.5',
            'origin': 'https://megaplay.buzz',
            'referer': referer,
        }, separators=(',', ':'))
        return '{0}/proxy?url={1}&headers={2}'.format(
            proxy_base,
            urllib.parse.quote(m3u8_url, safe=''),
            urllib.parse.quote(stream_headers, safe=''),
        )

    @staticmethod
    def _proxy_subtitle(sub_url, fetch_base, ref=None):
        """Proxy remote VTT through animanga fetch (same as the site player)."""
        if not sub_url:
            return sub_url
        if 'animanga.fun/fetch' in sub_url or 'anixx.cloud/proxy' in sub_url:
            return sub_url
        ref = ref or Sources._MEGAPLAY_REF
        return '{0}/fetch?url={1}&ref={2}'.format(
            fetch_base,
            urllib.parse.quote(sub_url, safe=''),
            urllib.parse.quote(ref, safe=''),
        )

    @staticmethod
    def _build_tracks_subs(tracks, sub_fetch_base, play_referer, sub_ref=None):
        from resources.lib.ui import embed_extractor

        subs = []
        sub_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0',
            'Referer': play_referer,
        }
        sub_ref = sub_ref or Sources._MEGAPLAY_REF

        for idx, track in enumerate(tracks or []):
            if track.get('kind') != 'captions' or not track.get('file'):
                continue
            label = track.get('label') or ''
            sub_url = track.get('file')
            if sub_fetch_base:
                sub_url = Sources._proxy_subtitle(sub_url, sub_fetch_base, ref=sub_ref)
            subs.append({
                'url': sub_url,
                'file': track.get('file'),
                'lang': embed_extractor.detect_sub_lang(track.get('file'), label),
                'name': label,
                'index': idx,
                'headers': sub_headers,
            })
        return subs

    def _extract_server_source(self, task):
        server, lang, meta, title, episode = task
        try:
            embed_url = self._megaplay_embed_url(meta, lang)
            res = extract_megaplay_sources(embed_url, self._BASE_URL)
            play_referer = self._VIDNEST_REF
            if server == 'ayame':
                sub_fetch_base = self._PROXY_AYAME
            else:
                sub_fetch_base = self._PROXY_VOLT

            if not res or not res.get('sources'):
                control.log(f"HiAnime: No stream for {server} ({lang})", level='info')
                return None

            srclink = res['sources'][0].get('file')
            if not srclink:
                return None

            if server in ('ryu', 'volt'):
                srclink = self._proxy_playlist(srclink, self._PROXY_VOLT)
            elif server == 'ayame':
                srclink = self._proxy_playlist(srclink, self._PROXY_AYAME)

            subs = self._build_tracks_subs(
                res.get('tracks'),
                sub_fetch_base,
                play_referer,
            )

            skip = {}
            intro = res.get('intro') or {}
            outro = res.get('outro') or {}
            if intro.get('end') and int(intro.get('end', 0)) > 0:
                skip['intro'] = intro
            if outro.get('end') and int(outro.get('end', 0)) > 0:
                skip['outro'] = outro

            headers = {
                'Referer': play_referer,
                'Origin': play_referer.rstrip('/'),
            }
            quality = self._playlist_quality(srclink, headers)

            source = {
                'release_title': '{0} - Ep {1}'.format(title, episode),
                'hash': srclink + '|User-Agent=iPad&{0}'.format(urllib.parse.urlencode(headers)),
                'type': 'direct',
                'quality': quality,
                'debrid_provider': '',
                'provider': 'hianime',
                'size': 'NA',
                'seeders': 0,
                'byte_size': 0,
                'info': [server + (' DUB' if lang == 'dub' else ' SUB')],
                'lang': 3 if lang == 'dub' else 2,
                'channel': 3,
                'sub': 1,
            }
            if subs:
                source['subs'] = subs
                control.log(f"HiAnime: {server} ({lang}) attached {len(subs)} subtitle track(s)", level='info')
            if skip:
                source['skip'] = skip
            return source
        except Exception as e:
            control.log(f"HiAnime: Failed {server} ({lang}): {e}", level='error')
            return None

    def _playlist_quality(self, srclink, headers):
        quality = 0
        m3u8_res = self._get_request(srclink, headers=headers)
        if not m3u8_res:
            return quality
        quals = re.findall(r'#EXT.+?RESOLUTION=\d+x(\d+).*\n(?!#)(.+)', m3u8_res)
        if quals:
            qual = int(sorted(quals, key=lambda x: int(x[0]), reverse=True)[0][0])
            if qual <= 480:
                quality = 1
            elif qual <= 720:
                quality = 2
            elif qual <= 1080:
                quality = 3
        return quality
