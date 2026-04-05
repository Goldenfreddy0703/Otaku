import pickle
import re
import time
import urllib.parse
import json
from bs4 import BeautifulSoup
from resources.lib.ui import control, database, client
from resources.lib.ui.BrowserBase import BrowserBase
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class Sources(BrowserBase):
    _BASE_URL = 'https://www.wcostream.tv/'
    _WNT2_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'

    def __init__(self):
        super().__init__()
        self.request_delay = 1.2  # Conservative rate limiting to avoid blocks
        self._cache = {}  # Simple response cache
        self._cache_lock = threading.Lock()
        self._last_request_time = 0
        # Clear any previous session state
        client.clear_session()

    def _make_request(self, url, method='GET', data=None, headers=None, timeout=8, use_cache=True):
        """Make a request using enhanced client with WNT2's proven Cloudflare bypass approach"""

        # Check cache first for GET requests
        cache_key = f"{method}:{url}"
        if use_cache and method.upper() == 'GET':
            with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

        try:
            # Use WNT2's proven headers approach
            my_headers = {
                'User-Agent': self._WNT2_UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Cache-Control': 'no-cache',
            }

            if headers:
                my_headers.update(headers)

            start_time = time.time()

            # Rate limiting
            time_since_last = start_time - self._last_request_time
            if time_since_last < self.request_delay:
                time.sleep(self.request_delay - time_since_last)

            # Try the request with automatic TLS retry on Cloudflare 403
            # The enhanced client now handles TLS adapter switching automatically
            if method.upper() == 'POST':
                response = client.session_request(
                    url,
                    method='POST',
                    data=data,
                    headers=my_headers,
                    timeout=timeout,
                    verify=False
                )
            else:
                response = client.session_request(
                    url,
                    method='GET',
                    headers=my_headers,
                    timeout=timeout,
                    verify=False
                )

            self._last_request_time = time.time()

            # response is now a string from session_request (legacy)
            # We should update to use client.Session() instead for Response objects
            if response:
                # Cache successful GET responses
                if use_cache and method.upper() == 'GET':
                    with self._cache_lock:
                        self._cache[cache_key] = response
                        # Keep cache size reasonable
                        if len(self._cache) > 50:
                            # Remove oldest entries
                            oldest_keys = list(self._cache.keys())[:10]
                            for key in oldest_keys:
                                del self._cache[key]

                return response
            else:
                control.log(f"Request failed for {url}")
                return None

        except Exception as e:
            control.log(f"Client request failed for {url}: {str(e)}", "error")
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

        # Collect all unique search titles
        search_titles = []
        if romaji_title:
            search_titles.append(("romaji", romaji_title))
        if english_title:
            search_titles.append(("english", english_title))
        if clean_title:
            search_titles.append(("clean", clean_title))

        # Search for episodes using all titles concurrently for faster results
        found_episodes = {}  # Use dict to avoid duplicates by URL

        def search_title_worker(search_data):
            search_type, search_title = search_data
            control.log(f"Searching for {search_type} version with title: {search_title}")
            return self._search_and_get_episode(search_title, season, mapped_episode, search_type)

        # Process searches concurrently
        with ThreadPoolExecutor(max_workers=control.max_threads) as executor:
            future_to_search = {executor.submit(search_title_worker, search_data): search_data for search_data in search_titles}

            for future in as_completed(future_to_search):
                search_data = future_to_search[future]
                search_type = search_data[0]
                try:
                    episode_result = future.result()
                    if episode_result:
                        # Use URL as key to avoid duplicates
                        episode_url = episode_result['url']
                        if episode_url not in found_episodes:
                            found_episodes[episode_url] = episode_result
                            control.log(f"Added {search_type} episode: {episode_result['title']}")
                        else:
                            control.log(f"Duplicate episode found for {search_type}, skipping")
                except Exception as e:
                    control.log(f"Search failed for {search_type}: {str(e)}")

        # Convert found episodes to sources with concurrent processing
        sources = []
        sources_found_per_lang = {}  # Track which languages we've found sources for

        control.log(f"WatchNixtoons2: Found {len(found_episodes)} episode variants to process")

        def extract_sources_worker(episode_data):
            # Determine if it's SUB or DUB based on title/series
            episode_title = episode_data.get('title', '').lower()
            is_dub = ('english dubbed' in episode_title)
            version_type = "DUB" if is_dub else "SUB"
            lang = 3 if is_dub else 2

            # Early exit check - skip if we already have sources for this language
            if lang in sources_found_per_lang:
                control.log(f"WatchNixtoons2: Skipping '{version_type}' - already have sources")
                return None

            control.log(f"WatchNixtoons2: Processing '{version_type}' episode: {episode_data.get('title', 'Unknown')}")

            # Get the episode page content
            resp = self._make_request(episode_data['url'])
            if resp:
                # First try to find direct video sources using the advanced method
                advanced_sources = self._extract_advanced_sources(episode_data['url'], resp, version_type, lang, episode_data['title'])
                if advanced_sources:
                    return (advanced_sources, lang)
                else:
                    # Fallback to basic iframe extraction
                    iframe_sources = self._extract_iframe_sources(resp, version_type, lang, episode_data)
                    if iframe_sources:
                        return (iframe_sources, lang)
            else:
                control.log(f"Failed to get episode page: {episode_data['url']}")
            return None

        # Process episodes concurrently for faster source extraction
        with ThreadPoolExecutor(max_workers=control.max_threads) as executor:
            future_to_episode = {executor.submit(extract_sources_worker, episode_data): episode_data for episode_data in found_episodes.values()}

            for future in as_completed(future_to_episode):
                episode_data = future_to_episode[future]
                try:
                    result = future.result()
                    if result:
                        episode_sources, lang = result
                        sources.extend(episode_sources)
                        sources_found_per_lang[lang] = True
                        control.log(f"WatchNixtoons2: Found {len(episode_sources)} sources for lang {lang}")

                        # If we have both SUB and DUB, we can stop early
                        if len(sources_found_per_lang) >= 2:
                            control.log("WatchNixtoons2: Found sources for both SUB and DUB - stopping early")
                            break
                except Exception as e:
                    control.log(f"Source extraction failed for {episode_data.get('title', 'Unknown')}: {str(e)}")

        control.log(f"WatchNixtoons2: Returning {len(sources)} total sources")
        return sources

    def _extract_advanced_sources(self, episode_url, page_content, version_type, lang, title):
        """Extract sources using WNT2's exact approach with optimized server API detection"""
        sources = []

        try:
            # FIRST: Try WNT2's premium workaround (the "playlist thing")
            premium_url = self._premium_workaround_check(page_content, episode_url)
            if premium_url:
                source = {
                    'release_title': f"{title} - {version_type}",
                    'hash': f"{premium_url}|{urllib.parse.urlencode({'User-Agent': self._WNT2_UA, 'Referer': episode_url})}",
                    'type': 'direct',
                    'quality': 3,  # Premium usually has best quality (1080p)
                    'debrid_provider': '',
                    'provider': 'watchnixtoons2',
                    'size': 'NA',
                    'seeders': 0,
                    'byte_size': 0,
                    'info': [f'Premium {version_type}'],
                    'lang': lang,
                    'channel': 3,
                    'sub': 1
                }
                sources.append(source)
                control.log(f"Added premium workaround source: {premium_url}")

            # SECOND: Use WNT2's exact server API detection approach (optimized)
            has_getjson = 'getJSON(' in page_content
            has_iframe = '<iframe' in page_content

            # Try to find server API URLs even without the getvid indicator
            source_url = None

            if 'getvid?evid' in page_content:
                # Check for redirected URL type first (like WNT2)
                if 'getRedirectedUrl(videoUrl)' in page_content:
                    # Type 1: jQuery getJSON with redirect pattern
                    match = re.search(r'\$\.getJSON\(\"([^\"]+)\"', page_content, re.DOTALL)
                    if match:
                        source_url = match.group(1)
                        if not source_url.startswith('http'):
                            source_url = "https://embed.wcostream.com/" + source_url
                        source_url += "&json"
                        control.log(f"Found redirected getJSON API: {source_url}")
                else:
                    # Type 2: Direct getvidlink API pattern
                    match = re.search(r'"(/inc/embed/getvidlink[^"]+)', page_content, re.DOTALL)
                    if match:
                        source_url = self._BASE_URL.rstrip('/') + match.group(1)
                        control.log(f"Found direct getvidlink API: {source_url}")

            # ALTERNATIVE: Look for getJSON patterns even without getvid indicator
            elif has_getjson:
                # Look for any getJSON calls that might be video APIs
                getjson_matches = re.findall(r'\$\.getJSON\(["\']([^"\']+)["\']', page_content)
                for match in getjson_matches:
                    # Skip obvious non-video APIs
                    if any(skip in match.lower() for skip in ['firebase', 'analytics', 'ads', 'login', 'check']):
                        continue

                    if not match.startswith('http'):
                        if match.startswith('/'):
                            source_url = self._BASE_URL.rstrip('/') + match
                        else:
                            source_url = "https://embed.wcostream.com/" + match
                    else:
                        source_url = match

                    # Add &json if it looks like it needs it
                    if 'embed' in source_url and 'json' not in source_url:
                        source_url += "&json"

                    control.log(f"Trying getJSON API: {source_url}")
                    break  # Try the first promising one

            # If we found a server API URL, try to extract qualities
            if source_url:
                control.log(f"Requesting server API: {source_url}")

                api_headers = {
                    'Accept': '*/*',
                    'Referer': episode_url,
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self._WNT2_UA
                }

                server_resp = self._make_request(source_url, headers=api_headers, use_cache=False)
                if server_resp:
                    try:
                        json_data = json.loads(server_resp)
                        control.log(f"Server API response keys: {list(json_data.keys())}")

                        # Extract quality tokens (WNT2 style)
                        token_sd = json_data.get('enc', '')  # Standard definition
                        token_hd = json_data.get('hd', '')   # High definition
                        token_fhd = json_data.get('fhd', '')  # Full high definition

                        server_base_url = json_data.get('server', '')
                        if server_base_url and not server_base_url.endswith('/getvid?evid='):
                            server_base_url = server_base_url.rstrip('/') + '/getvid?evid='

                        # Build sources for each quality level
                        quality_sources = []
                        if token_sd:
                            quality_sources.append(('SD', token_sd, 1))
                        if token_hd:
                            quality_sources.append(('HD', token_hd, 2))
                        if token_fhd:
                            quality_sources.append(('FHD', token_fhd, 3))

                        # Create source entries
                        for quality_label, token, quality_num in quality_sources:
                            if server_base_url and token:
                                video_url = server_base_url + token

                                video_headers = {
                                    'User-Agent': self._WNT2_UA,
                                    'Referer': episode_url,
                                    'Accept': '*/*'
                                }

                                hlink = f"{video_url}|{urllib.parse.urlencode(video_headers)}"
                                source = {
                                    'release_title': f"{title} - {version_type}",
                                    'hash': hlink,
                                    'type': 'direct',
                                    'quality': quality_num,
                                    'debrid_provider': '',
                                    'provider': 'watchnixtoons2',
                                    'size': 'NA',
                                    'seeders': 0,
                                    'byte_size': 0,
                                    'info': [f'API {quality_label} {version_type}'],
                                    'lang': lang,
                                    'channel': 3,
                                    'sub': 1
                                }
                                sources.append(source)
                                control.log(f"Added WNT2-style source: {quality_label} - {video_url}")

                        # Also check for backup CDN (like WNT2)
                        cdn_backup = json_data.get('cdn', '')
                        if cdn_backup and (token_sd or token_hd or token_fhd):
                            backup_token = token_fhd or token_hd or token_sd
                            backup_url = cdn_backup.rstrip('/') + '/getvid?evid=' + backup_token

                            backup_headers = {
                                'User-Agent': self._WNT2_UA,
                                'Referer': episode_url,
                                'Accept': '*/*'
                            }

                            hlink = f"{backup_url}|{urllib.parse.urlencode(backup_headers)}"
                            source = {
                                'release_title': f"{title} - {version_type}",
                                'hash': hlink,
                                'type': 'direct',
                                'quality': 2,  # Default backup quality
                                'debrid_provider': '',
                                'provider': 'watchnixtoons2',
                                'size': 'NA',
                                'seeders': 0,
                                'byte_size': 0,
                                'info': [f'CDN Backup {version_type}'],
                                'lang': lang,
                                'channel': 3,
                                'sub': 1
                            }
                            sources.append(source)
                            control.log(f"Added CDN backup source: {backup_url}")

                    except json.JSONDecodeError as e:
                        control.log(f"Failed to parse server JSON response: {str(e)}")
                        control.log(f"Response content: {server_resp[:500]}")
                else:
                    control.log("Failed to get server API response")
            else:
                control.log("No server API URL found - trying fallback patterns")

                # FALLBACK 1: Extract and process iframe content for video APIs (optimized)
                if has_iframe:
                    control.log("Found iframe - extracting iframe sources for video APIs")
                    iframe_matches = re.findall(r'<iframe[^>]+src="([^"]+)"', page_content, re.IGNORECASE)

                    # Filter and process only promising iframes concurrently
                    promising_iframes = []
                    for iframe_url in iframe_matches[:3]:  # Limit to first 3 iframes for speed
                        # Skip ads and non-video iframes
                        if any(skip in iframe_url.lower() for skip in ['ads', 'analytics', 'disqus', 'facebook', 'twitter']):
                            continue

                        if not iframe_url.startswith('http'):
                            if iframe_url.startswith('//'):
                                iframe_url = 'https:' + iframe_url
                            elif iframe_url.startswith('/'):
                                iframe_url = urllib.parse.urljoin(episode_url, iframe_url)
                            else:
                                iframe_url = urllib.parse.urljoin(episode_url, iframe_url)

                        promising_iframes.append(iframe_url)

                    # Process iframes concurrently for faster extraction
                    def process_iframe_worker(iframe_url):
                        control.log(f"Processing iframe: {iframe_url}")

                        iframe_headers = {
                            'User-Agent': self._WNT2_UA,
                            'Referer': episode_url,
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                        }

                        iframe_content = self._make_request(iframe_url, headers=iframe_headers, use_cache=False)
                        if iframe_content:
                            return self._process_iframe_content(iframe_content, iframe_url, episode_url, title, version_type, lang)
                        return []

                    # Process iframes concurrently
                    if promising_iframes:
                        with ThreadPoolExecutor(max_workers=control.max_threads) as executor:
                            iframe_futures = {executor.submit(process_iframe_worker, iframe_url): iframe_url for iframe_url in promising_iframes}

                            for future in as_completed(iframe_futures):
                                try:
                                    iframe_sources = future.result()
                                    if iframe_sources:
                                        sources.extend(iframe_sources)
                                        # Break after first successful iframe to save time
                                        break
                                except Exception as e:
                                    control.log(f"Iframe processing failed: {str(e)}")

                # FALLBACK 2: Basic iframe source if no APIs found
                if not sources or len(sources) == 0:
                    control.log("No API sources found, adding basic iframe fallback")
                    iframe_pattern = re.search(r'<iframe[^>]+src="([^"]+)"', page_content)
                    if iframe_pattern:
                        iframe_url = iframe_pattern.group(1)
                        if not iframe_url.startswith('http'):
                            iframe_url = urllib.parse.urljoin(episode_url, iframe_url)

                        source = {
                            'release_title': f"{title} - {version_type}",
                            'hash': f"{iframe_url}|{urllib.parse.urlencode({'User-Agent': self._WNT2_UA, 'Referer': episode_url})}",
                            'type': 'direct',
                            'quality': 2,  # Default
                            'debrid_provider': '',
                            'provider': 'watchnixtoons2',
                            'size': 'NA',
                            'seeders': 0,
                            'byte_size': 0,
                            'info': [f'Basic Iframe {version_type}'],
                            'lang': lang,
                            'channel': 3,
                            'sub': 1
                        }
                        sources.append(source)
                        control.log(f"Added basic iframe source: {iframe_url}")

        except Exception as e:
            control.log(f"Advanced source extraction failed: {str(e)}", "error")

        control.log(f"WNT2 extraction completed - Total sources found: {len(sources)}")
        for i, source in enumerate(sources, 1):
            info_str = ' '.join(source.get('info', []))
            control.log(f"Source {i}: {info_str} - Quality: {source.get('quality')}")

        return sources

    def _process_iframe_content(self, iframe_content, iframe_url, episode_url, title, version_type, lang):
        """Process iframe content for video APIs - optimized helper method"""
        sources = []

        # Check iframe for the patterns we missed in main page
        iframe_has_getvid = 'getvid?evid' in iframe_content
        iframe_has_getjson = 'getJSON(' in iframe_content
        iframe_has_getvidlink = '/inc/embed/getvidlink' in iframe_content

        # Try to find video APIs in iframe content
        if iframe_has_getvid or iframe_has_getjson or iframe_has_getvidlink:
            iframe_source_url = None

            if iframe_has_getjson:
                # Look for getJSON calls in iframe
                getjson_matches = re.findall(r'\$\.getJSON\(["\']([^"\']+)["\']', iframe_content)
                for match in getjson_matches:
                    if any(skip in match.lower() for skip in ['firebase', 'analytics', 'ads', 'login']):
                        continue

                    if not match.startswith('http'):
                        if match.startswith('/'):
                            iframe_source_url = urllib.parse.urljoin(iframe_url, match)
                        else:
                            iframe_source_url = "https://embed.wcostream.com/" + match
                    else:
                        iframe_source_url = match

                    if 'embed' in iframe_source_url and 'json' not in iframe_source_url:
                        iframe_source_url += "&json"

                    control.log(f"Found iframe getJSON API: {iframe_source_url}")
                    break

            elif iframe_has_getvidlink:
                # Look for getvidlink in iframe
                match = re.search(r'"(/inc/embed/getvidlink[^"]+)', iframe_content, re.DOTALL)
                if match:
                    iframe_source_url = urllib.parse.urljoin(iframe_url, match.group(1))
                    control.log(f"Found iframe getvidlink API: {iframe_source_url}")

            # If we found an API in iframe, try to extract qualities
            if iframe_source_url:
                control.log(f"Requesting iframe server API: {iframe_source_url}")

                api_headers = {
                    'Accept': '*/*',
                    'Referer': iframe_url,
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self._WNT2_UA
                }

                iframe_api_resp = self._make_request(iframe_source_url, headers=api_headers, use_cache=False)
                if iframe_api_resp:
                    try:
                        iframe_json_data = json.loads(iframe_api_resp)
                        control.log(f"Iframe API response keys: {list(iframe_json_data.keys())}")

                        # Extract quality tokens from iframe API
                        iframe_token_sd = iframe_json_data.get('enc', '')
                        iframe_token_hd = iframe_json_data.get('hd', '')
                        iframe_token_fhd = iframe_json_data.get('fhd', '')

                        iframe_server_base_url = iframe_json_data.get('server', '')
                        if iframe_server_base_url and not iframe_server_base_url.endswith('/getvid?evid='):
                            iframe_server_base_url = iframe_server_base_url.rstrip('/') + '/getvid?evid='

                        control.log(f"Iframe quality tokens - SD: {bool(iframe_token_sd)}, HD: {bool(iframe_token_hd)}, FHD: {bool(iframe_token_fhd)}")

                        # Build sources from iframe API
                        iframe_quality_sources = []
                        if iframe_token_sd:
                            iframe_quality_sources.append(('SD', iframe_token_sd, 1))
                        if iframe_token_hd:
                            iframe_quality_sources.append(('HD', iframe_token_hd, 2))
                        if iframe_token_fhd:
                            iframe_quality_sources.append(('FHD', iframe_token_fhd, 3))

                        for quality_label, token, quality_num in iframe_quality_sources:
                            if iframe_server_base_url and token:
                                video_url = iframe_server_base_url + token

                                video_headers = {
                                    'User-Agent': self._WNT2_UA,
                                    'Referer': iframe_url,
                                    'Accept': '*/*'
                                }

                                hlink = f"{video_url}|{urllib.parse.urlencode(video_headers)}"
                                source = {
                                    'release_title': f"{title} - {version_type}",
                                    'hash': hlink,
                                    'type': 'direct',
                                    'quality': quality_num,
                                    'debrid_provider': '',
                                    'provider': 'watchnixtoons2',
                                    'size': 'NA',
                                    'seeders': 0,
                                    'byte_size': 0,
                                    'info': [f'Iframe {quality_label} {version_type}'],
                                    'lang': lang,
                                    'channel': 3,
                                    'sub': 1
                                }
                                sources.append(source)
                                control.log(f"Added iframe API source: {quality_label} - {video_url}")

                    except json.JSONDecodeError as e:
                        control.log(f"Failed to parse iframe API JSON: {str(e)}")

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

    def _search_and_get_episode(self, search_title, season, mapped_episode, version_type):
        """
        Search for a series and get the matching episode using original proven POST method
        Returns the episode dict if found, None if not found
        """
        try:
            # Search for the series using proven POST method
            series_results = self.search_series(search_title)

            if not series_results:
                control.log(f"No series found for {version_type} search: {search_title}")
                return None

            # Get the first series as the base
            first_series = series_results[0]
            first_title = first_series['title'].strip()

            # Look for additional series with "English Subbed" or "English Dubbed"
            series_to_check = [first_series]

            for series in series_results[1:]:  # Check remaining series
                series_title = series['title'].strip()

                # Check if this series is the same base title with English Subbed/Dubbed
                if (series_title.lower().startswith(first_title.lower())
                        and ("english subbed" in series_title.lower() or "english dubbed" in series_title.lower())):
                    control.log(f"Found additional series variant: {series_title}")
                    series_to_check.append(series)

            # Prioritize series based on version_type
            if version_type == "romaji":
                # For romaji, prioritize "English Subbed" variants first
                series_to_check.sort(key=lambda x: 0 if "english subbed" in x['title'].lower() else 1)
            elif version_type == "english":
                # For english, prioritize "English Dubbed" variants second
                series_to_check.sort(key=lambda x: 0 if "english dubbed" in x['title'].lower() else 1)
            elif version_type == "clean":
                # For clean, prioritize "Raw" variants third
                series_to_check.sort(key=lambda x: x['index'])

            # Collect all episodes from all series variants
            all_episodes = []

            for series in series_to_check:
                control.log(f"Getting episodes from: {series['title']}")
                episodes = self.get_episodes_from_series(series['url'])

                if not episodes:
                    control.log(f"No episodes found in series: {series['title']}")
                    continue

                # Add series info to each episode for tracking
                for episode in episodes:
                    episode['series_title'] = series['title']
                    episode['series_url'] = series['url']

                all_episodes.extend(episodes)

            if not all_episodes:
                control.log("No episodes found in any series variant")
                return None

            # Find matching episodes from all collected episodes
            episode_matches = self.find_episode_match(all_episodes, season, mapped_episode)

            if episode_matches:
                best_match = episode_matches[0]
                control.log(f"Found {version_type} episode in '{best_match['series_title']}': {best_match['title']} ({best_match['match_type']})")
                return best_match
            else:
                control.log(f"No matching episode found in any series variant for Season {season} Episode {mapped_episode}")
                # Show some examples of available episodes
                if all_episodes:
                    control.log("Sample episodes found:")
                    for i, ep in enumerate(all_episodes[:5]):
                        control.log(f"{i + 1}. {ep['title']} (from {ep['series_title']})")
                return None

        except Exception as e:
            control.log(f"Error in {version_type} search: {e}")
            return None

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

    def find_episode_match(self, episodes, target_season, target_episode):
        """Find the matching episode from the episode list using original priority system"""
        matches = []

        for episode in episodes:
            title_text = episode['title']

            # Pattern 1: Exact season and episode match
            season_episode_pattern = re.compile(rf'season\s+{target_season}\s+episode\s+{target_episode}(?!\d)', re.IGNORECASE)
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
        """Basic iframe source extraction fallback"""
        sources = []

        try:
            iframe_pattern = re.search(r'<iframe[^>]+src="([^"]+)"', page_content)
            if iframe_pattern:
                iframe_url = iframe_pattern.group(1)
                episode_url = episode_data.get('url', '')

                if not iframe_url.startswith('http'):
                    iframe_url = urllib.parse.urljoin(episode_url, iframe_url)

                source = {
                    'release_title': f"{episode_data.get('title', 'Unknown')} - {version_type}",
                    'hash': f"{iframe_url}|{urllib.parse.urlencode({'User-Agent': self._WNT2_UA, 'Referer': episode_url})}",
                    'type': 'direct',
                    'quality': 2,  # Default quality
                    'debrid_provider': '',
                    'provider': 'watchnixtoons2',
                    'size': 'NA',
                    'seeders': 0,
                    'byte_size': 0,
                    'info': [f'Basic {version_type}'],
                    'lang': lang,
                    'channel': 3,
                    'sub': 1
                }
                sources.append(source)
                control.log(f"Added basic iframe source: {iframe_url}")

        except Exception as e:
            control.log(f"Basic iframe extraction failed: {str(e)}", "error")

        return sources
