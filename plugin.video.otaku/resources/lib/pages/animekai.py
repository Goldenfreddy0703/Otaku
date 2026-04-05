import json
import pickle
import re
import urllib.parse

from bs4 import BeautifulSoup
from resources.lib.ui import client, control, database, utils
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.megacloud_extractor import extract_megacloud_sources


class Sources(BrowserBase):
    _BASE_URL = 'https://animekai.to/'

    _AJAX_HEADERS = {
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://animekai.to/'
    }

    _ENCDEC_URL = 'https://enc-dec.app/api/enc-kai'
    _ENCDEC_DEC_KAI = 'https://enc-dec.app/api/dec-kai'
    _ENCDEC_DEC_MEGA = 'https://enc-dec.app/api/dec-mega'

    def get_sources(self, mal_id, episode):
        control.log(f"AnimeKAI: Getting sources for MAL ID {mal_id}, Episode {episode}")
        show = database.get_show(mal_id)
        kodi_meta = pickle.loads(show.get('kodi_meta'))
        title = kodi_meta.get('name')
        title = self._clean_title(title)

        srcs = ['sub', 'dub']
        if control.getInt('general.source') == 1:
            srcs.remove('dub')
        elif control.getInt('general.source') == 2:
            srcs.remove('sub')

        all_results = []

        # Step 1: Search for the anime
        slug = self._search_anime(title, kodi_meta)
        if not slug:
            control.log(f"AnimeKAI: No slug found for '{title}'")
            return all_results

        # Step 2: Get anime info to retrieve ani_id
        ani_id = self._get_ani_id(slug)
        if not ani_id:
            control.log(f"AnimeKAI: No ani_id found for slug '{slug}'")
            return all_results

        # Step 3: Fetch episodes and find the target episode token
        ep_token = self._get_episode_token(ani_id, episode)
        if not ep_token:
            control.log(f"AnimeKAI: No episode token found for episode {episode}")
            return all_results

        # Step 4: Fetch servers for the episode
        servers = self._get_servers(ep_token)
        if not servers:
            control.log(f"AnimeKAI: No servers found for episode {episode}")
            return all_results

        # Step 5: Process servers for each language
        for lang in srcs:
            lang_servers = servers.get(lang, [])
            if not lang_servers:
                continue

            control.log(f"AnimeKAI: Processing {len(lang_servers)} servers for '{lang}'")

            def process_server(server_info, _lang=lang):
                return self._resolve_and_build_source(server_info, title, episode, _lang)

            server_sources = utils.parallel_process(lang_servers, process_server)

            for server_source in server_sources:
                if server_source:
                    all_results.extend(server_source)

            if all_results:
                control.log(f"AnimeKAI: Found {len(all_results)} sources for '{lang}'")

        return all_results

    def _search_anime(self, title, kodi_meta):
        """Search AnimeKAI and return the best matching slug."""
        params = {'keyword': title}
        r = database.get(
            self._get_request,
            8,
            self._BASE_URL + 'ajax/anime/search',
            data=params,
            headers=self._AJAX_HEADERS
        )
        if not r:
            return None

        try:
            html = json.loads(r).get('result', {}).get('html', '')
        except (json.JSONDecodeError, AttributeError):
            return None

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        sitems = []
        for item in soup.find_all('a', class_='aitem'):
            title_tag = item.find('h6', class_='title')
            if title_tag:
                item_title = title_tag.get_text(strip=True)
                jp_title = title_tag.get('data-jp', '')
                href = item.get('href', '')
                slug = href.replace('/watch/', '') if href.startswith('/watch/') else href
                sitems.append({'title': item_title, 'jp_title': jp_title, 'slug': slug})

        if not sitems:
            return None

        # Try exact match first
        clean_title = self.clean_embed_title(title)
        for item in sitems:
            if clean_title == self.clean_embed_title(item['title']) or clean_title == self.clean_embed_title(item['jp_title']):
                return item['slug']

        # Try partial match
        if title[-1].isdigit():
            matches = [x['slug'] for x in sitems if title.lower() in x['title'].lower() or title.lower() in x['jp_title'].lower()]
        else:
            matches = [x['slug'] for x in sitems if (title.lower() + '  ') in (x['title'].lower() + '  ') or (title.lower() + '  ') in (x['jp_title'].lower() + '  ')]

        if not matches and ':' in title:
            short_title = title.split(':')[0]
            matches = [x['slug'] for x in sitems if (short_title.lower() + '  ') in (x['title'].lower() + '  ')]

        # Fall back to first result
        if not matches:
            matches = [sitems[0]['slug']]

        return matches[0] if matches else None

    def _get_ani_id(self, slug):
        """Get the anime_id (ani_id) from the watch page."""
        url = self._BASE_URL + 'watch/' + slug
        r = database.get(
            self._get_request,
            8,
            url,
            headers={'Referer': self._BASE_URL}
        )
        if not r:
            return None

        match = re.search(r'id="syncData"[^>]*>(.*?)</script>', r, re.DOTALL)
        if match:
            try:
                sync_data = json.loads(match.group(1))
                return sync_data.get('anime_id', '')
            except (json.JSONDecodeError, AttributeError):
                pass
        return None

    def _encode_token(self, text):
        """Encrypt a token using the enc-dec.app API."""
        response = client.get(self._ENCDEC_URL, params={'text': text}, timeout=15)
        if response and response.ok:
            try:
                data = response.json()
                if data.get('status') == 200:
                    return data.get('result')
            except (json.JSONDecodeError, AttributeError):
                pass
        return None

    def _decode_kai(self, text):
        """Decrypt AnimeKAI encrypted data."""
        response = client.post(self._ENCDEC_DEC_KAI, json_data={'text': text}, timeout=15)
        if response and response.ok:
            try:
                data = response.json()
                if data.get('status') == 200:
                    return data.get('result')
            except (json.JSONDecodeError, AttributeError):
                pass
        return None

    def _decode_mega(self, text):
        """Decrypt megacloud-style encrypted media data."""
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        response = client.post(self._ENCDEC_DEC_MEGA, json_data={'text': text, 'agent': ua}, timeout=15)
        if response:
            control.log(f"AnimeKAI: dec-mega API status: {response.status_code}, response (first 200): {response.text[:200] if response.text else 'EMPTY'}")
            if response.ok:
                try:
                    data = response.json()
                    control.log(f"AnimeKAI: dec-mega API parsed status: {data.get('status')}")
                    if data.get('status') == 200:
                        return data.get('result')
                except (json.JSONDecodeError, AttributeError) as e:
                    control.log(f"AnimeKAI: dec-mega JSON parse error: {str(e)}")
        else:
            control.log("AnimeKAI: dec-mega API returned no response")
        return None

    def _get_episode_token(self, ani_id, episode):
        """Fetch episode list and return the token for the target episode."""
        encoded = self._encode_token(ani_id)
        if not encoded:
            control.log("AnimeKAI: Token encryption failed for ani_id")
            return None

        params = {'ani_id': ani_id, '_': encoded}
        r = self._get_request(
            self._BASE_URL + 'ajax/episodes/list',
            data=params,
            headers=self._AJAX_HEADERS
        )
        if not r:
            return None

        try:
            html = json.loads(r).get('result', '')
        except (json.JSONDecodeError, AttributeError):
            return None

        soup = BeautifulSoup(html, "html.parser")
        episodes = soup.select('.eplist a')

        for ep in episodes:
            ep_num = ep.get('num', '')
            if str(ep_num) == str(episode):
                return ep.get('token', '')

        return None

    def _get_servers(self, ep_token):
        """Fetch available servers for an episode, grouped by language."""
        encoded = self._encode_token(ep_token)
        if not encoded:
            control.log("AnimeKAI: Token encryption failed for ep_token")
            return None

        params = {'token': ep_token, '_': encoded}
        r = self._get_request(
            self._BASE_URL + 'ajax/links/list',
            data=params,
            headers=self._AJAX_HEADERS
        )
        if not r:
            return None

        try:
            html = json.loads(r).get('result', '')
        except (json.JSONDecodeError, AttributeError):
            return None

        soup = BeautifulSoup(html, "html.parser")
        servers = {}
        for group in soup.select('.server-items'):
            lang = group.get('data-id', 'unknown')
            server_list = []
            for s in group.select('.server'):
                server_list.append({
                    'name': s.get_text(strip=True),
                    'server_id': s.get('data-sid', ''),
                    'episode_id': s.get('data-eid', ''),
                    'link_id': s.get('data-lid', ''),
                })
            servers[lang] = server_list

        return servers

    def _resolve_and_build_source(self, server_info, title, episode, lang):
        """Resolve a server link and build source dict(s)."""
        sources = []
        link_id = server_info.get('link_id', '')
        server_name = server_info.get('name', 'unknown')

        if not link_id:
            return sources

        try:
            encoded = self._encode_token(link_id)
            if not encoded:
                return sources

            r = self._get_request(
                self._BASE_URL + 'ajax/links/view',
                data={'id': link_id, '_': encoded},
                headers=self._AJAX_HEADERS
            )
            if not r:
                return sources

            encrypted_result = json.loads(r).get('result', '')
            embed_data = self._decode_kai(encrypted_result)
            if not embed_data:
                control.log(f"AnimeKAI: Embed decryption failed for server '{server_name}'")
                return sources

            embed_url = embed_data.get('url', '')
            skip = {}
            if embed_data.get('skip'):
                skip_data = embed_data['skip']
                if skip_data.get('intro'):
                    intro = skip_data['intro']
                    if isinstance(intro, list) and len(intro) >= 2:
                        skip['intro'] = {'start': intro[0], 'end': intro[1]}
                    elif isinstance(intro, dict):
                        skip['intro'] = intro
                if skip_data.get('outro'):
                    outro = skip_data['outro']
                    if isinstance(outro, list) and len(outro) >= 2:
                        skip['outro'] = {'start': outro[0], 'end': outro[1]}
                    elif isinstance(outro, dict):
                        skip['outro'] = outro

            if not embed_url:
                return sources

            control.log(f"AnimeKAI: Got embed URL for server '{server_name}': {embed_url}")

            # Attempt 1: Use megacloud extractor (same as HiAnime)
            srclink = None
            subs = []
            quality = 0
            try:
                res = extract_megacloud_sources(embed_url, self._BASE_URL)
                if res and res.get('sources'):
                    srclink = res['sources'][0].get('file', '')
                    if srclink:
                        control.log(f"AnimeKAI: Megacloud extraction succeeded for '{server_name}'")
                        tracks = res.get('tracks', [])
                        if tracks:
                            subs = [{'url': x.get('file'), 'lang': x.get('label')} for x in tracks if x.get('kind') == 'captions']
                        if res.get('intro') and not skip.get('intro'):
                            skip['intro'] = res['intro']
                        if res.get('outro') and not skip.get('outro'):
                            skip['outro'] = res['outro']
                    else:
                        control.log(f"AnimeKAI: Megacloud returned empty source for '{server_name}'")
                else:
                    control.log(f"AnimeKAI: Megacloud extraction returned no sources for '{server_name}'")
            except Exception as e:
                control.log(f"AnimeKAI: Megacloud extraction error for '{server_name}': {str(e)}")

            # Attempt 2: Try /media/ endpoint + dec-mega API
            if not srclink:
                try:
                    video_id = embed_url.rstrip('/').split('/')[-1]
                    embed_base = embed_url.rsplit('/e/', 1)[0] if '/e/' in embed_url else embed_url.rsplit('/', 1)[0]
                    media_url = f"{embed_base}/media/{video_id}"
                    control.log(f"AnimeKAI: Trying media endpoint: {media_url}")
                    media_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': embed_url,
                    }
                    media_resp = client.get(media_url, headers=media_headers, timeout=15)
                    if media_resp and media_resp.ok:
                        control.log(f"AnimeKAI: Media endpoint response status: {media_resp.status_code}")
                        control.log(f"AnimeKAI: Media endpoint response (first 200 chars): {media_resp.text[:200] if media_resp.text else 'EMPTY'}")
                        try:
                            media_json = media_resp.json()
                        except Exception:
                            media_json = None
                            control.log(f"AnimeKAI: Media response is not valid JSON for '{server_name}'")
                        if media_json:
                            encrypted_media = media_json.get('result', '')
                            control.log(f"AnimeKAI: Encrypted media (first 100 chars): {str(encrypted_media)[:100] if encrypted_media else 'EMPTY'}")
                            if encrypted_media:
                                final_data = self._decode_mega(encrypted_media)
                                control.log(f"AnimeKAI: dec-mega result: {type(final_data).__name__}, has sources: {bool(final_data and final_data.get('sources') if isinstance(final_data, dict) else False)}")
                                if isinstance(final_data, dict) and final_data.get('sources'):
                                    srclink = final_data['sources'][0].get('file', '')
                                    if srclink:
                                        control.log(f"AnimeKAI: Media/dec-mega succeeded for '{server_name}'")
                                        tracks = final_data.get('tracks', [])
                                        if tracks:
                                            subs = [{'url': x.get('file'), 'lang': x.get('label')} for x in tracks if x.get('kind') == 'captions']
                                else:
                                    control.log(f"AnimeKAI: dec-mega decryption failed for '{server_name}'")
                            else:
                                control.log(f"AnimeKAI: Media endpoint returned empty result for '{server_name}'")
                    else:
                        control.log(f"AnimeKAI: Media endpoint failed - status: {media_resp.status_code if media_resp else 'None'}")
                except Exception as e:
                    control.log(f"AnimeKAI: Media/dec-mega error for '{server_name}': {str(e)}")

            # If we got a direct stream, determine quality and return as direct source
            if srclink:
                netloc = urllib.parse.urljoin(embed_url, '/')
                headers = {'Referer': netloc, 'Origin': netloc[:-1]}
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

                source = {
                    'release_title': '{0} - Ep {1}'.format(title, episode),
                    'hash': srclink + '|User-Agent=iPad&{0}'.format(urllib.parse.urlencode(headers)),
                    'type': 'direct',
                    'quality': quality,
                    'debrid_provider': '',
                    'provider': 'animekai',
                    'size': 'NA',
                    'seeders': 0,
                    'byte_size': 0,
                    'info': [server_name + (' DUB' if lang == 'dub' else ' SUB')],
                    'lang': 3 if lang == 'dub' else 2,
                    'channel': 3,
                    'sub': 1,
                }
                if subs:
                    source['subs'] = subs
                if skip:
                    source['skip'] = skip
                sources.append(source)
                return sources

            # Fallback: return as embed URL (EQ quality)
            control.log(f"AnimeKAI: Returning embed fallback for server '{server_name}'")
            source = {
                'release_title': '{0} - Ep {1}'.format(title, episode),
                'hash': embed_url,
                'type': 'embed',
                'quality': 0,
                'debrid_provider': '',
                'provider': 'animekai',
                'size': 'NA',
                'seeders': 0,
                'byte_size': 0,
                'info': [server_name + (' DUB' if lang == 'dub' else ' SUB')],
                'lang': 3 if lang == 'dub' else 2,
                'channel': 3,
                'sub': 1,
            }
            if skip:
                source['skip'] = skip
            sources.append(source)

        except Exception as e:
            control.log(f"AnimeKAI: Failed to process server '{server_name}': {str(e)}")

        return sources
