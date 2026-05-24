# Easynews episode/movie search — results resolve as hoster + Easynews provider.
import pickle
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from resources.lib.debrid import easynews as easynews_debrid
from resources.lib.ui import database, source_utils, control
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    @staticmethod
    def _extract_titles(query):
        """Parse '(Title1)|(Title2)' from kodi_meta['query']; else single cleaned string."""
        if not query:
            return []
        parts = re.findall(r'\(([^)]+)\)', query)
        if not parts:
            return [Sources._simplify_title(query)]
        seen, result = set(), []
        for p in parts:
            p = p.strip()
            if p and p.lower() not in seen:
                seen.add(p.lower())
                result.append(p)
        return result

    @staticmethod
    def _simplify_title(q):
        if not q:
            return ''
        s = q.split('|')[0].strip()
        if s.startswith('(') and ')' in s:
            s = s[1:s.index(')')]
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _broaden_titles(titles):
        """Extra query variants Usenet uploads often omit (subtitle after ':', trailing season/part)."""
        seen = {t.lower() for t in titles}
        extras = []
        for t in titles:
            if ':' in t:
                prefix = t.split(':', 1)[0].strip()
                if prefix and prefix.lower() not in seen:
                    seen.add(prefix.lower())
                    extras.append(prefix)
            no_qual = re.sub(r'\s+(season|part)\s+\d+\s*$', '', t, flags=re.IGNORECASE).strip()
            if no_qual and no_qual.lower() not in seen:
                seen.add(no_qual.lower())
                extras.append(no_qual)
        return titles + extras

    @staticmethod
    def _title_matches(filename, titles):
        """Reject cross-franchise noise while keeping romanji / abbreviated Usenet filenames."""
        flat_name = re.sub(r'[^a-z0-9]', '', filename.lower())

        def _tokens(s):
            return [tok for tok in re.findall(r'[a-z0-9]+', s.lower()) if len(tok) >= 3]

        def _threshold(n):
            if n <= 2:
                return n
            return min(3, max(2, (n + 1) // 2))

        for title in titles:
            if ':' in title:
                pre, suf = title.split(':', 1)
                pre_toks = _tokens(pre)
                suf_toks = _tokens(suf)
                pre_hits = sum(1 for tok in pre_toks if tok in flat_name)
                suf_hits = sum(1 for tok in suf_toks if tok in flat_name)
                if pre_toks and pre_hits >= _threshold(len(pre_toks)) and suf_hits >= 1:
                    return True
                if suf_toks and suf_hits >= _threshold(len(suf_toks)):
                    return True
            else:
                toks = _tokens(title)
                if not toks:
                    continue
                hits = sum(1 for tok in toks if tok in flat_name)
                if hits >= _threshold(len(toks)):
                    return True
        return False

    @staticmethod
    def _uniq_queries(queries):
        """Preserve order; case-fold dedupe."""
        seen = set()
        out = []
        for q in queries:
            q = (q or '').strip()
            if not q:
                continue
            k = q.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(q)
        return out

    def _movie_queries(self, mal_id, search_titles):
        try:
            row = database.get_show(mal_id)
            meta = pickle.loads(row['kodi_meta']) if row and row.get('kodi_meta') else {}
            year = (meta.get('year') or '') or ''
            if not year and meta.get('start_date'):
                year = str(meta['start_date']).split('-')[0]
        except Exception:
            year = ''
        if year:
            return self._uniq_queries([f'{t} {year}'.strip() for t in search_titles])
        return self._uniq_queries(list(search_titles))

    def get_sources(self, query, mal_id, episode, status, media_type, season=None, part=None):
        if not control.easynews_enabled():
            return {'cached': [], 'uncached': []}

        originals = self._extract_titles(query)
        originals = [self._clean_title(t).strip() for t in originals if t]
        if not originals:
            return {'cached': [], 'uncached': []}

        search_titles = self._broaden_titles(originals)
        primary = originals[0]
        season_int = int(season) if season else 1
        ep_str = str(episode).zfill(2) if episode is not None else '01'
        sz = str(season).zfill(2) if season else '01'

        if media_type == 'movie':
            queries = self._movie_queries(mal_id, search_titles)
        else:
            queries = []
            for t in search_titles:
                queries.append(f'{t} - {ep_str}')
                queries.append(f'{t} S{sz}E{ep_str}')
            queries = self._uniq_queries(queries)

        if not queries:
            return {'cached': [], 'uncached': []}

        workers = max(1, min(len(queries), int(control.max_threads or 4)))
        api = easynews_debrid.Easynews()
        rows = []
        seen_urls = set()

        def fetch_one(q):
            return q, api.search(q)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(fetch_one, q): q for q in queries}
            for fut in as_completed(future_map):
                q = future_map[fut]
                try:
                    batch = fut.result()[1]
                except Exception as e:
                    control.log(f'Easynews: query failed for {q!r}: {e}', 'warning')
                    continue
                if not batch:
                    continue
                gained = 0
                for r in batch:
                    u = r.get('url_dl')
                    if not u or u in seen_urls:
                        continue
                    seen_urls.add(u)
                    rows.append(r)
                    gained += 1
                if gained:
                    control.log(f'Easynews: query {q!r} added {gained} new hits', 'info')

        control.log(f'Easynews: {len(rows)} raw hits before title / episode filter', 'info')
        relevant = [r for r in rows if self._title_matches(r.get('name', ''), originals)]
        control.log(f'Easynews: {len(relevant)} hits after title relevance', 'info')

        if media_type == 'movie':
            filtered_dicts = [{'name': r['name'], 'hash': r['url_dl']} for r in relevant]
        else:
            prepared = [{'name': r['name'], 'hash': r['url_dl']} for r in relevant]
            filtered_dicts = source_utils.filter_sources(
                'easynews', prepared, mal_id, season_int, episode, part)

        control.log(f'Easynews: {len(filtered_dicts)} hits after episode/season filter', 'info')

        by_hash = {r['url_dl']: r for r in relevant}
        cached = []
        for d in filtered_dicts:
            url_dl = d['hash']
            row = by_hash.get(url_dl)
            if not row:
                continue
            name = row['name']
            raw = row.get('rawSize') or 0
            try:
                raw = int(raw)
            except (TypeError, ValueError):
                raw = 0
            cached.append({
                'release_title': name,
                'hash': url_dl,
                'type': 'hoster',
                'quality': source_utils.getQuality(name),
                'debrid_provider': 'Easynews',
                'provider': 'easynews',
                'episode_re': str(episode).zfill(2) if episode is not None else '01',
                'size': source_utils.get_size(raw),
                'byte_size': raw,
                'info': source_utils.getInfo(name),
                'lang': source_utils.getAudio_lang(name),
                'channel': source_utils.getAudio_channel(name),
                'sub': source_utils.getSubtitle_lang(name),
                'cached': True,
                'seeders': 0,
            })

        cached.sort(key=lambda x: x.get('byte_size') or 0, reverse=True)
        control.log(f'Easynews: returning {len(cached)} sources for {primary!r}', 'info')

        return {'cached': cached, 'uncached': []}
