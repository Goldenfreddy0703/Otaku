"""
Debrid Cache - Local SQLite cache for debrid hash availability.

Stores previously checked torrent hashes and their cached status per debrid service.
Uses external services (Torrentio, AIOStreams, DMM) to check RD/AD cache status
since those services removed their native cache-check APIs.
"""

import random
import re
import time
import threading

from resources.lib.ui import control, client, database


# ═══════════════════════════════════════════════════════════════════════════
#  Debrid Cache DB Operations
# ═══════════════════════════════════════════════════════════════════════════

_CACHE_EXPIRY_HOURS = 24


def _ensure_debrid_cache_table():
    database._ensure_table(
        control.cacheFile, 'debrid_cache',
        'CREATE TABLE IF NOT EXISTS debrid_cache '
        '(hash TEXT, debrid TEXT, cached TEXT, expires INTEGER, '
        'UNIQUE(hash, debrid))'
    )


def get_cached_hashes(hash_list):
    """Get previously cached hash results from local DB."""
    if not hash_list:
        return []
    _ensure_debrid_cache_table()
    now = int(time.time())
    placeholders = ', '.join('?' for _ in hash_list)
    with database.SQL(control.cacheFile) as cur:
        cur.execute(
            f'SELECT hash, debrid, cached FROM debrid_cache '
            f'WHERE hash IN ({placeholders}) AND expires > ?',
            hash_list + [now]
        )
        return cur.fetchall() or []


def set_cached_hashes(hash_status_list, debrid):
    """Store hash cache status results. hash_status_list = [(hash, 'True'/'False'), ...]"""
    if not hash_status_list:
        return
    _ensure_debrid_cache_table()
    expires = int(time.time()) + (_CACHE_EXPIRY_HOURS * 3600)
    with database.SQL(control.cacheFile) as cur:
        cur.executemany(
            'REPLACE INTO debrid_cache (hash, debrid, cached, expires) VALUES (?, ?, ?, ?)',
            [(h, debrid, status, expires) for h, status in hash_status_list]
        )
        cur.connection.commit()


def clear_debrid_cache():
    """Clear the entire debrid cache table."""
    _ensure_debrid_cache_table()
    with database.SQL(control.cacheFile) as cur:
        cur.execute('DELETE FROM debrid_cache')
        cur.execute('VACUUM')
        cur.connection.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  External Cache Checking (for RD/AD)
# ═══════════════════════════════════════════════════════════════════════════

def check_rd_cache(hash_list, imdb_id, season, episode):
    """Check Real-Debrid cache status using external services (Torrentio + DMM)."""
    cached_hashes = []
    threads = [
        threading.Thread(target=_tio_check_cache, args=(imdb_id, season, episode, cached_hashes)),
        threading.Thread(target=_dmm_check_cache, args=(hash_list, imdb_id, cached_hashes)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return list(set(cached_hashes))


def check_ad_cache(imdb_id, season, episode):
    """Check AllDebrid cache status using external services (AIOStreams)."""
    cached_hashes = []
    threads = [
        threading.Thread(target=_aio_check_cache, args=(imdb_id, season, episode, cached_hashes)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return list(set(cached_hashes))


def _tio_check_cache(imdb_id, season, episode, collector):
    """Check Torrentio for Real-Debrid cached torrents."""
    if not imdb_id:
        return
    try:
        if str(season).isdigit() and int(season) > 0:
            url_path = f'series/{imdb_id}:{season}:{episode}.json'
        else:
            url_path = f'movie/{imdb_id}.json'
        params = 'realdebrid=T2iZoymNCCD1T5c2sX5u8tIZVcgcFWlCsCJ72rCmrU2mDdmvgieM'
        url = f'https://torrentio.strem.fun/debridoptions=nodownloadlinks,nocatalog|{params}/stream/{url_path}'
        pattern = re.compile(r'\b\w{40}\b')
        response = client.get(url, timeout=7)
        if response and response.ok:
            files = response.json().get('streams', [])
            for f in files:
                if '+' in f.get('name', '') and 'url' in f:
                    matches = pattern.findall(f['url'])
                    if matches:
                        collector.append(matches[-1])
    except Exception as e:
        control.log(f'Torrentio cache check error: {e}', 'warning')


def _aio_check_cache(imdb_id, season, episode, collector):
    """Check AIOStreams for AllDebrid cached torrents."""
    if not imdb_id:
        return
    try:
        if str(season).isdigit() and int(season) > 0:
            params = {'type': 'series', 'id': f'{imdb_id}:{season}:{episode}'}
        else:
            params = {'type': 'movie', 'id': str(imdb_id)}

        headers = {
            'x-aiostreams-user-data': (
                'ewogICJzZXJ2aWNlcyI6IFsKICAgIHsKICAgICAgImlkIjogImFsbGRlYnJpZCIsCiAgICAgICJlbmFi'
                'bGVkIjogdHJ1ZSwKICAgICAgImNyZWRlbnRpYWxzIjogeyJhcGlLZXkiOiAic3RhdGljRGVtb0FwaWtl'
                'eVByZW0ifQogICAgfQogIF0sCiAgInByZXNldHMiOiBbCiAgICB7CiAgICAgICJ0eXBlIjogIm1lZGlh'
                'ZnVzaW9uIiwKICAgICAgImluc3RhbmNlSWQiOiAiNWI4IiwKICAgICAgImVuYWJsZWQiOiB0cnVlLAog'
                'ICAgICAib3B0aW9ucyI6IHsKICAgICAgICAibmFtZSI6ICJNZWRpYUZ1c2lvbiIsCiAgICAgICAgInRp'
                'bWVvdXQiOiA2NTAwLAogICAgICAgICJyZXNvdXJjZXMiOiBbInN0cmVhbSJdLAogICAgICAgICJ1c2VD'
                'YWNoZWRSZXN1bHRzT25seSI6IHRydWUsCiAgICAgICAgImVuYWJsZVdhdGNobGlzdENhdGFsb2dzIjog'
                'ZmFsc2UsCiAgICAgICAgImRvd25sb2FkVmlhQnJvd3NlciI6IGZhbHNlLAogICAgICAgICJjb250cmli'
                'dXRvclN0cmVhbXMiOiBmYWxzZSwKICAgICAgICAiY2VydGlmaWNhdGlvbkxldmVsc0ZpbHRlciI6IFtd'
                'LAogICAgICAgICJudWRpdHlGaWx0ZXIiOiBbXSwKICAgICAgICAibWVkaWFUeXBlcyI6IFtdCiAgICAg'
                'IH0KICAgIH0sCiAgICB7CiAgICAgICJ0eXBlIjogInN0cmVtdGhydVRvcnoiLAogICAgICAiaW5zdGFu'
                'Y2VJZCI6ICI1NDgiLAogICAgICAiZW5hYmxlZCI6IHRydWUsCiAgICAgICJvcHRpb25zIjogewogICAg'
                'ICAgICJuYW1lIjogIlN0cmVtVGhydSBUb3J6IiwKICAgICAgICAidGltZW91dCI6IDY1MDAsCiAgICAg'
                'ICAgInJlc291cmNlcyI6IFsic3RyZWFtIl0sCiAgICAgICAgIm1lZGlhVHlwZXMiOiBbXSwKICAgICAg'
                'ICAiaW5jbHVkZVAyUCI6IGZhbHNlLAogICAgICAgICJ1c2VNdWx0aXBsZUluc3RhbmNlcyI6IGZhbHNl'
                'CiAgICAgIH0KICAgIH0KICBdLAogICJmb3JtYXR0ZXIiOiB7CiAgICAiaWQiOiAidG9ycmVudGlvIiwK'
                'ICAgICJkZWZpbml0aW9uIjogewogICAgICAibmFtZSI6ICIiLAogICAgICAiZGVzY3JpcHRpb24iOiAi'
                'IgogICAgfQogIH0sCiAgInNvcnRDcml0ZXJpYSI6IHsKICAgICJnbG9iYWwiOiBbXQogIH0sCiAgImRl'
                'ZHVwbGljYXRvciI6IHsKICAgICJlbmFibGVkIjogZmFsc2UsCiAgICAia2V5cyI6IFsiaW5mb0hhc2gi'
                'XSwKICAgICJtdWx0aUdyb3VwQmVoYXZpb3VyIjogImFnZ3Jlc3NpdmUiLAogICAgImNhY2hlZCI6ICJz'
                'aW5nbGVfcmVzdWx0IiwKICAgICJ1bmNhY2hlZCI6ICJwZXJfc2VydmljZSIsCiAgICAicDJwIjogInNp'
                'bmdsZV9yZXN1bHQiLAogICAgImV4Y2x1ZGVBZGRvbnMiOiBbXQogIH0sCiAgImV4Y2x1ZGVVbmNhY2hl'
                'ZCI6IHRydWUKfQ=='
            )
        }
        url = 'https://aiostreams.fortheweak.cloud/api/v1/search'
        response = client.get(url, params=params, headers=headers, timeout=7)
        if response and response.ok:
            files = response.json().get('data', {}).get('results', [])
            for f in files:
                info_hash = f.get('infoHash')
                if info_hash:
                    collector.append(info_hash)
    except Exception as e:
        control.log(f'AIOStreams cache check error: {e}', 'warning')


def _dmm_check_cache(hash_list, imdb_id, collector):
    """Check DMM (Debrid Media Manager) for cached torrent hashes."""
    if not imdb_id or not hash_list:
        return
    try:
        # DMM only handles 40-char hashes and max 100 per request
        clean_hashes = [h for h in hash_list if len(h) == 40]
        if not clean_hashes:
            return
        if len(clean_hashes) > 100:
            clean_hashes = random.sample(clean_hashes, 100)

        dmm_key, solution = _get_dmm_secret()
        url = 'https://debridmediamanager.com/api/availability/check'
        data = {
            'dmmProblemKey': dmm_key,
            'solution': solution,
            'imdbId': imdb_id,
            'hashes': clean_hashes
        }
        response = client.post(url, json=data, timeout=7)
        if response and response.ok:
            available = response.json().get('available', [])
            for f in available:
                if 'hash' in f:
                    collector.append(f['hash'])
    except Exception as e:
        control.log(f'DMM cache check error: {e}', 'warning')


# ═══════════════════════════════════════════════════════════════════════════
#  DMM Secret Generation (ported from POV)
# ═══════════════════════════════════════════════════════════════════════════

def _to_int32(v):
    """Truncate to signed 32-bit integer (replaces ctypes.c_long for Xbox compat)."""
    v = v & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _get_dmm_secret():
    def _calc_value_alg(t, n, const):
        temp = t ^ n
        t = _to_int32(temp * const)
        t4 = _to_int32(t << 5)
        t5 = _to_int32((t & 0xFFFFFFFF) >> 27)
        return t4 | t5

    def _slice_hash(s, n):
        half = int(len(s) // 2)
        left_s, right_s = s[:half], s[half:]
        left_n, right_n = n[:half], n[half:]
        l = ''.join(ls + ln for ls, ln in zip(left_s, left_n))
        return l + right_n[::-1] + right_s[::-1]

    def _generate_hash(e):
        t = _to_int32(0xDEADBEEF ^ len(e))
        a = 1103547991 ^ len(e)
        for ch in e:
            n = ord(ch)
            t = _calc_value_alg(t, n, 2654435761)
            a = _calc_value_alg(a, n, 1597334677)
        t = _to_int32(t + _to_int32(a * 1566083941))
        a = _to_int32(a + _to_int32(t * 2024237689))
        return _to_int32(t ^ a) & 0xFFFFFFFF

    ran = random.randrange(10 ** 80)
    hex_str = f"{ran:064x}"[:8]
    timestamp = int(time.time())
    dmm_key = f"{hex_str}-{timestamp}"

    s = _generate_hash(dmm_key)
    s = f"{s:x}"

    n = _generate_hash("debridmediamanager.com%%fe7#td00rA3vHz%VmI-" + hex_str)
    n = f"{n:x}"

    solution = _slice_hash(s, n)
    return dmm_key, solution
