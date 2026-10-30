# Keep only the releases of the part being played, for every provider.
#
# Later parts of a show (Bleach: Thousand-Year Blood War - The Calamity) are often released
# with the same "S01E06" / "- 06" numbering as the earlier parts, so the episode filter alone
# lets episode 6 of every part through.
import pickle
import re

from resources.lib.ui import control, database

EP_TITLE = re.compile(r'(?i)s\d{1,2}[ ._-]?e\d{1,4}[ ._-]+(.+)')
TITLE_END = re.compile(r'(?i)[\[(]|\b(?:\d{3,4}p|4k|uhd|web|webrip|web-dl|bluray|bdrip|bd|hdtv|x26[45]|h\.?26[45]|hevc|avc|av1|aac|ddp?|flac|multi|dual|repack|proper|amzn|cr|dsnp|nf|jc|10bit|subbed|dubbed)\b')
SMALL_WORDS = {'the', 'and', 'for', 'part', 'episode', 'final'}
# entries that are parts of the series itself; movies, specials, recaps and OVAs are not
SERIES_TYPES = ('TV', 'ONA', 'UNKNOWN', None)


def _is_part(row):
    return str(row.get('thetvdb_season')) != '0' and row.get('anime_media_type') in SERIES_TYPES
# Chinese subtitles burned into the picture ([CHS] / [CHT] / [GB] / [BIG5] / 简繁)
CHINESE_HARDSUB = re.compile(r'(?i)\[(?:chs|cht|gb|big5|chs_jp|cht_jp|chs&cht)\]|[简繁]')
# "[07]" / "[05v2]": the episode number Chinese and some Japanese groups put in brackets
BRACKET_EP = re.compile(r'\[(\d{1,3})(?:v\d)?\]')
PART_NO = re.compile(r'(?i)(?:^|[^a-z])(?:part|cour)[ ._-]?(\d{1,2})(?!\d)')


def _flat(text):
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def titles_from_query(query):
    """'(Title one)|(Title two)' -> ['Title one', 'Title two']"""
    parts = re.findall(r'\(([^)]+)\)', query or '')
    return [p.strip() for p in parts if p.strip()] or ([query.split('|')[0].strip()] if query else [])


def part_info(mal_id):
    """(this part's number, its name, names of the other parts) from Otaku's mappings, e.g.
    (4, 'kashintan', ['ketsubetsutan', 'soukokutan']) for Bleach TYBW - Kashin-tan."""
    try:
        with database.SQL(control.mappingDB) as cur:
            cur.execute('SELECT mal_title FROM anime WHERE mal_id=?', (mal_id,))
            row = cur.fetchone()
            title = (row or {}).get('mal_title') or ''
            base = title.split(' - ')[0]
            if not base:
                return None, '', []
            cur.execute("SELECT mal_id, mal_title, thetvdb_season, anime_media_type FROM anime "
                        "WHERE mal_title=? OR mal_title LIKE ?", (base, base + ' - %'))
            siblings = [r for r in cur.fetchall() if _is_part(r)]
    except Exception as e:
        control.log(f'Part filter: mappings failed: {e}', 'warning')
        return None, '', []
    siblings.sort(key=lambda r: r['mal_id'])
    ids = [r['mal_id'] for r in siblings]
    number = ids.index(mal_id) + 1 if mal_id in ids and len(ids) > 1 else None

    def name(t):
        return _flat(t.split(' - ', 1)[1]) if ' - ' in (t or '') else ''
    own = name(title)
    others = [n for n in (name(r['mal_title']) for r in siblings if r['mal_id'] != mal_id)
              if len(n) >= 5 and n != own]
    return number, own, others


def continuous_offset(mal_id):
    """Episodes of the earlier parts, from their global_media_episodes ('27-40' -> 40), so
    part 4 episode 6 is episode 46 for groups that keep counting. 0 when unknown."""
    try:
        with database.SQL(control.mappingDB) as cur:
            cur.execute('SELECT mal_title FROM anime WHERE mal_id=?', (mal_id,))
            title = ((cur.fetchone() or {}).get('mal_title') or '')
            base = title.split(' - ')[0]
            if not base:
                return 0
            cur.execute("SELECT mal_id, global_media_episodes, thetvdb_season, anime_media_type "
                        "FROM anime WHERE (mal_title=? OR mal_title LIKE ?) AND mal_id < ?",
                        (base, base + ' - %', mal_id))
            ends = [int(n[-1]) for r in cur.fetchall() if _is_part(r)
                    for n in [re.findall(r'\d+', str(r.get('global_media_episodes') or ''))] if n]
    except Exception:
        return 0
    return max(ends) if ends else 0


def franchise_offset(mal_id):
    """Episodes of the entries that come before this one in the same TVDB show, whatever
    their names (Gintama, Gintama', Gintama': Enchousen before Gintama°: 201 + 51 + 13).
    Groups that number the whole franchise ("Gintama - 001") use this count. 0 when unknown."""
    try:
        with database.SQL(control.mappingDB) as cur:
            cur.execute('SELECT thetvdb_id FROM anime WHERE mal_id=?', (mal_id,))
            tvdb = (cur.fetchone() or {}).get('thetvdb_id')
            if not str(tvdb or '').isdigit():
                return 0
            cur.execute('SELECT anime_media_episodes, thetvdb_season, anime_media_type FROM anime '
                        'WHERE thetvdb_id=? AND mal_id < ?', (tvdb, mal_id))
            total = 0
            for r in cur.fetchall():
                if str(r.get('thetvdb_season')) in ('None', '') or not _is_part(r):
                    continue  # movies, specials, recaps
                n = [int(x) for x in re.findall(r'\d+', str(r.get('anime_media_episodes') or ''))]
                if len(n) >= 2 and n[1] >= n[0]:
                    total += n[1] - n[0] + 1
                elif n:
                    total += n[-1]
    except Exception:
        return 0
    return total


# "- 001", "E001", " 001 [": a zero-padded three-digit episode number
PADDED_NUMBER = re.compile(r'(?i)(?:\s-\s?|\be|\bep\.?\s?|\s)(0\d{2})(?:v\d)?(?=[\s\[(._]|$)')
# words of a title that say nothing about which show it is
NOT_SHOW_WORDS = SMALL_WORDS | {'season', 'movie', 'series', 'anime', 'with', 'from', 'that', 'this'}


# "(01-367)", "001-367", "266~316": the episodes a batch holds (not "1920x1080" or "x264-10")
BATCH_RANGE = re.compile(r'(?<![\dxX.])(\d{1,4})\s*[-~]\s*(\d{1,4})(?![\dpP])')


def episode_count(mal_id):
    """Episodes of this entry ('1 - 51' -> 51), or 0 when unknown."""
    try:
        with database.SQL(control.mappingDB) as cur:
            cur.execute('SELECT anime_media_episodes FROM anime WHERE mal_id=?', (mal_id,))
            n = [int(x) for x in re.findall(r'\d+', str((cur.fetchone() or {}).get('anime_media_episodes') or ''))]
    except Exception:
        return 0
    return n[-1] if n else 0


def file_names(source):
    """Names of the files inside a debrid cloud item (Real-Debrid, TorBox), if it has any."""
    files = source.get('torrent_files') or (source.get('torrent') or {}).get('files') or []
    if not isinstance(files, list):
        return []
    return [str(f.get('path') or f.get('short_name') or f.get('name') or '')
            for f in files if isinstance(f, dict)]


def side_names(mal_id, titles):
    """Movies, specials and OVAs of the same show, as flat names that a release of them
    carries in full ('Gintama: The Final' -> 'gintamathefinal'), for skipping them while
    a TV episode plays. Names that this entry's own titles contain are left out."""
    own = [_flat(t) for t in titles]
    try:
        with database.SQL(control.mappingDB) as cur:
            cur.execute('SELECT mal_title FROM anime WHERE mal_id=?', (mal_id,))
            title = (cur.fetchone() or {}).get('mal_title') or ''
            first = re.findall(r'[A-Za-z0-9]+', title)
            if not first or len(first[0]) < 4:
                return []
            own.append(_flat(title))
            cur.execute('SELECT mal_title, anime_media_type FROM anime WHERE mal_title LIKE ? '
                        'AND mal_id != ?', (first[0] + '%', mal_id))
            rows = cur.fetchall()
    except Exception:
        return []
    names = []
    for r in rows:
        if r.get('anime_media_type') in SERIES_TYPES:
            continue
        n = _flat(r.get('mal_title'))
        if len(n) >= 12 and not any(n in o for o in own):
            names.append(n)
    return names


def show_words(titles):
    """Words that name the show, from all its titles: 'Gintama°', 'Gintama Season 4' ->
    {'gintama'}."""
    words = set()
    for t in titles:
        words.update(w for w in re.findall(r'[a-z0-9]{4,}', (t or '').lower())
                     if w not in NOT_SHOW_WORDS and not w.isdigit())
    return words


# "- 45", "- 45v2", "E45", " 45 [": an episode number in a release name
NAMED_NUMBER = re.compile(r'(?i)(?:\s-\s?|\be|\bep\.?\s?|\s)(\d{2,3})(?:v\d)?(?=[\s\[(._]|$)')


def wants_chinese():
    """True when Chinese is one of the viewer's subtitle languages in Kodi (Settings ->
    Player -> Language), so Chinese burned-in subtitles are welcome rather than in the way."""
    try:
        import json
        import xbmc
        q = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue',
             'params': {'setting': 'subtitles.languages'}}
        langs = json.loads(xbmc.executeJSONRPC(json.dumps(q))).get('result', {}).get('value') or []
        q['params']['setting'] = 'locale.subtitlelanguage'
        langs.append(json.loads(xbmc.executeJSONRPC(json.dumps(q))).get('result', {}).get('value') or '')
    except Exception:
        return False
    return any('chinese' in str(l).lower() or str(l).lower().startswith(('zh', 'chi', 'zho'))
               for l in langs)


def _words(text):
    return {w for w in re.findall(r'[a-z]{3,}', (text or '').lower()) if w not in SMALL_WORDS}


def episode_title_words(mal_id, episode):
    """Words of the episode's own title from Otaku's episode list ('The End' -> {'end'})."""
    try:
        row = database.get_episode(mal_id, episode)
        meta = pickle.loads(row['kodi_meta']) if row and row.get('kodi_meta') else {}
        # Otaku keeps it under 'info' ({'info': {'title': 'The End', ...}, 'image': ...})
        title = (meta.get('info') or {}).get('title') or meta.get('title') or ''
    except Exception as e:
        control.log(f'Part filter: episode title not found: {e}', 'warning')
        return set()
    if re.search(r'(?i)(?:^|\s)(?:episode|ep)\s*\d+\s*$', title):
        return set()  # a placeholder ("Episode 6"), not a title
    words = _words(title)
    control.log(f'Part filter: episode {episode} is "{title}"', 'info')
    return words


def release_episode_words(name):
    """Words of the episode title a release names after S01E06 ('S01E06.The.Fire.1080p' ->
    {'fire'}), or an empty set when it names none."""
    m = EP_TITLE.search(name or '')
    if not m:
        return set()
    rest = re.sub(r'[._]', ' ', m.group(1))
    cut = TITLE_END.search(rest)
    return _words(rest[:cut.start()] if cut else rest)


def apply(sources, mal_id, query, label='', episode=None):
    """Filter a list of source dicts (with 'release_title') down to this part's releases."""
    if not sources:
        return sources
    number, own, others = part_info(mal_id)
    titles = titles_from_query(query)

    def name_of(s):
        return s.get('release_title') or s.get('name') or ''

    own_words = episode_title_words(mal_id, episode) if episode else set()
    drop_chinese = not wants_chinese()
    offset = continuous_offset(mal_id) if episode else 0
    earlier = franchise_offset(mal_id) if episode else 0
    side = side_names(mal_id, titles) if episode else []

    # 0. names another show altogether ("Jack-of-All-Trades, Party of None 01" while playing
    #    Gintama°): a provider's ID mix-up or a loose match. Only when some releases do name
    #    the show, and never for names in other scripts (銀魂), which these words cannot check.
    words = show_words(titles)
    if words:
        def names_show(s):
            n = name_of(s)
            return not _flat(n) or not n.isascii() or any(w in _flat(n) for w in words)
        named = [s for s in sources if names_show(s)]
        if named and len(named) != len(sources):
            control.log(f'Part filter{label}: {len(sources) - len(named)} releases of other '
                        f'shows dropped', 'info')
            sources = named

    own_count = episode_count(mal_id) if episode else 0
    kept = []
    dropped = 0
    hardsub = 0
    renumbered = 0
    for s in sources:
        flat = _flat(name_of(s))
        if not flat:
            kept.append(s)
            continue
        # 0a. a batch numbered past this entry ("Gintama (01-367)", "Gintama (266-316)" while
        #     playing Gintama° episode 1 of 51): its files count over the whole show, so
        #     episode 1 is file 266 in it. Point the file choice there, or drop the batch
        #     when that number is not in its range ("Gintama (001-201)").
        if episode is not None and own_count and (earlier or offset):
            ranges = [(int(a), int(b)) for a, b in BATCH_RANGE.findall(name_of(s))
                      if int(a) < int(b) and not (1900 <= int(a) <= 2099)]  # not years (2015-2016)
            if ranges:
                a, b = max(ranges, key=lambda r: r[1])
                if b > own_count:
                    ep = int(episode)
                    target = next((n for n in (ep + offset, ep + earlier)
                                   if n != ep and a <= n <= b), None)
                    if target:
                        for key in ('episode', 'episode_re'):
                            if key in s:
                                s[key] = str(target).zfill(2) if isinstance(s[key], str) else target
                        renumbered += 1
                    elif earlier:
                        dropped += 1
                        continue
        # 0b. "Gintama - 001" while playing Gintama° episode 1: a zero-padded number counts
        #     the whole franchise, and franchise episode 1 belongs to an earlier entry
        #     (Gintama° episode 1 is franchise episode 266)
        if earlier and episode is not None and not (own and own in flat):
            padded = {int(n) for n in PADDED_NUMBER.findall(name_of(s))}
            if padded and all(n <= earlier for n in padded):
                dropped += 1
                continue
            # the same for a batch in the debrid cloud: its files are numbered 001-201 over
            # the whole franchise, so this entry's episode 1 would play franchise episode 1
            files = file_names(s)
            if files:
                padded = {int(n) for f in files for n in PADDED_NUMBER.findall(f)}
                if padded and all(n <= earlier for n in padded):
                    dropped += 1
                    continue
        # 0c. a movie or special of the same show ("Gintama - The Final (2021)" while
        #     playing a TV episode)
        if any(k in flat for k in side):
            dropped += 1
            continue
        # 1. names another part of the same show ("Soukoku-tan" while playing Kashin-tan)
        if any(o in flat for o in others) and not (own and own in flat):
            dropped += 1
            continue
        # 1b. Chinese subtitles burned into the picture: they cannot be turned off, so drop
        #     them unless Chinese is one of the viewer's subtitle languages
        if drop_chinese and CHINESE_HARDSUB.search(name_of(s)):
            hardsub += 1
            continue
        # 1c. "[07]" while playing episode 6 (the episode filter misses this numbering).
        #     Accepted: the episode, its number counted on from the earlier parts ("[46]"),
        #     and any number of 100 or more for a short show: that is a count over the whole
        #     franchise ("[372]") we cannot check, so the release is kept.
        if episode is not None:
            ep = int(episode)
            ok = {ep, ep + offset}
            brackets = {int(n) for n in BRACKET_EP.findall(name_of(s))}
            wrong = {n for n in brackets if n not in ok and (n < 100 or ep >= 100)}
            if brackets and not (brackets & ok) and wrong:
                dropped += 1
                continue
        # 1d. counts on from the earlier parts ("- 45v2") and lands on another episode:
        #     part 4 episode 6 is 46 when parts 1-3 had 40 episodes
        if offset:
            nums = {int(n) for n in NAMED_NUMBER.findall(re.sub(r'(?i)\b\d{3,4}p\b|\b(?:x|h)\.?26[45]\b', ' ', name_of(s)))}
            later = {n for n in nums if offset < n <= offset + 200}
            if later and int(episode) + offset not in later:
                dropped += 1
                continue
        # 2. says "Part 2" / "Cour 2" while this is part 4
        nums = {int(n) for n in PART_NO.findall(name_of(s))}
        if number and nums and number not in nums:
            dropped += 1
            continue
        # 3. names an episode title, and it is another episode's ("S01E06.The.Fire" is part 1's
        #    episode 6; part 4's episode 6 is "The End")
        if own_words:
            named = release_episode_words(name_of(s))
            if named and not (named & own_words):
                dropped += 1
                continue
        kept.append(s)
    if dropped:
        control.log(f'Part filter{label}: {dropped} releases of other parts or episodes dropped', 'info')
    if renumbered:
        control.log(f'Part filter{label}: {renumbered} batches numbered over the whole show, '
                    f'file choice moved to that numbering', 'info')
    if hardsub:
        control.log(f'Part filter{label}: {hardsub} releases with burned-in Chinese subtitles dropped', 'info')

    # 4. when some releases carry the series subtitle ("Thousand-Year Blood War"), drop the
    #    ones that only say "Bleach" (the original show). Never removes everything.
    toks = set()
    for t in titles:
        if ':' in t:
            sub = t.split(':', 1)[1].split(' - ')[0]
            toks.update(tok for tok in re.findall(r'[a-z0-9]+', sub.lower()) if len(tok) >= 4)
    if toks:
        need = min(2, len(toks))
        # this part's own name ("Kashin Tan") counts as well as the series subtitle
        named = [s for s in kept if not _flat(name_of(s))
                 or (own and own in _flat(name_of(s)))
                 or sum(1 for tok in toks if tok in _flat(name_of(s))) >= need]
        if named and len(named) != len(kept):
            control.log(f'Part filter{label}: {len(kept) - len(named)} releases without the series '
                        f'subtitle dropped', 'info')
            kept = named
    return kept


def part_queries(titles, episode, number):
    """Search words for this part itself, for providers that search by text:
    'BLEACH Kashin-tan 06', 'BLEACH The Calamity 06', 'BLEACH Thousand-Year Blood War Part 4 06'."""
    ep = str(episode).zfill(2) if episode is not None else '01'
    out = []
    for t in titles:
        clean = re.sub(r'\s+', ' ', t.replace(':', ' ')).strip()
        if ' - ' in clean:
            series, part_name = clean.split(' - ', 1)
            show = t.split(':', 1)[0].strip() if ':' in t else series
            out.append(f'{show} {part_name} {ep}')
            if number:
                out.append(f'{series} Part {number} {ep}')
    return out
