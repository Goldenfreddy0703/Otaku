"""source_utils.py - Source Quality & Filtering Engine
=====================================================
Detects video quality, codec, audio format, and subtitle info from
release titles.  Provides regex-based torrent filtering, fuzzy matching,
and file-selection helpers used by the resolver pipeline.

Sections
--------
Quality & Info Detection   - getQuality, getAudio_lang, getInfo, etc.
Episode Regex              - get_cache_check_reg, convert_to_bytes, get_size
Fuzzy Matching             - get_fuzzy_match, get_best_match
Torrent Filtering          - filter_sources (season / episode / part regex)
Text Cleaning              - remove_patterns, cleanup_text, clean_text, cleanTitle
File Utilities             - is_file_ext_valid, video_ext, user_select, get_embedhost
"""

import re
import string
import xbmc


from resources.lib.ui import control

res = ['EQ', '480p', '720p', '1080p', '4k']


# ═══════════════════════════════════════════════════════════════════════════
#  Quality & Info Detection
# ═══════════════════════════════════════════════════════════════════════════

def getAudio_lang(release_title):
    release_title = cleanTitle(release_title)
    if any(i in release_title for i in ['multi audio', 'multi lang', 'multiple audio', 'multiple lang']):
        lang = 0
    elif any(i in release_title for i in ['dual audio']):
        lang = 1
    elif any(i in release_title for i in ['dub', 'dubbed']):
        lang = 3
    else:
        lang = 2
    return lang


def getAudio_channel(release_title):
    release_title = cleanTitle(release_title)
    if any(i in release_title for i in ['2 0 ', '2 0ch', '2ch']):
        channel = 0
    elif any(i in release_title for i in ['5 1 ', '5 1ch', '6ch']):
        channel = 1
    elif any(i in release_title for i in ['7 1 ', '7 1ch', '8ch']):
        channel = 2
    else:
        channel = 3
    return channel


def getSubtitle_lang(release_title):
    release_title = cleanTitle(release_title)
    if any(i in release_title for i in ['multi sub', 'multiple sub']):
        sub = 0
    else:
        sub = 1
    return sub


def getQuality(release_title):
    release_title = release_title.lower()
    if any(i in release_title for i in ['4k', '2160', "216o"]):
        quality = 4
    elif any(i in release_title for i in ["1080", "1o80", "108o", "1o8o"]):
        quality = 3
    elif any(i in release_title for i in ["720", "72o"]):
        quality = 2
    else:
        quality = 1
    return quality


# Tag-detection table: (label, [keywords...])
# Checked in order — first match per label wins.
_INFO_TAGS = (
    # ── Video Codec ──
    ('AVC',         ['x264', 'x 264', 'h264', 'h 264', 'avc']),
    ('HEVC',        ['x265', 'x 265', 'h265', 'h 265', 'hevc']),
    ('XVID',        ['xvid']),
    ('DIVX',        ['divx']),
    ('MP4',         ['mp4']),
    ('WMV',         ['wmv']),
    ('MPEG',        ['mpeg']),
    ('VP9',         ['vp9']),
    ('AV1',         ['av1']),
    ('REMUX',       ['remux', 'bdremux']),
    ('HDR',         [' hdr ', 'hdr10', 'hdr 10', 'uhd bluray 2160p', 'uhd blu ray 2160p',
                     '2160p uhd bluray', '2160p uhd blu ray', '2160p bluray hevc truehd',
                     '2160p bluray hevc dts', '2160p bluray hevc lpcm',
                     '2160p us bluray hevc truehd', '2160p us bluray hevc dts']),
    ('SDR',         [' sdr ']),
    ('DV',          [' dv ', 'dovi', 'dolby vision', 'dolbyvision']),
    # ── Audio Codec ──
    ('AAC',         ['aac']),
    ('DTS',         ['dts']),
    ('DTS-HDMA',    ['hd ma', 'hdma']),
    ('DTS-HDHR',    ['hd hr', 'hdhr', 'dts hr', 'dtshr']),
    ('DTS-X',       ['dtsx', ' dts x']),
    ('ATMOS',       ['atmos']),
    ('TRUEHD',      ['truehd', 'true hd']),
    ('DD+',         ['ddp', 'dd+', 'eac3', ' e ac3', ' e ac 3']),
    ('DD',          [' dd ', 'dd2', 'dd5', 'dd7', ' ac3', ' ac 3']),
    ('MP3',         ['mp3']),
    ('WMA',         [' wma']),
    ('OPUS',        ['opus']),
    ('DUB',         ['dub', 'dubbed']),
    ('DUAL-AUDIO',  ['dual audio']),
    ('MULTI-AUDIO', ['multi audio', 'multi lang', 'multiple audio', 'multiple lang']),
    # ── Channels ──
    ('2.0',         ['2 0 ', '2 0ch', '2ch']),
    ('5.1',         ['5 1 ', '5 1ch', '6ch']),
    ('7.1',         ['7 1 ', '7 1ch', '8ch']),
    # ── Subtitles ──
    ('MULTI-SUB',   ['multi sub', 'multiple sub']),
    # ── Source ──
    ('BLURAY',      ['bluray', 'blu ray', 'bdrip', 'bd rip', 'brrip', 'br rip']),
    ('WEB',         [' web ', 'webrip', 'webdl', 'web rip', 'web dl']),
    ('HDRIP',       [' hdrip', ' hd rip']),
    ('DVDRIP',      ['dvdrip', 'dvd rip']),
    ('HDTV',        ['hdtv']),
    ('PDTV',        ['pdtv']),
    ('CAM',         [' cam ', 'camrip', 'hdcam', 'hd cam', ' ts ', 'hd ts', 'hdts',
                     'telesync', ' tc ', 'hd tc', 'hdtc', 'telecine', 'xbet']),
    ('SCR',         ['dvdscr', ' scr ', 'screener']),
    ('HC',          ['korsub', ' kor ', ' hc']),
    ('BLUR',        ['blurred']),
    ('3D',          [' 3d', ' half ou', ' half sbs']),
    ('60-FPS',      [' 60 fps', ' 60fps']),
    # ── Batch ──
    ('BATCH',       ['batch', 'complete series']),
)


def getInfo(release_title):
    release_title = cleanTitle(release_title)
    return [label for label, keywords in _INFO_TAGS
            if any(kw in release_title for kw in keywords)]


# ═══════════════════════════════════════════════════════════════════════════
#  Episode Regex & Size Helpers
# ═══════════════════════════════════════════════════════════════════════════

def get_cache_check_reg(episode):
    episode = str(episode)
    season = ''
    reg_string = r'''(?ix)                              # Ignore case (i), and use verbose regex (x)
                 (?:                                    # non-grouping pattern
                   s|season                             # s or season
                   )?
                 ({})?                                  # season num format
                 (?:                                    # non-grouping pattern
                   e|x|episode|ep|ep\.|_|-|\(           # e or x or episode or start of a line
                   )                                    # end non-grouping pattern
                 \s*                                    # 0-or-more whitespaces
                 (?<![\d])
                 ({}|{}|{})                             # episode num format: xx or xxx or xxxx
                 (?![\d])
                 '''.format(season, episode.zfill(2), episode.zfill(3), episode.zfill(4))
    return re.compile(reg_string)


def convert_to_bytes(size, units):
    unit = units.upper()
    if unit == 'KB':
        byte_size = size * 2**10
    elif unit == 'MB':
        byte_size = size * 2**20
    elif unit == 'GB':
        byte_size = size * 2**30
    elif unit == 'TB':
        byte_size = size * 2**40
    else:
        raise ValueError("Unit must be 'KB', 'MB', 'GB', 'TB' ")
    return byte_size


def get_size(size=0):
    power = 1024.0
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return '{0:.2f} {1}'.format(size, power_labels[n])


# ═══════════════════════════════════════════════════════════════════════════
#  Fuzzy Matching
# ═══════════════════════════════════════════════════════════════════════════

def get_fuzzy_match(query, filenames):
    """
    Multi-stage fuzzy matching for torrent/file selection.
    Uses local algorithms for accuracy and speed (no external API dependency).

    Returns: List of indices that match the query, sorted by best match first
    """
    from difflib import SequenceMatcher

    if not query or not filenames:
        return []

    # Normalize query for matching
    query_clean = cleanTitle(query)
    query_lower = query.lower()

    # Stage 1: Exact match (case-insensitive)
    exact_matches = []
    for i, filename in enumerate(filenames):
        if query_lower in filename.lower():
            exact_matches.append((i, 1.0))  # Perfect score

    if exact_matches:
        control.log(f"Fuzzy Match: Found {len(exact_matches)} exact matches for '{query}'")
        return [i for i, _ in exact_matches]

    # Stage 2: Token-based matching (handles reordered words)
    query_tokens = set(query_clean.split())
    token_matches = []

    for i, filename in enumerate(filenames):
        filename_clean = cleanTitle(filename)
        filename_tokens = set(filename_clean.split())

        # Calculate token overlap
        common_tokens = query_tokens & filename_tokens
        if common_tokens:
            # Jaccard similarity: intersection / union
            jaccard = len(common_tokens) / len(query_tokens | filename_tokens)

            # Token coverage: what % of query tokens are present
            coverage = len(common_tokens) / len(query_tokens) if query_tokens else 0

            # Combined score (weighted average)
            score = (jaccard * 0.4) + (coverage * 0.6)

            if score >= 0.5:  # Threshold: at least 50% match
                token_matches.append((i, score))

    if token_matches:
        token_matches.sort(key=lambda x: x[1], reverse=True)
        control.log(f"Fuzzy Match: Found {len(token_matches)} token matches for '{query}' (best: {token_matches[0][1]:.2f})")
        return [i for i, _ in token_matches]

    # Stage 3: Sequence matching with difflib (handles typos, partial matches)
    sequence_matches = []
    threshold = control.getInt('general.fuzzy') / 100.0 if control.getInt('general.fuzzy') > 0 else 0.6

    for i, filename in enumerate(filenames):
        filename_clean = cleanTitle(filename)

        # Use SequenceMatcher for similarity ratio
        ratio = SequenceMatcher(None, query_clean, filename_clean).ratio()

        if ratio >= threshold:
            sequence_matches.append((i, ratio))

    if sequence_matches:
        sequence_matches.sort(key=lambda x: x[1], reverse=True)
        control.log(f"Fuzzy Match: Found {len(sequence_matches)} sequence matches for '{query}' (best: {sequence_matches[0][1]:.2f})")
        return [i for i, _ in sequence_matches]

    # Stage 4: Fallback - Close matches with lower threshold
    fallback_matches = []

    for i, filename in enumerate(filenames):
        filename_clean = cleanTitle(filename)

        # Try both ways (query in filename, filename in query)
        ratio1 = SequenceMatcher(None, query_clean, filename_clean).ratio()
        ratio2 = SequenceMatcher(None, query_lower, filename.lower()).ratio()

        max_ratio = max(ratio1, ratio2)

        if max_ratio >= 0.4:  # Lower threshold for fallback
            fallback_matches.append((i, max_ratio))

    if fallback_matches:
        fallback_matches.sort(key=lambda x: x[1], reverse=True)
        control.log(f"Fuzzy Match: Found {len(fallback_matches)} fallback matches for '{query}' (best: {fallback_matches[0][1]:.2f})")
        return [i for i, _ in fallback_matches[:10]]  # Limit to top 10

    # No matches found
    control.log(f"Fuzzy Match: No matches found for '{query}'")
    return []


def get_best_match(dict_key, dictionary_list, episode, pack_select=False):
    control.setBool('best_match', True)
    regex = get_cache_check_reg(episode)
    files = []
    for i in dictionary_list:
        path = re.sub(r'\[.*?]', '', i[dict_key].split('/')[-1])
        if not is_file_ext_valid(path):
            continue
        i['regex_matches'] = regex.findall(path)
        files.append(i)
    if pack_select:
        files = user_select(files, dict_key)
    else:
        files = [i for i in files if len(i['regex_matches']) > 0]
        if len(files) == 0:
            control.setBool('best_match', False)
            return {}
        files = sorted(files, key=lambda x: len(' '.join(list(x['regex_matches'][0]))), reverse=True)
        if len(files) != 1:
            files = user_select(files, dict_key)

    return files[0]


# ═══════════════════════════════════════════════════════════════════════════
#  Torrent Filtering
# ═══════════════════════════════════════════════════════════════════════════

def filter_sources(provider, torrent_list, mal_id, season=None, episode=None, part=None, anidb_id=True):
    from resources.lib.ui import database
    """
    Filter torrents based on season, episode, and part information.
    Uses improved regex patterns to handle a wider variety of media title formats.
    """
    # Check for Large Animes or Tvdb Animes with season 0
    if season == 1:
        mal_mapping = database.get_mappings(mal_id, 'mal_id')
        if mal_mapping and 'thetvdb_season' in mal_mapping:
            thetvdb_season = mal_mapping['thetvdb_season']
            if thetvdb_season == 'a' or thetvdb_season == 0:
                season = None

    # Define regexes from the testing file
    regex_season = re.compile(r"(?i)\b(?:s(?:eason)?[ ._-]?(\d{1,2}))(?!\d)")
    regex_episode = re.compile(r"""(?ix)
        (?:^|[\s._-])                     # separator
        (?:e(?:p)?\s?(\d{1,4}))           # E12, EP12
        |
        -\s?(\d{1,4})\b                   # - 12
        |
        \b(?:episode|ep|e)\s?(\d{1,4})\b   # ep 03
        |
        s\d{1,2}e(\d{1,4})                # s01e07 format
        |
        (\d{1,4})\s+(\d{1,4})             # standalone episode range
    """)
    regex_episode_range = re.compile(r"(\d{1,4})\s*[~\-]\s*(\d{1,4})")
    regex_part = re.compile(r"(?i)\b(?:part|cour)[ ._-]?(\d+)(?:[&-](\d+))?\b")
    regex_trailing_number = re.compile(r"""(?ix)
        \b(?:[a-z]{3,})\s+(\d{1,3})\b
    """)
    regex_ordinal_check = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)

    filtered = []

    # Loop over each torrent in the list
    for torrent in torrent_list:
        # Set up the torrent hash as in the original function
        if provider == 'animetosho':
            if 'hash' not in torrent:
                continue
        elif provider == 'nekobt':
            if 'hash' not in torrent:
                continue
        elif provider == 'nyaa':
            torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]
        elif provider == 'realdebrid':
            torrent['hash'] = torrent.get('hash', '')
        elif provider == 'alldebrid':
            link = torrent['link']
            torrent['hash'] = re.search(r'/f/([^/]+)', link).group(1)
        elif provider == 'premiumize':
            torrent['hash'] = torrent.get('id', '')
        elif provider == 'torbox':
            torrent['hash'] = torrent.get('hash', '')
        elif provider == 'local':
            torrent['hash'] = torrent.get('path', '')
        else:
            continue

        # Select the title based on provider
        if provider in ['realdebrid', 'alldebrid']:
            title = torrent['filename'].lower()
        else:
            title = torrent['name'].lower()

        # Clean the title for extraction
        clean_title = clean_text(title)

        # Extract parts
        part_matches = regex_part.findall(title)
        extracted_parts = []
        for match in part_matches:
            for group in match:
                if group:
                    extracted_parts.append(group)

        # Extract seasons
        season_matches = regex_season.findall(title)
        extracted_seasons = None
        if season_matches:
            extracted_seasons = ", ".join(season_matches)

        # For episode extraction, remove part tokens from the clean title
        clean_title_no_parts = re.sub(regex_part, "", clean_title)

        # Extract episode using the improved logic from testing.py
        extracted_episode = None

        # First, if an sXXeYY pattern exists, extract the episode number directly
        se_match = re.search(r"s\d{1,2}e(\d{1,4})", clean_title_no_parts, re.IGNORECASE)
        if se_match:
            epnum = se_match.group(1)
            if not (extracted_parts and epnum in extracted_parts):
                extracted_episode = epnum

        # Otherwise, check for a dedicated episode range using "~" or "-"
        if not extracted_episode:
            range_match = regex_episode_range.search(clean_title_no_parts)
            if range_match:
                start, end = range_match.group(1), range_match.group(2)
                if not (extracted_parts and (start in extracted_parts or end in extracted_parts)):
                    extracted_episode = f"{start}-{end}"

        # Fallback: use the regex_episode findall approach
        if not extracted_episode:
            ep_match = regex_episode.findall(clean_title_no_parts)
            if ep_match:
                episodes = []
                for match in ep_match:
                    for group in match:
                        if group and group not in extracted_parts:
                            episodes.append(group)

                # If season is detected, drop a leading number equal to a season
                if extracted_seasons and episodes:
                    try:
                        season_nums = [int(s.strip()) for s in extracted_seasons.split(",") if s.strip().isdigit()]
                        if episodes[0].isdigit() and int(episodes[0]) in season_nums:
                            episodes = episodes[1:]
                    except Exception:
                        season_nums = []

                if len(episodes) >= 2 and episodes[0].isdigit() and episodes[-1].isdigit():
                    extracted_episode = f"{episodes[0]}-{episodes[-1]}"
                elif episodes:
                    extracted_episode = ", ".join(episodes)

        # Fallback: get final word-number match (unless it matches a part)
        if not extracted_episode:
            trail_matches = regex_trailing_number.findall(clean_title_no_parts)
            if trail_matches:
                last_num = trail_matches[-1]
                if not (extracted_parts and last_num in extracted_parts):
                    if extracted_seasons:
                        try:
                            season_nums = [int(s.strip()) for s in extracted_seasons.split(",") if s.strip().isdigit()]
                            if last_num.isdigit() and int(last_num) in season_nums:
                                extracted_episode = None
                            elif not regex_ordinal_check.search(clean_title_no_parts):
                                extracted_episode = last_num
                        except Exception:
                            season_nums = []
                    elif not regex_ordinal_check.search(clean_title_no_parts):
                        extracted_episode = last_num

        # Determine if we have any metadata to filter by
        has_info = bool(extracted_episode or extracted_seasons or extracted_parts)

        # For the inverted filter, torrents with no info are immediately added.
        if not has_info:
            filtered.append(torrent)
            continue

        valid = True

        # Check episode match if applicable
        if episode and extracted_episode:
            episode_nums = []
            # Handle episode ranges
            if "-" in extracted_episode:
                start, end = extracted_episode.split("-")
                try:
                    episode_nums = list(range(int(start), int(end) + 1))
                except (ValueError, TypeError):
                    valid = False
            # Handle single episode
            else:
                try:
                    episode_nums = [int(extracted_episode)]
                except (ValueError, TypeError):
                    valid = False

            if episode_nums:
                try:
                    req_ep = int(episode)
                    if req_ep not in episode_nums:
                        valid = False
                except (ValueError, TypeError):
                    valid = False

        # Check season match if applicable
        if season and extracted_seasons:
            season_nums = []
            for s in extracted_seasons.split(","):
                try:
                    season_nums.append(int(s.strip()))
                except (ValueError, TypeError):
                    pass

            if season_nums:
                try:
                    req_season = int(season)
                    if req_season not in season_nums:
                        valid = False
                except (ValueError, TypeError):
                    valid = False

        # Check part match if applicable
        if part and extracted_parts:
            part_nums = []
            for p in extracted_parts:
                try:
                    part_nums.append(int(p))
                except (ValueError, TypeError):
                    pass

            if part_nums:
                try:
                    req_part = int(part)
                    if req_part not in part_nums:
                        valid = False
                except (ValueError, TypeError):
                    valid = False

        if valid:
            filtered.append(torrent)

    return filtered


# ═══════════════════════════════════════════════════════════════════════════
#  Text Cleaning
# ═══════════════════════════════════════════════════════════════════════════

def remove_patterns(text):
    patterns = [
        r"\b(?:360p|480p|720p|1080p|2160p|4k)(?!\d)",
        r"\b10\s?bits?\b",  # matches 10bit, 10bits, 10 bit, 10 bits
        r"\b(?:h\.?\s?264|x\.?\s?264|h\.?\s?265|x\.?\s?265|hevc|avc|hls)(?!\d)",
        r"\b(?:web-dl|webrip|bluray|hdrip|dvdrip|hdtv|pdtv|cam|screener)\b",
        r"\b(?:hdr10|hdr|sdr|dv|dolby vision|dovi)\b",
        r"\b(?:mp4|vp9|av1|mpeg|xvid|divx|wmv|flac)\b",
        r"\b(?:aac|mp3|opus|ddp|dd(?:\s?(?:2|5|7))|ac3|dts(?:-hdma|-hdhr|-x)?|atmos|truehd)(?:\d+(?:\.\d+)?)?\b",
        r"\b(?:1\.0|2\.0|5\.1|7\.1|2ch|5ch|7ch|8ch)\b",
        r"\b(?:3d|60[-\s]?fps)\b",
        r"\b(?:multi audio|dual audio|dub(?:bed)?|multi sub|batch|complete series)\b"
    ]
    combined_pattern = "|".join(patterns)
    return re.sub(combined_pattern, "", text, flags=re.I)


def cleanup_text(text):
    # Remove content within brackets or parentheses
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text).strip()
    # Replace special characters with a space, but preserve dashes for episode range detection
    text = re.sub(r"[:/,!?()'\"\\\[\]_.]", " ", text)
    # Collapse multiple spaces into one
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text):
    text = remove_patterns(text)
    text = cleanup_text(text)
    return text


def cleanTitle(title):
    title = title.lower()
    result = ''.join(char for char in title if char in string.printable)
    title = result.encode('ascii', errors='ignore').decode('ascii', errors='ignore')
    apostrophe_replacement = 's'
    title = title.replace("\\'s", apostrophe_replacement)
    title = title.replace("'s", apostrophe_replacement)
    title = title.replace("&#039;s", apostrophe_replacement)
    title = title.replace(" 039 s", apostrophe_replacement)
    title = re.sub(r'[:/,!?()\'"\\\[\]\-_.]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    title = re.sub(r'&', 'and', title)
    return title.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  File Utilities
# ═══════════════════════════════════════════════════════════════════════════

def is_file_ext_valid(file_name):
    return False if '.' + file_name.split('.')[-1] not in video_ext() else True


def video_ext():
    COMMON_VIDEO_EXTENSIONS = xbmc.getSupportedMedia('video').split('|')
    COMMON_VIDEO_EXTENSIONS = [i for i in COMMON_VIDEO_EXTENSIONS if i != '' and i != '.zip']
    return COMMON_VIDEO_EXTENSIONS


def user_select(files, dict_key):
    idx = control.select_dialog('Select File', [i[dict_key].rsplit('/')[-1] for i in files])
    if idx == -1:
        file = [{'path': ''}]
    else:
        file = [files[idx]]
    return file


def get_embedhost(url):
    s = re.search(r'(?://|\.)([^.]+)\.', url)
    return s.group(1)
