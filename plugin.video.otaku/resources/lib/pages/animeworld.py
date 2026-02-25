import json
import pickle
import re
import urllib.parse

from bs4 import BeautifulSoup
from resources.lib.ui import control, database, source_utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://www.animeworld.ac/'

    def get_sources(self, mal_id, episode):
        show = database.get_show(mal_id)
        if not show:
            control.log(f"AnimeWorld: No show found for MAL ID {mal_id}", level='info')
            return []

        kodi_meta_raw = show.get('kodi_meta')
        if not kodi_meta_raw:
            control.log(f"AnimeWorld: Missing kodi_meta for MAL ID {mal_id}", level='info')
            return []
        kodi_meta = pickle.loads(kodi_meta_raw)
        title = self._clean_title(kodi_meta.get('name') or '')
        if not title:
            control.log(f"AnimeWorld: Missing title for MAL ID {mal_id}", level='info')
            return []

        control.log(f"AnimeWorld: Getting sources for MAL ID {mal_id}, Episode {episode}", level='info')

        start_date = kodi_meta.get('start_date') or ''
        year = start_date.split('-')[0] if start_date else ''

        try:
            anime = self._find_anime(mal_id, title, year=year)
            if not anime:
                control.log(f"AnimeWorld: No matching anime found for '{title}'", level='info')
                return []

            play_url = self._build_play_url(anime)
            if not play_url:
                control.log("AnimeWorld: Failed to build play URL", level='info')
                return []

            html = database.get(self._get_request, 8, play_url, headers={'Referer': self._BASE_URL})
            if not html:
                control.log("AnimeWorld: Empty anime page response", level='info')
                return []

            episode_data = self._collect_episode_data(html, str(episode))
            if not episode_data:
                control.log(f"AnimeWorld: Episode {episode} not found via API layout, trying inline fallback", level='info')
                fallback = self._extract_inline_sources(html, title, str(episode))
                control.log(f"AnimeWorld: Inline fallback returned {len(fallback)} sources", level='info')
                return fallback

            sources = self._build_sources(title, str(episode), episode_data)
            if not sources:
                control.log("AnimeWorld: API extraction returned 0 sources, trying inline fallback", level='info')
                fallback = self._extract_inline_sources(html, title, str(episode))
                control.log(f"AnimeWorld: Inline fallback returned {len(fallback)} sources", level='info')
                return fallback
            return sources
        except Exception as e:
            control.log(f"AnimeWorld: Unhandled error: {str(e)}", level='info')
            return []

    def _find_anime(self, mal_id, title, year=''):
        """Find the best AnimeWorld match using MAL ID first, then title fallback."""
        animes = []
        for keyword in self._build_search_keywords(title):
            params = {'keyword': keyword}
            response = database.get(
                self._get_request,
                8,
                urllib.parse.urljoin(self._BASE_URL, 'api/search/v2'),
                data=params,
                headers={'Referer': self._BASE_URL}
            )
            if not response:
                continue

            try:
                payload = json.loads(response)
            except (json.JSONDecodeError, TypeError):
                continue

            animes = payload.get('animes') or []
            if animes:
                control.log(f"AnimeWorld: Search hit with keyword '{keyword}' ({len(animes)} results)", level='info')
                break

        if not animes:
            html_match = self._find_anime_from_html(title, year=year)
            if html_match:
                return html_match
            return None

        for item in animes:
            if str(item.get('malId') or '') == str(mal_id):
                return item

        clean_title = self._normalize_title(title)
        exact = [x for x in animes if self._normalize_title(x.get('name') or '') == clean_title]
        if exact:
            return exact[0]

        scored = []
        for item in animes:
            candidate = "{0} {1}".format(item.get('name') or '', item.get('link') or '')
            score = self._score_text_match(candidate, title, year=year)
            if score > 0:
                scored.append((score, item))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

        # Avoid returning random unrelated anime when no decent match exists.
        html_match = self._find_anime_from_html(title, year=year)
        return html_match

    def _normalize_title(self, text):
        text = (text or '').lower()
        text = text.replace('&', ' and ')
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _build_search_keywords(self, title):
        base = (title or '').strip()
        variants = []

        def add(v):
            v = (v or '').strip()
            if v and v not in variants:
                variants.append(v)

        add(base)
        add(base.replace(':', ' '))
        add(base.split(':')[0].strip())

        normalized = self._normalize_title(base)
        add(normalized)
        add(normalized.replace('shippuuden', 'shippuden'))
        add(normalized.replace('ou', 'o'))
        add(normalized.replace('uu', 'u'))

        # token-based fallback (drop punctuation artifacts, keep core words)
        tokens = [t for t in normalized.split(' ') if t not in ('season', 'part')]
        if len(tokens) > 1:
            add(' '.join(tokens))
            add(' '.join(tokens[:2]))

        return variants

    def _find_anime_from_html(self, title, year=''):
        """HTML search fallback when /api/search/v2 returns empty or blocked."""
        for keyword in self._build_search_keywords(title):
            params = {'keyword': keyword}
            html = database.get(
                self._get_request,
                8,
                urllib.parse.urljoin(self._BASE_URL, 'filter'),
                data=params,
                headers={'Referer': self._BASE_URL}
            )
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href') or ''
                if '/play/' not in href:
                    continue
                full = urllib.parse.urljoin(self._BASE_URL, href)
                text_blob = " ".join(filter(None, [
                    a.get_text(" ", strip=True),
                    a.get('title') or '',
                    a.get('data-jname') or '',
                    a.get('data-name') or ''
                ]))
                links.append((a, full, text_blob))

            if not links:
                continue

            best = None
            best_score = -1
            for _, full, text_blob in links:
                parsed = urllib.parse.urlparse(full)
                path = parsed.path.strip('/').split('/')
                token = path[1] if len(path) > 1 else (path[0] if path else '')
                slug = token.partition('.')[0]
                candidate_text = "{0} {1}".format(text_blob, slug.replace('-', ' '))
                score = self._score_text_match(candidate_text, title, year=year)
                if score > best_score:
                    best_score = score
                    best = full

            # Require at least a minimal overlap; otherwise ignore this page.
            if not best or best_score < 2:
                continue

            parsed = urllib.parse.urlparse(best)
            path = parsed.path.strip('/').split('/')
            if not path:
                continue
            token = path[1] if len(path) > 1 else path[0]
            slug, sep, identifier = token.partition('.')
            if slug and sep and identifier:
                control.log(
                    f"AnimeWorld: HTML search hit with keyword '{keyword}' (score={best_score}, slug={slug})",
                    level='info'
                )
                return {'link': slug, 'identifier': identifier}
            # fallback direct url
            return {'link': best}
        return None

    def _score_text_match(self, candidate, title, year=''):
        cand = self._normalize_title(candidate)
        tgt = self._normalize_title(title)
        if not cand or not tgt:
            return 0

        stop = {'season', 'part', 'series', 'tv', 'the', 'nd', 'st', 'rd', 'th'}
        cand_tokens = {t for t in cand.split(' ') if t and t not in stop}
        tgt_tokens = {t for t in tgt.split(' ') if t and t not in stop}
        common = cand_tokens.intersection(tgt_tokens)

        score = len(common) * 3
        if tgt in cand:
            score += 3
        if year and year in cand:
            score += 1

        target_season = self._extract_season_number(title)
        candidate_season = self._extract_season_number(candidate)
        if target_season:
            if candidate_season:
                if target_season == candidate_season:
                    score += 8
                else:
                    score -= 12
            else:
                score -= 2

        if not common:
            score = 0
        return score

    def _extract_season_number(self, text):
        t = (text or '').lower()
        # Examples: "2nd season", "season 2", "third season" (limited words).
        m = re.search(r'(\d+)\s*(?:st|nd|rd|th)?\s*season', t)
        if m:
            return int(m.group(1))
        m = re.search(r'season\s*(\d+)', t)
        if m:
            return int(m.group(1))
        # Sometimes only trailing number is used in slugs/titles (e.g. jujutsu-kaisen-3).
        m = re.search(r'(?:^|[\s\-_])(\d+)(?:$|[\s\-_])', t)
        if m:
            return int(m.group(1))
        return None

    def _build_play_url(self, anime):
        slug = anime.get('link')
        identifier = anime.get('identifier')
        if slug and identifier:
            return urllib.parse.urljoin(self._BASE_URL, f"play/{slug}.{identifier}")

        direct = anime.get('link')
        if isinstance(direct, str) and direct.startswith('http'):
            return direct
        if isinstance(direct, str):
            return urllib.parse.urljoin(self._BASE_URL, direct.lstrip('/'))
        return None

    def _collect_episode_data(self, html, episode):
        soup = BeautifulSoup(html, "html.parser")

        legacy_providers = {}
        for prov in soup.select("div[class*='server'][data-name]"):
            prov_id = (prov.get('data-name') or '').strip()
            if not prov_id:
                continue
            title = (prov.get('data-title') or prov.get('data-tab') or prov.get('data-name') or '').strip()
            legacy_providers[prov_id] = {'name': title or f"server-{prov_id}"}

        all_episodes = {}
        for prov_id, prov_data in legacy_providers.items():
            prov_div = soup.select_one(f"div[class*='server'][data-name='{prov_id}']")
            if not prov_div:
                continue

            for anchor in prov_div.select('li.episode > a'):
                ep_num = (anchor.get('data-episode-num') or '').strip()
                ep_id = (anchor.get('data-episode-id') or '').strip()
                href = anchor.get('href')
                if not ep_num or not ep_id:
                    continue

                if ep_num not in all_episodes:
                    all_episodes[ep_num] = {}
                if ep_id not in all_episodes[ep_num]:
                    all_episodes[ep_num][ep_id] = {'legacy': []}

                if href:
                    all_episodes[ep_num][ep_id]['legacy'].append({
                        'id': int(prov_id) if prov_id.isdigit() else -1,
                        'name': prov_data['name'],
                        'link': urllib.parse.urljoin(self._BASE_URL, href)
                    })

        candidates = [episode]
        if episode.isdigit():
            candidates.extend([str(int(episode)), f"{int(episode)}.0"])

        selected = None
        for candidate in candidates:
            if candidate in all_episodes:
                selected = all_episodes[candidate]
                break
        if selected is None:
            return []

        episode_data = []
        for ep_id, meta in selected.items():
            episode_data.append({
                'id': ep_id,
                'download_api': urllib.parse.urljoin(self._BASE_URL, f"api/download/{ep_id}"),
                'legacy': meta.get('legacy') or []
            })

        # Fallback: extract explicit episode URLs like
        # /play/<anime-slug>.<identifier>/<episode-token>
        episode_urls = self._extract_episode_urls(soup, episode)
        for episode_url in episode_urls:
            episode_data.append({
                'id': '',
                'download_api': '',
                'legacy': [],
                'episode_url': episode_url
            })

        return episode_data

    def _build_sources(self, title, episode, episode_data):
        sources = []
        seen = set()

        for ep in episode_data:
            extracted = []

            response = None
            if ep.get('download_api'):
                response = database.get(
                    self._get_request,
                    8,
                    ep['download_api'],
                    headers={'Referer': self._BASE_URL}
                )
            if response:
                try:
                    payload = json.loads(response)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
                links = payload.get('links') or {}
                for prov_id, prov_data in links.items():
                    key = next((k for k in prov_data.keys() if k != 'server'), None)
                    if not key:
                        continue
                    link = ((prov_data.get(key) or {}).get('link') or '').strip()
                    name = ((prov_data.get('server') or {}).get('name') or '').strip()
                    if not link:
                        continue
                    extracted.append({
                        'id': int(prov_id) if str(prov_id).isdigit() else -1,
                        'name': name or source_utils.get_embedhost(link),
                        'link': link
                    })

            # If we have a direct episode page URL, extract embeds from that page too.
            episode_url = ep.get('episode_url')
            if episode_url:
                episode_html = database.get(
                    self._get_request,
                    8,
                    episode_url,
                    headers={'Referer': self._BASE_URL}
                )
                if episode_html:
                    inline_sources = self._extract_inline_sources(episode_html, title, episode)
                    for src in inline_sources:
                        extracted.append({
                            'id': -1,
                            'name': source_utils.get_embedhost(src.get('hash') or ''),
                            'link': src.get('hash') or ''
                        })

            known_ids = {str(x.get('id')) for x in extracted if x.get('id') is not None}
            for legacy in ep.get('legacy') or []:
                if str(legacy.get('id')) in known_ids:
                    continue
                extracted.append(legacy)

            for item in extracted:
                link = (item.get('link') or '').strip()
                if not link:
                    continue
                if link in seen:
                    continue
                source = self._build_source_item(title, episode, link, item.get('name') or '')
                if not source:
                    continue
                seen.add(link)
                sources.append(source)

        control.log(f"AnimeWorld: Returning {len(sources)} sources", level='info')
        return sources

    def _build_source_item(self, title, episode, link, name_hint=''):
        host = source_utils.get_embedhost(link)
        if self._is_direct_link(link):
            return {
                'release_title': '{0} - Ep {1}'.format(title, episode),
                'hash': link,
                'type': 'direct',
                'quality': 0,
                'debrid_provider': '',
                'provider': 'animeworld',
                'size': 'NA',
                'seeders': 0,
                'byte_size': 0,
                'info': [name_hint or host or 'direct', 'SUB'],
                'lang': 2,
                'channel': 3,
                'sub': 1
            }
        if self._is_supported_embed(link):
            return {
                'release_title': '{0} - Ep {1}'.format(title, episode),
                'hash': link,
                'type': 'embed',
                'quality': 0,
                'debrid_provider': '',
                'provider': 'animeworld',
                'size': 'NA',
                'seeders': 0,
                'byte_size': 0,
                'info': [name_hint or host or 'embed', 'SUB'],
                'lang': 2,
                'channel': 3,
                'sub': 1
            }
        return None

    @staticmethod
    def _is_direct_link(link):
        low = link.lower().split('?', 1)[0]
        return any(low.endswith(ext) for ext in ('.m3u8', '.mp4', '.mkv', '.webm'))

    def _is_supported_embed(self, link):
        low = link.lower()
        parsed = urllib.parse.urlparse(link)
        domain = (parsed.netloc or '').lower()
        path = (parsed.path or '').lower()

        if any(domain.endswith(x) for x in ('animeworld.ac', 'static.animeworld.ac', 'ad.a-ads.com')):
            return False
        if any(path.endswith(x) for x in ('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2')):
            return False

        from resources.lib.ui import embed_extractor
        return any(low.startswith(prefix.lower()) for prefix in embed_extractor._EMBED_EXTRACTORS.keys())

    def _extract_episode_urls(self, soup, episode):
        episode_urls = []
        seen = set()

        candidates = [episode]
        if episode.isdigit():
            candidates.extend([str(int(episode)), f"{int(episode)}.0"])

        for anchor in soup.find_all('a', href=True):
            href = anchor.get('href') or ''
            if '/play/' not in href:
                continue
            # episode number can be in attributes or visible text
            ep_num = (
                (anchor.get('data-episode-num') or '').strip()
                or (anchor.get('data-num') or '').strip()
                or anchor.get_text(strip=True)
            )
            if ep_num not in candidates:
                continue

            full = urllib.parse.urljoin(self._BASE_URL, href)
            if full in seen:
                continue
            seen.add(full)
            episode_urls.append(full)

        return episode_urls

    def _extract_inline_sources(self, html, title, episode):
        """Fallback extractor when API/server blocks are unavailable."""
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        seen = set()

        def push_link(url):
            if not url:
                return
            url = url.strip()
            if not url or url.startswith('javascript:'):
                return
            full = urllib.parse.urljoin(self._BASE_URL, url)
            if full in seen:
                return
            seen.add(full)
            candidates.append(full)

        for iframe in soup.find_all('iframe'):
            push_link(iframe.get('src'))

        for tag in soup.find_all(True):
            push_link(tag.get('data-link'))
            push_link(tag.get('data-href'))
            href = tag.get('href')
            if href:
                href_low = href.lower()
                if any(href_low.endswith(x) for x in ('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2')):
                    continue
                if any(x in href_low for x in ('/embed', '/player', '/stream', '.m3u8', '.mp4')):
                    push_link(href)

        sources = []
        for link in candidates:
            source = self._build_source_item(title, episode, link, '')
            if source:
                sources.append(source)
        return sources
