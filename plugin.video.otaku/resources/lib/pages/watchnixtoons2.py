import html
import pickle
import re
import time
import uuid
import urllib.parse
import json
from bs4 import BeautifulSoup
from resources.lib.ui import control, database, client
from resources.lib.ui.BrowserBase import BrowserBase
import threading


class Sources(BrowserBase):
    _BASE_URL = 'https://www.wcostream.tv/'
    _WNT2_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'

    def __init__(self):
        super().__init__()
        self.request_delay = 1.2  # Minimum spacing between WCO requests
        self._cache = {}  # Simple response cache
        self._cache_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._last_request_time = 0
        self._thread_local = threading.local()
        self._on_ad_verify_complete = None

    def _get_wco_session(self):
        """Per-thread session so parallel SUB/DUB embed flows keep separate cookies."""
        session = getattr(self._thread_local, 'wco_session', None)
        if session is None:
            session = client.Session()
            self._thread_local.wco_session = session
        return session

    def _build_search_titles(self, romaji_title, english_title, clean_title):
        """English first; only add fallbacks when titles differ."""
        ordered = []
        seen = set()
        for search_type, title in (
            ('english', english_title),
            ('romaji', romaji_title),
            ('clean', clean_title),
        ):
            if not title:
                continue
            key = title.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append((search_type, title))
        return ordered

    def _episode_langs_complete(self, found_episodes):
        return 2 in found_episodes and 3 in found_episodes

    def _merge_episode_results(self, found_episodes, episode_results, search_type):
        for episode_result in episode_results:
            lang = self._episode_lang_key(episode_result)
            version_type = "DUB" if lang == 3 else "SUB"
            existing = found_episodes.get(lang)
            if self._is_better_episode(episode_result, existing):
                found_episodes[lang] = episode_result
                control.log(
                    f"Added {search_type} {version_type} episode: {episode_result['title']} "
                    f"(from {episode_result.get('series_title', 'Unknown')})"
                )
            else:
                control.log(f"Duplicate {version_type} episode found for {search_type}, skipping")

    def _make_request(self, url, method='GET', data=None, json_data=None, headers=None, timeout=10, use_cache=True):
        """HTTP helper with per-thread cookies and shared rate limiting."""

        cache_key = "{0}:{1}".format(method, url)
        if use_cache and method.upper() == 'GET':
            with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

        try:
            my_headers = {
                'User-Agent': self._WNT2_UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Cache-Control': 'no-cache',
            }
            if headers:
                my_headers.update(headers)

            with self._rate_lock:
                time_since_last = time.time() - self._last_request_time
                if time_since_last < self.request_delay:
                    time.sleep(self.request_delay - time_since_last)

            wco_session = self._get_wco_session()
            if method.upper() == 'POST':
                if json_data is not None:
                    resp = wco_session.post(
                        url, json_data=json_data, headers=my_headers, timeout=timeout, verify=False
                    )
                else:
                    resp = wco_session.post(
                        url, data=data, headers=my_headers, timeout=timeout, verify=False
                    )
            else:
                resp = wco_session.get(
                    url, headers=my_headers, timeout=timeout, verify=False
                )

            with self._rate_lock:
                self._last_request_time = time.time()

            if resp.status_code not in (200, 204):
                control.log(
                    "Request failed for {0} (HTTP {1})".format(url, resp.status_code),
                    level='warning',
                )
                return None

            response = resp.text if resp.content else None
            if not response:
                control.log("Request returned empty body for {0}".format(url), level='warning')
                return None

            if use_cache and method.upper() == 'GET':
                with self._cache_lock:
                    self._cache[cache_key] = response
                    if len(self._cache) > 50:
                        for key in list(self._cache.keys())[:10]:
                            del self._cache[key]

            return response

        except Exception as e:
            control.log("Client request failed for {0}: {1}".format(url, str(e)), "error")
            return None

    def get_sources(self, mal_id, episode, media_type):

        if media_type == 'movie':
            return []

        show = database.get_show(mal_id)
        database_meta = database.get_mappings(mal_id, 'mal_id')
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        season = database.get_episode(mal_id)['season']
        anime_media_episodes = database_meta.get('anime_media_episodes', {})
        global_media_episodes = database_meta.get('global_media_episodes', {})
        romaji_title = kodi_meta.get('name')
        english_title = kodi_meta.get('ename')
        clean_title = self._clean_title(romaji_title)

        if season == 1:
            if database_meta and 'thetvdb_season' in database_meta:
                thetvdb_season = database_meta['thetvdb_season']
                if thetvdb_season == 'a' or thetvdb_season == 0:
                    season = None

        # Map episode number if anime_media_episodes and global_media_episodes are different
        mapped_episode = episode
        if anime_media_episodes and global_media_episodes:
            # Parse ranges like "1-13" and "13-25"
            anime_range = self._parse_episode_range(anime_media_episodes)
            global_range = self._parse_episode_range(global_media_episodes)

            if anime_range and global_range and anime_range != global_range:
                anime_start, anime_end = anime_range
                global_start, global_end = global_range

                # Convert episode to int for comparison
                episode_int = int(episode)

                # Check if episode is within anime range
                if anime_start <= episode_int <= anime_end:
                    # Map episode from anime range to global range
                    offset = episode_int - anime_start
                    mapped_episode = global_start + offset
                    control.log(f"Mapped episode {episode} to {mapped_episode}")

        search_titles = self._build_search_titles(romaji_title, english_title, clean_title)
        found_episodes = {}  # keyed by lang (2=SUB, 3=DUB)

        for search_type, search_title in search_titles:
            if self._episode_langs_complete(found_episodes):
                control.log('WatchNixtoons2: SUB and DUB episodes found, skipping remaining searches')
                break

            control.log(f"Searching for {search_type} version with title: {search_title}")
            try:
                episode_results = self._search_and_get_episodes(
                    search_title, season, mapped_episode, search_type
                ) or []
                self._merge_episode_results(found_episodes, episode_results, search_type)
            except Exception as e:
                control.log(f"Search failed for {search_type}: {str(e)}")

        control.log(f"WatchNixtoons2: Found {len(found_episodes)} episode variants to process")

        sources = []
        sub_ep = found_episodes.get(2)
        dub_ep = found_episodes.get(3)
        piped_dub = {'thread': None, 'result': None}

        def start_dub_pipeline():
            if not dub_ep or piped_dub['thread'] is not None:
                return

            def run_dub():
                piped_dub['result'] = self._extract_episode_sources(dub_ep)

            piped_dub['thread'] = threading.Thread(target=run_dub, daemon=True)
            piped_dub['thread'].start()
            control.log('WatchNixtoons2: started DUB extraction during SUB ad-verify wait', level='info')

        if sub_ep:
            self._on_ad_verify_complete = start_dub_pipeline
            try:
                sub_result = self._extract_episode_sources(sub_ep)
                if sub_result:
                    sources.extend(sub_result[0])
                    control.log(
                        f"WatchNixtoons2: Found {len(sub_result[0])} sources for lang {sub_result[1]}"
                    )
            finally:
                self._on_ad_verify_complete = None

            if dub_ep and piped_dub['thread'] is None:
                start_dub_pipeline()
        elif dub_ep:
            dub_result = self._extract_episode_sources(dub_ep)
            if dub_result:
                sources.extend(dub_result[0])
                control.log(
                    f"WatchNixtoons2: Found {len(dub_result[0])} sources for lang {dub_result[1]}"
                )

        if piped_dub['thread'] is not None:
            piped_dub['thread'].join()

        if piped_dub['result']:
            dub_sources, dub_lang = piped_dub['result']
            if dub_sources:
                sources.extend(dub_sources)
                control.log(f"WatchNixtoons2: Found {len(dub_sources)} sources for lang {dub_lang}")

        langs_found = {s.get('lang') for s in sources}
        if 2 in langs_found and 3 in langs_found:
            control.log("WatchNixtoons2: Found sources for both SUB and DUB")

        control.log(f"WatchNixtoons2: Returning {len(sources)} total sources")
        return sources

    def _extract_episode_sources(self, episode_data):
        """Extract playable sources for one episode link (SUB or DUB)."""
        lang = self._episode_lang_key(episode_data)
        version_type = "DUB" if lang == 3 else "SUB"

        try:
            control.log(
                f"WatchNixtoons2: Processing '{version_type}' episode: "
                f"{episode_data.get('title', 'Unknown')}"
            )

            resp = self._make_request(episode_data['url'])
            if not resp:
                control.log(f"Failed to get episode page: {episode_data['url']}")
                return None

            for attempt in (1, 2):
                advanced_sources = self._extract_advanced_sources(
                    episode_data['url'], resp, version_type, lang, episode_data['title']
                )
                if advanced_sources:
                    return (advanced_sources, lang)
                if attempt == 1 and lang == 2:
                    control.log(
                        'WatchNixtoons2: SUB extraction returned no sources, retrying once',
                        level='warning',
                    )
                    self._thread_local.wco_session = None
                    time.sleep(2)
                    continue

                iframe_sources = self._extract_iframe_sources(
                    resp, version_type, lang, episode_data
                )
                if iframe_sources:
                    return (iframe_sources, lang)
                break

        except Exception as e:
            control.log(
                f"Source extraction failed for {episode_data.get('title', 'Unknown')}: {str(e)}"
            )

        return None

    def _unescape_html_url(self, url):
        return html.unescape(url or '')

    def _ensure_full_url(self, base_url, url):
        url = self._unescape_html_url(url)
        if url.startswith('http://') or url.startswith('https://'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        return urllib.parse.urljoin(base_url, url)

    def _embed_api_origin(self, embed_url):
        parsed = urllib.parse.urlparse(embed_url)
        if parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}/'
        return 'https://embed.wcostream.com/'

    def _find_embed_url(self, page_content, episode_url):
        """Locate the player embed URL using the original WNT2 detection order."""
        if '"vjs_iframe"' in page_content:
            match = re.search(
                r'<iframe id="(?:[a-zA-Z0-9-]+)" class="vjs_iframe" rel="nofollow" src="([^"]+)"',
                page_content,
                re.DOTALL
            )
            if match:
                return self._ensure_full_url(episode_url, match.group(1)), True

        if 'uploads0" src=' in page_content:
            match = re.search(
                r'<iframe\s*id="(?:[a-zA-Z]+)uploads(?:[0-9]+)"\s*src="([^"]+)"',
                page_content,
                re.DOTALL
            )
            if match:
                return self._ensure_full_url(episode_url, match.group(1)), False

        if '-js-0" src=' in page_content:
            match = re.search(
                r'<iframe\s*(?:rel="nofollow")?\s*id="(?:[a-zA-Z]+)\-js\-(?:[0-9]+)"\s*src="([^"]+)"',
                page_content,
                re.DOTALL
            )
            if match:
                return self._ensure_full_url(episode_url, match.group(1)), False

        embed_url_index = page_content.find('onclick="myFunction')
        if embed_url_index <= 0:
            embed_url_index = page_content.find('class="episode-descp"')

        if embed_url_index > 0:
            match = re.search(r'src="([^"]+)', page_content[embed_url_index:])
            if match:
                embed_src = self._ensure_full_url(episode_url, match.group(1))
                is_vhs = 'vhs.wcostream.com' in embed_src.lower()
                return embed_src, is_vhs

        skip_hosts = ('ads', 'analytics', 'disqus', 'facebook', 'twitter', 'check-login')
        for iframe_url in re.findall(r'<iframe[^>]+src="([^"]+)"', page_content, re.IGNORECASE):
            if any(skip in iframe_url.lower() for skip in skip_hosts):
                continue
            return self._ensure_full_url(episode_url, iframe_url), False

        return None, False

    def _prepare_embed_player_url(self, embed_url):
        """Run WCO ad-verify and return the video-js-old.php player URL."""
        embed_url = self._unescape_html_url(embed_url)
        if 'inc/embed/index.php' not in embed_url:
            return embed_url

        control.log('WatchNixtoons2: running WCO ad-verify for embed', level='info')
        flag = '__abd_' + uuid.uuid4().hex[:8]
        self._make_request(
            'https://embed.wcostream.com/assets/ads/advertisement.js?flag={0}&_={1}'.format(
                flag, int(time.time() * 1000)
            ),
            headers={
                'Accept': '*/*',
                'Referer': embed_url,
            },
            use_cache=False,
        )

        pid_match = re.search(r'&pid=([0-9]+)', embed_url)
        if not pid_match:
            control.log('WatchNixtoons2: embed URL missing pid for ad-verify', level='warning')
            return embed_url.replace('inc/embed/index.php', 'inc/embed/video-js-old.php')

        nonce = uuid.uuid4().hex
        self._make_request(
            'https://embed.wcostream.com/ad-verify',
            method='POST',
            json_data={'nonce': nonce, 'status': 'clear', 'id': pid_match.group(1)},
            headers={
                'Content-Type': 'application/json',
                'Referer': embed_url,
            },
            use_cache=False,
        )

        player_url = embed_url.replace('inc/embed/index.php', 'inc/embed/video-js-old.php') + '&n=' + nonce
        control.log('WatchNixtoons2: ad-verify complete, loading player URL', level='info')
        if self._on_ad_verify_complete:
            try:
                self._on_ad_verify_complete()
            except Exception as exc:
                control.log(
                    'WatchNixtoons2: pipelined DUB start failed: {0}'.format(exc),
                    level='warning',
                )
        time.sleep(5)
        return player_url

    def _follow_redirect_url(self, url, referer):
        """Follow 3xx redirects on media URLs (same as WNT2 solve_media_redirect)."""
        headers = {
            'User-Agent': self._WNT2_UA,
            'Referer': referer,
            'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
        }
        current = url
        for _ in range(10):
            result = client.request(
                current,
                headers=headers,
                redirect=False,
                verify=False,
                error=True,
                output='extended',
                timeout=10,
            )
            if not result or not isinstance(result, tuple) or len(result) < 6:
                return url
            _content, status_code, resp_headers, _req_headers, _cookie, resp_url = result
            location = resp_headers.get('Location')
            if str(status_code) in ('301', '302', '303', '307', '308') and location:
                if location.startswith('/'):
                    parsed = urllib.parse.urlparse(resp_url or current)
                    current = '{0}://{1}{2}'.format(parsed.scheme, parsed.netloc, location)
                elif location.startswith('http'):
                    current = location
                else:
                    current = urllib.parse.urljoin(resp_url or current, location)
                continue
            if str(status_code).startswith('2'):
                return resp_url or current
            break
        return url

    def _fetch_player_html(self, embed_url, episode_url):
        original_embed = self._unescape_html_url(embed_url)
        player_url = self._prepare_embed_player_url(original_embed)
        headers = {
            'User-Agent': self._WNT2_UA,
            'Referer': player_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        player_html = self._make_request(player_url, headers=headers, use_cache=False)
        if not player_html:
            control.log(
                'WatchNixtoons2: empty player page for {0}'.format(player_url),
                level='warning',
            )
        elif not any(
            marker in player_html
            for marker in ('getvid?evid', 'getvidlink', 'getRedirectedUrl', '<source')
        ):
            control.log(
                'WatchNixtoons2: player page missing stream markers (len={0})'.format(len(player_html)),
                level='warning',
            )
        return player_html, player_url

    def _build_direct_source(self, title, version_type, lang, video_url, referer, quality_num, info_label):
        video_url = self._follow_redirect_url(video_url, referer)
        video_headers = {
            'User-Agent': self._WNT2_UA,
            'Referer': referer,
            'Accept': '*/*',
        }
        return {
            'release_title': f"{title} - {version_type}",
            'hash': f"{video_url}|{urllib.parse.urlencode(video_headers)}",
            'type': 'direct',
            'quality': quality_num,
            'debrid_provider': '',
            'provider': 'watchnixtoons2',
            'size': 'NA',
            'seeders': 0,
            'byte_size': 0,
            'info': [info_label],
            'lang': lang,
            'channel': 3,
            'sub': 1,
        }

    def _resolve_api_url(self, player_html, embed_url):
        if 'getRedirectedUrl(videoUrl)' in player_html:
            match = re.search(r'\$\.getJSON\("([^"]+)"', player_html, re.DOTALL)
            if match:
                source_url = 'https://embed.wcostream.com/' + match.group(1).lstrip('/')
                if 'json' not in source_url:
                    source_url += '&json' if '?' in source_url else '?json'
                return source_url

        match = re.search(r'"(/inc/embed/getvidlink[^"]+)', player_html, re.DOTALL)
        if match:
            return self._BASE_URL.rstrip('/') + match.group(1)

        return None

    def _api_source_candidates(self, player_html, embed_url):
        candidates = []
        primary = self._resolve_api_url(player_html, embed_url)
        if primary:
            candidates.append(primary)

        match = re.search(r'"(/inc/embed/getvidlink[^"]+)', player_html or '', re.DOTALL)
        if match:
            embed_fallback = 'https://embed.wcostream.com' + match.group(1)
            if embed_fallback not in candidates:
                candidates.append(embed_fallback)

        return candidates

    def _extract_api_sources_from_html(self, player_html, embed_url, title, version_type, lang):
        sources = []
        api_urls = self._api_source_candidates(player_html, embed_url)
        if not api_urls:
            control.log('WatchNixtoons2: no WCO API URL found in player HTML', level='info')
            return sources

        server_resp = None
        json_data = None
        api_headers = {
            'Accept': '*/*',
            'Referer': embed_url,
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': self._WNT2_UA,
        }
        for candidate in api_urls:
            control.log('WatchNixtoons2: requesting WCO server API: {0}'.format(candidate))
            server_resp = self._make_request(candidate, headers=api_headers, use_cache=False)
            if not server_resp:
                control.log(
                    'WatchNixtoons2: WCO API request failed for {0}'.format(candidate),
                    level='warning',
                )
                continue
            try:
                json_data = json.loads(server_resp)
                break
            except json.JSONDecodeError as exc:
                control.log(
                    'WatchNixtoons2: invalid JSON from {0}: {1}'.format(candidate, exc),
                    level='warning',
                )
                control.log('Response preview: {0}'.format(server_resp[:500]))
                server_resp = None
                json_data = None

        if not server_resp or json_data is None:
            control.log('WatchNixtoons2: all WCO API requests failed', level='warning')
            return sources

        control.log(f"WCO API response keys: {list(json_data.keys())}")
        token_sd = json_data.get('enc', '')
        token_hd = json_data.get('hd', '')
        token_fhd = json_data.get('fhd', '')

        server_base_url = json_data.get('server', '')
        if server_base_url:
            server_base_url = server_base_url.rstrip('/') + '/getvid?evid='

        for quality_label, token, quality_num in (
            ('SD', token_sd, 1),
            ('HD', token_hd, 2),
            ('FHD', token_fhd, 3),
        ):
            if server_base_url and token:
                video_url = server_base_url + token
                sources.append(self._build_direct_source(
                    title, version_type, lang, video_url, embed_url, quality_num,
                    f'API {quality_label} {version_type}'
                ))
                control.log(f"Added WCO API source: {quality_label} - {video_url}")

        cdn_backup = json_data.get('cdn', '')
        if cdn_backup and (token_sd or token_hd or token_fhd):
            backup_token = token_fhd or token_hd or token_sd
            backup_url = cdn_backup.rstrip('/') + '/getvid?evid=' + backup_token
            sources.append(self._build_direct_source(
                title, version_type, lang, backup_url, embed_url, 2,
                f'CDN Backup {version_type}'
            ))
            control.log(f"Added CDN backup source: {backup_url}")

        return sources

    def _extract_m3u8_sources_from_html(self, player_html, embed_url, title, version_type, lang):
        sources = []

        source_match = re.search(r'<source\s*src="([^"]+)"', player_html, re.DOTALL)
        if source_match:
            m3u8_url = source_match.group(1)
            sources.append(self._build_direct_source(
                title, version_type, lang, m3u8_url, embed_url, 3,
                f'M3U8 {version_type}'
            ))
            control.log(f"Added M3U8 source: {m3u8_url}")
            return sources

        redirect_match = re.search(r'getRedirectedUrl\("([^"]+)', player_html, re.DOTALL)
        if redirect_match:
            m3u8_url = redirect_match.group(1)
            sources.append(self._build_direct_source(
                title, version_type, lang, m3u8_url, embed_url, 3,
                f'M3U8 {version_type}'
            ))
            control.log(f"Added redirected M3U8 source: {m3u8_url}")

        return sources

    def _extract_jwplayer_sources_from_html(self, player_html, embed_url, title, version_type, lang):
        sources = []
        sources_block = re.search(r'sources:\s*?\[(.*?)\]', player_html, re.DOTALL)
        if not sources_block:
            return sources

        stream_pattern = re.compile(r'\{\s*?file:\s*?"(.*?)"(?:,\s*?label:\s*?"(.*?)")?')
        for source_match in stream_pattern.finditer(sources_block.group(1)):
            label = source_match.group(2) or 'Stream'
            video_url = source_match.group(1)
            if '1080' in label:
                quality_num = 3
            elif '720' in label:
                quality_num = 2
            else:
                quality_num = 1
            sources.append(self._build_direct_source(
                title, version_type, lang, video_url, embed_url, quality_num,
                f'{label} {version_type}'
            ))
            control.log(f"Added JWPlayer source: {label} - {video_url}")

        return sources

    def _extract_streams_from_player_html(self, player_html, embed_url, title, version_type, lang, is_m3u8_player=False):
        if not player_html:
            return []

        if 'high volume of requests' in player_html:
            control.log('WCO player blocked free users temporarily')
            return []

        if 'getvid?evid' in player_html:
            sources = self._extract_api_sources_from_html(player_html, embed_url, title, version_type, lang)
            if sources:
                return sources

        if is_m3u8_player:
            sources = self._extract_m3u8_sources_from_html(player_html, embed_url, title, version_type, lang)
            if sources:
                return sources

        sources = self._extract_m3u8_sources_from_html(player_html, embed_url, title, version_type, lang)
        if sources:
            return sources

        sources = self._extract_jwplayer_sources_from_html(player_html, embed_url, title, version_type, lang)
        if not sources:
            control.log(
                'WatchNixtoons2: no streams extracted from player HTML for {0}'.format(version_type),
                level='warning',
            )
        return sources

    def _extract_advanced_sources(self, episode_url, page_content, version_type, lang, title):
        """Extract sources using the original WNT2 embed/player resolution flow."""
        sources = []

        try:
            premium_url = self._premium_workaround_check(page_content, episode_url)
            if premium_url:
                sources.append(self._build_direct_source(
                    title, version_type, lang, premium_url, episode_url, 3,
                    f'Premium {version_type}'
                ))
                control.log(f"Added premium workaround source: {premium_url}")

            embed_url, is_m3u8_player = self._find_embed_url(page_content, episode_url)
            if not embed_url:
                control.log("No embed URL found on episode page")
                return sources

            control.log(f"Found embed URL: {embed_url}")
            player_html, resolved_embed_url = self._fetch_player_html(embed_url, episode_url)
            if not player_html:
                control.log(f"Failed to fetch embed player page: {resolved_embed_url}")
                return sources

            sources.extend(self._extract_streams_from_player_html(
                player_html,
                resolved_embed_url,
                title,
                version_type,
                lang,
                is_m3u8_player,
            ))

        except Exception as e:
            control.log(f"Advanced source extraction failed: {str(e)}", "error")

        control.log(f"WNT2 extraction completed - Total sources found: {len(sources)}")
        for i, source in enumerate(sources, 1):
            info_str = ' '.join(source.get('info', []))
            control.log(f"Source {i}: {info_str} - Quality: {source.get('quality')}")

        return sources

    def _premium_workaround_check(self, page_content, episode_url):
        """Check for WNT2's premium workaround playlist URLs"""
        try:
            # Look for premium playlist URLs (the "playlist thing" that bypasses premium)
            playlist_pattern = r'href="([^"]*playlist-cat-jw[^"]*)"'
            playlist_matches = re.findall(playlist_pattern, page_content)

            for playlist_path in playlist_matches:
                if not playlist_path.startswith('http'):
                    playlist_url = urllib.parse.urljoin(episode_url, playlist_path)
                else:
                    playlist_url = playlist_path

                control.log(f"Found premium workaround playlist: {playlist_url}")

                # Get the RSS feed content
                playlist_resp = self._make_request(playlist_url)
                if playlist_resp:
                    # Extract the actual video URL from RSS
                    rss_url_match = re.search(r'<link[^>]*>([^<]+)</link>', playlist_resp)
                    if rss_url_match:
                        video_url = rss_url_match.group(1).strip()
                        if video_url and video_url.startswith('http'):
                            control.log(f"Premium workaround found video URL: {video_url}")
                            return video_url

        except Exception as e:
            control.log(f"Premium workaround check failed: {str(e)}")

        return None

    def _clean_title(self, title):
        """Clean title for better search results"""
        if not title:
            return ""

        # Remove common patterns that might interfere with search
        cleaned = re.sub(r'\s*\([^)]*\)', '', title)  # Remove parentheses content
        cleaned = re.sub(r'\s*\[[^\]]*\]', '', cleaned)  # Remove bracket content
        cleaned = re.sub(r'\s*:\s*[^:]*$', '', cleaned)  # Remove subtitle after colon
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Normalize whitespace

        return cleaned

    def _normalize_series_base_title(self, title):
        base = (title or '').strip()
        for suffix in (
            ' english subbed',
            ' english dubbed',
            ' english dub',
            ' subbed',
            ' dubbed',
        ):
            if base.lower().endswith(suffix):
                base = base[:-len(suffix)].strip()
        return base

    def _is_dub_episode(self, episode_data):
        episode_title = episode_data.get('title', '').lower()
        series_title = episode_data.get('series_title', '').lower()
        combined = f"{episode_title} {series_title}"

        sub_markers = ('english subbed', 'english sub', ' subbed')
        dub_markers = ('english dubbed', 'english dub', ' dubbed')

        if any(marker in combined for marker in sub_markers):
            return False
        if any(marker in combined for marker in dub_markers):
            return True
        if re.search(r'\bdub(?:bed)?\b', combined) and not re.search(r'\bsub(?:bed)?\b', combined):
            return True
        return False

    def _episode_lang_key(self, episode_data):
        return 3 if self._is_dub_episode(episode_data) else 2

    def _get_series_variants(self, series_results):
        if not series_results:
            return []

        anchor_base = self._normalize_series_base_title(series_results[0]['title']).lower()
        variants = []
        seen_urls = set()

        for series in series_results:
            series_base = self._normalize_series_base_title(series['title']).lower()
            same_show = (
                series_base == anchor_base
                or self._titles_match(series_results[0]['title'], series['title'])
            )
            if not same_show:
                continue
            if series['url'] in seen_urls:
                continue
            seen_urls.add(series['url'])
            variants.append(series)

        return variants or [series_results[0]]

    def _pick_sub_and_dub_episodes(self, episode_matches):
        picked = {}
        for match in episode_matches:
            lang = self._episode_lang_key(match)
            existing = picked.get(lang)
            if not existing or match.get('priority', 99) < existing.get('priority', 99):
                picked[lang] = match
        return list(picked.values())

    def _parse_episode_range(self, range_str):
        """Parse episode range string like '1-13' or '13-25'"""
        if not range_str or '-' not in range_str:
            return None

        try:
            parts = range_str.split('-')
            if len(parts) >= 2:
                start = int(parts[0])
                end = int(parts[1])
                return (start, end)
        except (ValueError, IndexError):
            pass

        return None

    def _search_and_get_episodes(self, search_title, season, mapped_episode, version_type):
        """
        Search for a series and return matching SUB and DUB episodes when available.
        Returns a list of episode dicts (0-2 items), not a single episode.
        """
        try:
            series_results = self.search_series(search_title)

            if not series_results:
                control.log(f"No series found for {version_type} search: {search_title}")
                return []

            series_to_check = self._get_series_variants(series_results)
            for series in series_to_check:
                control.log(f"Checking series variant: {series['title']}")

            all_episodes = []

            for series in series_to_check:
                control.log(f"Getting episodes from: {series['title']}")
                episodes = self.get_episodes_from_series(series['url'])

                if not episodes:
                    control.log(f"No episodes found in series: {series['title']}")
                    continue

                for episode in episodes:
                    episode['series_title'] = series['title']
                    episode['series_url'] = series['url']

                all_episodes.extend(episodes)

            if not all_episodes:
                control.log("No episodes found in any series variant")
                return []

            episode_matches = self.find_episode_match(all_episodes, season, mapped_episode, search_title)
            if not episode_matches:
                control.log(f"No matching episode found in any series variant for Season {season} Episode {mapped_episode}")
                if all_episodes:
                    control.log("Sample episodes found:")
                    for i, ep in enumerate(all_episodes[:5]):
                        control.log(f"{i + 1}. {ep['title']} (from {ep['series_title']})")
                return []

            picked_episodes = self._pick_sub_and_dub_episodes(episode_matches)
            for episode in picked_episodes:
                lang_label = "DUB" if self._episode_lang_key(episode) == 3 else "SUB"
                control.log(
                    f"Found {version_type} {lang_label} episode in '{episode['series_title']}': "
                    f"{episode['title']} ({episode['match_type']})"
                )
            return picked_episodes

        except Exception as e:
            control.log(f"Error in {version_type} search: {e}")
            return []

    def _search_and_get_episode(self, search_title, season, mapped_episode, version_type):
        episodes = self._search_and_get_episodes(search_title, season, mapped_episode, version_type)
        return episodes[0] if episodes else None

    def truncate_search_query(self, title, max_length=40):
        """Truncate search query to fit character limit while keeping important info"""
        query = urllib.parse.quote_plus(title)

        if len(query) <= max_length:
            return query, title

        words = title.split()

        while len(words) > 1:
            words = words[1:]
            test_title = ' '.join(words)
            test_query = urllib.parse.quote_plus(test_title)
            if len(test_query) <= max_length:
                return test_query, test_title

        if len(words) == 1:
            truncated = words[0][:max_length]
            return truncated, truncated

        return query[:max_length], title

    def search_series(self, title, search_type='series'):
        """Search for series on wcostream using proven POST method with smart character limits"""
        # Try full-length search first
        full_query = urllib.parse.quote_plus(title)

        if len(full_query) <= 40:
            # Use full-length search for shorter titles
            query, search_title = full_query, title
            control.log(f"Using full-length search: {query} (length: {len(full_query)})")
        else:
            # Use truncation for longer titles
            query, search_title = self.truncate_search_query(title)
            control.log(f"Using truncated search: {query} (length: {len(query)})")

        data = {
            'catara': query,
            'konuara': search_type
        }

        try:
            response = self._make_request(f'{self._BASE_URL}search', method='POST', data=data)
            if not response:
                return []

            # First try WNT2's specific parsing with response markers
            series_results = []

            # Look for the search section using WNT2's start marker
            if 'aramamotoru' in response:
                start_pos = response.find('aramamotoru')
                end_pos = response.find('cizgiyazisi', start_pos)
                if start_pos != -1 and end_pos != -1:
                    search_section = response[start_pos:end_pos]

                    # Use WNT2's regex pattern
                    pattern = r'<a href="(?P<link>[^"]+)[^>]*>(?P<name>[^<]+)</a>'
                    matches = re.finditer(pattern, search_section)

                    for i, match in enumerate(matches):
                        href = match.group('link')
                        title_text = match.group('name').strip()

                        if href and href.startswith('/'):
                            href = href[1:]

                        if href:
                            series_results.append({
                                'index': i,
                                'title': title_text,
                                'href': href,
                                'url': f"{self._BASE_URL}{href}",
                                'search_used': search_title
                            })

            # Fallback to BeautifulSoup if regex fails
            if not series_results:
                soup = BeautifulSoup(response, 'html.parser')
                series_containers = soup.find_all('div', class_='cerceve')

                for i, container in enumerate(series_containers):
                    title_div = container.find('div', class_='aramadabaslik')
                    if title_div:
                        link = title_div.find('a')
                        if link:
                            href = link.get('href')
                            title_text = link.get('title') or link.text.strip()

                            if href and href.startswith('/'):
                                href = href[1:]

                            if href:
                                series_results.append({
                                    'index': i,
                                    'title': title_text,
                                    'href': href,
                                    'url': f"{self._BASE_URL}{href}",
                                    'search_used': search_title
                                })

            if series_results:
                control.log(f"Found {len(series_results)} series results using POST search")
                return series_results[:10]  # Limit results
            else:
                control.log(f"No series found for search: {title}")

        except Exception as e:
            control.log(f"Error searching with query '{query}': {e}")

        return []

    def get_episodes_from_series(self, series_url):
        """Get all episodes from a series page"""
        try:
            control.log(f"Getting episodes from: {series_url}")
            response = self._make_request(series_url)
            if not response:
                return []

            soup = BeautifulSoup(response, 'html.parser')

            episodes = []
            episode_links = soup.find_all('a', href=re.compile(r'episode'))

            for link in episode_links:
                href = link.get('href')
                title_text = link.get('title') or link.text.strip()

                if href and title_text:
                    episodes.append({
                        'title': title_text,
                        'href': href,
                        'url': f"{self._BASE_URL}{href}" if not href.startswith('http') else href
                    })

            return episodes
        except Exception as e:
            control.log(f"Error getting episodes from {series_url}: {e}")
            return []

    def _episode_season_in_title(self, title):
        match = re.search(r'season\s+(\d+)', title or '', re.I)
        return int(match.group(1)) if match else None

    def _is_bonus_or_crossover_episode(self, title):
        """True when the link title names another show before the episode (e.g. B.King Episode 17)."""
        match = re.search(r'episode\s+(\d+)', title or '', re.I)
        if not match:
            return False
        prefix = title[:match.start()].strip()
        if not prefix:
            return False
        prefix = re.sub(r'^season\s+\d+\s*', '', prefix, flags=re.I).strip()
        if not prefix:
            return False
        if re.match(
            r'^(english\s+(subbed|dubbed)|subbed|dubbed|fullhd|fhd|hd|sd|\d+k)$',
            prefix,
            re.I,
        ):
            return False
        return True

    def _refine_episode_matches(self, matches, target_season, target_episode, search_title=None):
        """
        Refine episode-number matches from a series page.

        WCO episode link titles are like 'Episode 17 English Subbed' — they do not contain
        the series name, so fuzzy-matching them against the search query always fails.
        Series identity is already validated when picking the series from search results.
        """
        if not matches:
            return []

        strong = [m for m in matches if m.get('priority', 99) <= 2]
        if strong:
            matches = strong

        refined = []
        for ep in matches:
            title = ep.get('title', '')
            if self._is_bonus_or_crossover_episode(title):
                control.log(
                    "WatchNixtoons2: skipping bonus/crossover episode '{0}'".format(title),
                    level='info',
                )
                continue

            ep_season = self._episode_season_in_title(title)
            if target_season is not None and ep_season is not None and ep_season != int(target_season):
                control.log(
                    "WatchNixtoons2: skipping season {0} link (wanted season {1}): '{2}'".format(
                        ep_season, target_season, title
                    ),
                    level='info',
                )
                continue

            refined.append(ep)

        if refined:
            control.log(
                "WatchNixtoons2: kept {0} episode match(es) for S{1}E{2}".format(
                    len(refined), target_season or '?', target_episode
                ),
                level='info',
            )
            return refined

        if search_title:
            for ep in matches:
                series_title = ep.get('series_title', '')
                if series_title and self._titles_match(search_title, series_title):
                    refined.append(ep)
            if refined:
                control.log(
                    "WatchNixtoons2: recovered {0} weak match(es) via series title".format(len(refined)),
                    level='info',
                )

        return refined

    def _is_better_episode(self, candidate, existing):
        """Prefer lower episode priority, standard titles, then fuzzy title rank."""
        if not existing:
            return True

        candidate_priority = candidate.get('priority', 99)
        existing_priority = existing.get('priority', 99)
        if candidate_priority != existing_priority:
            return candidate_priority < existing_priority

        cand_bonus = self._is_bonus_or_crossover_episode(candidate.get('title', ''))
        exist_bonus = self._is_bonus_or_crossover_episode(existing.get('title', ''))
        if cand_bonus != exist_bonus:
            return not cand_bonus

        candidate_rank = candidate.get('title_rank', 99)
        existing_rank = existing.get('title_rank', 99)
        return candidate_rank < existing_rank

    def find_episode_match(self, episodes, target_season, target_episode, search_title=None):
        """Find the matching episode from the episode list using original priority system"""
        matches = []

        for episode in episodes:
            title_text = episode['title']

            # Pattern 1: Exact season and episode match
            if target_season is not None:
                season_episode_pattern = re.compile(
                    rf'season\s+{target_season}\s+episode\s+{target_episode}(?!\d)',
                    re.IGNORECASE
                )
                if season_episode_pattern.search(title_text):
                    episode['match_type'] = 'Perfect Match (Season + Episode)'
                    episode['priority'] = 1
                    matches.append(episode)
                    continue

            # Pattern 2: Episode only match (for shows without clear seasons)
            episode_only_pattern = re.compile(rf'episode\s+{target_episode}(?!\d)', re.IGNORECASE)
            if episode_only_pattern.search(title_text) and not re.search(r'season\s+\d+', title_text, re.IGNORECASE):
                episode['match_type'] = 'Episode Only Match'
                episode['priority'] = 2
                matches.append(episode)
                continue

            # Pattern 3: Contains target episode number (broader match)
            episode_number_pattern = re.compile(rf'\b{target_episode}\b(?!\d)', re.IGNORECASE)
            if episode_number_pattern.search(title_text):
                episode['match_type'] = 'Episode Number Match'
                episode['priority'] = 3
                matches.append(episode)

        # Sort by priority (lower number = higher priority)
        matches.sort(key=lambda x: x['priority'])

        matches = self._refine_episode_matches(
            matches, target_season, target_episode, search_title=search_title
        )

        return matches

    def _titles_match(self, search_title, series_title):
        """Check if two titles match"""
        search_lower = search_title.lower()
        series_lower = series_title.lower()

        # Remove common words and punctuation for better matching
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']

        def clean_for_matching(title):
            # Remove punctuation and extra spaces
            cleaned = re.sub(r'[^\w\s]', ' ', title)
            words = [word for word in cleaned.split() if word.lower() not in common_words]
            return ' '.join(words).lower()

        clean_search = clean_for_matching(search_lower)
        clean_series = clean_for_matching(series_lower)

        # Check various matching strategies
        if clean_search in clean_series or clean_series in clean_search:
            return True

        # Check if most words match
        search_words = set(clean_search.split())
        series_words = set(clean_series.split())

        if search_words and series_words:
            overlap = len(search_words.intersection(series_words))
            total = len(search_words.union(series_words))
            similarity = overlap / total if total > 0 else 0

            if similarity >= 0.6:  # 60% word overlap
                return True

        return False

    def _extract_iframe_sources(self, page_content, version_type, lang, episode_data):
        """Fallback extraction if advanced resolution returned nothing."""
        episode_url = episode_data.get('url', '')
        title = episode_data.get('title', 'Unknown')
        embed_url, is_m3u8_player = self._find_embed_url(page_content, episode_url)
        if not embed_url:
            return []

        player_html, resolved_embed_url = self._fetch_player_html(embed_url, episode_url)
        if not player_html:
            return []

        return self._extract_streams_from_player_html(
            player_html,
            resolved_embed_url,
            title,
            version_type,
            lang,
            is_m3u8_player,
        )
