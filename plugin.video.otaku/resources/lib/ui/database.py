"""
database.py - Otaku Database & Caching Layer
=============================================
Clean, organized caching and metadata storage.

Architecture
------------
SQL          - Thread-safe SQLite context manager (module-level lock)
Memory Cache - Window-property RAM cache with expiry
General Cache- 3-tier caching: RAM → SQLite → fresh API call
Shows        - Anime show / meta / episode CRUD
Mappings     - Cross-service ID lookups
Watchlist    - Per-service watchlist cache with activity invalidation
Enrichment   - AniList supplementary metadata cache
History      - Per-category search history
Maintenance  - Cache clearing helpers
"""

import ast
import hashlib
import pickle
import re
import time
import threading

import xbmcgui
import xbmcvfs

from sqlite3 import OperationalError, dbapi2
from resources.lib.ui import control


# ═══════════════════════════════════════════════════════════════════════════
#  SQL - Thread-Safe SQLite Context Manager
# ═══════════════════════════════════════════════════════════════════════════

_db_lock = threading.Lock()


def _dict_factory(cursor, row):
    """Row factory that returns dicts keyed by column name."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class SQL:
    """Thread-safe SQLite context manager with optimized PRAGMAs.

    Uses a *module-level* lock so concurrent threads cannot
    corrupt data.  Always closes the connection on exit.

    Usage::

        with SQL(db_path) as cursor:
            cursor.execute('SELECT ...')
            cursor.connection.commit()   # needed for writes
    """

    def __init__(self, path, timeout=60):
        self.path = path
        self.timeout = timeout

    def __enter__(self):
        _db_lock.acquire()
        try:
            xbmcvfs.mkdir(control.dataPath)
            self._conn = dbapi2.connect(self.path, timeout=self.timeout)
            self._conn.row_factory = _dict_factory
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA mmap_size = 268435456")  # 256 MB mmap I/O
            self._cursor = self._conn.cursor()
            return self._cursor
        except Exception:
            _db_lock.release()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._conn.close()
        except Exception:
            pass
        finally:
            _db_lock.release()

        if exc_type:
            if exc_type is OperationalError:
                import traceback
                control.log('database OperationalError', level='error')
                control.log(''.join(traceback.format_exception(
                    exc_type, exc_val, exc_tb)), level='error')
                return True
            import traceback
            control.log('database error', level='error')
            control.log(''.join(traceback.format_exception(
                exc_type, exc_val, exc_tb)), level='error')
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  Memory Cache - Kodi Window Properties with Expiry
# ═══════════════════════════════════════════════════════════════════════════

_window = xbmcgui.Window(10000)
_MEM_PREFIX = 'otaku_test_'


def _mem_get(key):
    """Return parsed data or *None* if missing / expired."""
    raw = _window.getProperty(_MEM_PREFIX + key)
    if not raw:
        return None
    try:
        sep = raw.index('|')
        if int(raw[:sep]) > int(time.time()):
            return ast.literal_eval(raw[sep + 1:])
    except Exception:
        pass
    _window.clearProperty(_MEM_PREFIX + key)
    return None


def _mem_set(key, value_repr, hours):
    """Store *value_repr* (a ``repr()`` string) with an expiry of *hours*."""
    expires = int(time.time() + hours * 3600)
    _window.setProperty(_MEM_PREFIX + key, f"{expires}|{value_repr}")


def _mem_del(key):
    """Remove a single key from the RAM cache."""
    _window.clearProperty(_MEM_PREFIX + key)


# ═══════════════════════════════════════════════════════════════════════════
#  Lazy Table Initialization (once per session)
# ═══════════════════════════════════════════════════════════════════════════

_tables_ready = set()


def _ensure_table(db_path, name, ddl):
    """Run *ddl* only the first time (*db_path*, *name*) is seen."""
    tag = f"{db_path}:{name}"
    if tag in _tables_ready:
        return
    with SQL(db_path) as cur:
        cur.execute(ddl)
        cur.connection.commit()
    _tables_ready.add(tag)


def _init_cache_table():
    _ensure_table(
        control.cacheFile, 'cache',
        'CREATE TABLE IF NOT EXISTS cache '
        '(key TEXT UNIQUE, value TEXT, date INTEGER)'
    )


# ═══════════════════════════════════════════════════════════════════════════
#  General Cache - 3-Tier: RAM → SQLite → Fresh API Call
# ═══════════════════════════════════════════════════════════════════════════

def get(function, duration, *args, **kwargs):
    """Cached function call with 3-tier lookup.

    :param function:  Callable to execute on cache miss.
    :param duration:  Cache validity in **hours**.
    :param args/kwargs:  Forwarded to *function* on miss.
        Special kwarg ``key`` is popped and appended to the cache key.
    """
    key = _hash_function(function, args, kwargs)
    if 'key' in kwargs:
        key += kwargs.pop('key')

    # --- Tier 1: RAM (instant) ---
    mem = _mem_get(key)
    if mem is not None:
        return mem

    # --- Tier 2: SQLite ---
    _init_cache_table()
    with SQL(control.cacheFile) as cur:
        cur.execute('SELECT value, date FROM cache WHERE key=?', (key,))
        row = cur.fetchone()

    if row and is_cache_valid(row['date'], duration):
        try:
            data = ast.literal_eval(row['value'])
            _mem_set(key, row['value'], duration)
            return data
        except Exception:
            control.log(
                f"Cache corrupt for key {key}, fetching fresh data",
                level='warning')

    # --- Tier 3: Fresh call ---
    result = function(*args, **kwargs)
    result_repr = repr(result)
    _cache_write(key, result_repr)
    _mem_set(key, result_repr, duration)
    return result


def remove(function, *args, **kwargs):
    """Remove the cached value for a function call."""
    try:
        key = _hash_function(function, args, kwargs)
        _cache_delete(key)
        _mem_del(key)
        return True
    except Exception:
        return False


# — helpers ------------------------------------------------------------------

def _hash_function(func, args, kwargs):
    name = re.sub(
        r'.+\smethod\s|.+function\s|\sat\s.+|\sof\s.+', '', repr(func))
    return name + generate_md5((args, kwargs))


def generate_md5(*args):
    """MD5 hex-digest of the string representation of *args*."""
    md5 = hashlib.md5()
    for arg in args:
        md5.update(str(arg).encode())
    return md5.hexdigest()


def is_cache_valid(cached_time, hours):
    """True when *cached_time* (epoch) is younger than *hours*."""
    return (int(time.time()) - cached_time) < (hours * 3600)


def _cache_write(key, value_repr):
    _init_cache_table()
    with SQL(control.cacheFile) as cur:
        cur.execute(
            'REPLACE INTO cache (key, value, date) VALUES (?, ?, ?)',
            (key, value_repr, int(time.time())))
        cur.connection.commit()


def _cache_delete(key):
    with SQL(control.cacheFile) as cur:
        cur.execute('DELETE FROM cache WHERE key=?', (key,))
        cur.connection.commit()


# — backward-compat aliases (kept for any external callers) -----------------

def hash_function(function_instance, *args):
    function_name = re.sub(
        r'.+\smethod\s|.+function\s|\sat\s.+|\sof\s.+', '',
        repr(function_instance))
    return function_name + generate_md5(args)


def cache_get(key):
    _init_cache_table()
    with SQL(control.cacheFile) as cur:
        cur.execute('SELECT * FROM cache WHERE key=?', (key,))
        return cur.fetchone()


def cache_insert(key, value):
    _cache_write(key, value)


def cache_remove(key):
    _cache_delete(key)


def cache_clear():
    """Wipe general cache, watchlist cache, activity, and enrichment data."""
    with SQL(control.cacheFile) as cur:
        cur.execute("DROP TABLE IF EXISTS cache")
        cur.execute("VACUUM")
        cur.connection.commit()
    _tables_ready.discard(f"{control.cacheFile}:cache")

    clear_watchlist_cache()
    clear_watchlist_activity()
    clear_anilist_enrichment()

    control.notify(
        f'{control.ADDON_NAME}: {control.lang(30086)}',
        control.lang(30087), time=5000, sound=False)


# ═══════════════════════════════════════════════════════════════════════════
#  Show Operations
# ═══════════════════════════════════════════════════════════════════════════

def get_show(mal_id):
    with SQL(control.malSyncDB) as cur:
        cur.execute('SELECT * FROM shows WHERE mal_id=?', (mal_id,))
        return cur.fetchone()


def update_show(mal_id, kodi_meta, anime_schedule_route=''):
    with SQL(control.malSyncDB) as cur:
        cur.execute('PRAGMA foreign_keys=OFF')
        cur.execute(
            'REPLACE INTO shows '
            '(mal_id, kodi_meta, anime_schedule_route) VALUES (?, ?, ?)',
            (mal_id, kodi_meta, anime_schedule_route))
        cur.execute('PRAGMA foreign_keys=ON')
        cur.connection.commit()


def get_show_meta(mal_id):
    with SQL(control.malSyncDB) as cur:
        cur.execute('SELECT * FROM shows_meta WHERE mal_id=?', (mal_id,))
        return cur.fetchone()


def update_show_meta(mal_id, meta_ids, art):
    with SQL(control.malSyncDB) as cur:
        cur.execute('PRAGMA foreign_keys=OFF')
        cur.execute(
            'REPLACE INTO shows_meta (mal_id, meta_ids, art) VALUES (?, ?, ?)',
            (mal_id, pickle.dumps(meta_ids), pickle.dumps(art)))
        cur.execute('PRAGMA foreign_keys=ON')
        cur.connection.commit()


def update_kodi_meta(mal_id, kodi_meta):
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'UPDATE shows SET kodi_meta=? WHERE mal_id=?',
            (pickle.dumps(kodi_meta), mal_id))
        cur.connection.commit()


def add_mapping_id(mal_id, column, value):
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            f'UPDATE shows SET {column}=? WHERE mal_id=?', (value, mal_id))
        cur.connection.commit()


def get_show_data(mal_id):
    with SQL(control.malSyncDB) as cur:
        cur.execute('SELECT * FROM show_data WHERE mal_id=?', (mal_id,))
        return cur.fetchone()


def update_show_data(mal_id, data, last_updated=''):
    with SQL(control.malSyncDB) as cur:
        cur.execute('PRAGMA foreign_keys=OFF')
        cur.execute(
            'REPLACE INTO show_data '
            '(mal_id, data, last_updated) VALUES (?, ?, ?)',
            (mal_id, pickle.dumps(data), last_updated))
        cur.execute('PRAGMA foreign_keys=ON')
        cur.connection.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Episode Operations
# ═══════════════════════════════════════════════════════════════════════════

def get_episode(mal_id, episode=None):
    with SQL(control.malSyncDB) as cur:
        if episode:
            cur.execute(
                'SELECT * FROM episodes WHERE mal_id=? AND number=?',
                (mal_id, episode))
        else:
            cur.execute(
                'SELECT * FROM episodes WHERE mal_id=?', (mal_id,))
        return cur.fetchone()


def get_episode_list(mal_id):
    with SQL(control.malSyncDB) as cur:
        cur.execute('SELECT * FROM episodes WHERE mal_id=?', (mal_id,))
        return cur.fetchall()


def update_episode(mal_id, season, number, update_time, kodi_meta,
                   filler='', anidb_ep_id=''):
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'REPLACE INTO episodes '
            '(mal_id, season, kodi_meta, last_updated, number, filler, anidb_ep_id) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (mal_id, season, kodi_meta, update_time, number, filler, anidb_ep_id))
        cur.connection.commit()


def update_episode_column(mal_id, episode, column, value):
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            f'UPDATE episodes SET {column}=? WHERE mal_id=? AND number=?',
            (value, mal_id, episode))
        cur.connection.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Mapping & Info Lookups
# ═══════════════════════════════════════════════════════════════════════════

def get_mappings(anime_id, send_id):
    with SQL(control.mappingDB) as cur:
        cur.execute(
            f'SELECT * FROM anime WHERE {send_id}=?', (anime_id,))
        rows = cur.fetchall()
        return rows[0] if rows else {}


def get_unique_ids(anime_id, send_id):
    with SQL(control.mappingDB) as cur:
        cur.execute(
            f'SELECT mal_id, mal_dub_id, anilist_id, kitsu_id, anidb_id, '
            f'simkl_id, thetvdb_id, themoviedb_id, imdb_id, trakt_id '
            f'FROM anime WHERE {send_id}=?', (anime_id,))
        row = cur.fetchone()
        if not row:
            return {}
        return {
            'mal_id':     row.get('mal_id'),
            'mal_dub_id': row.get('mal_dub_id'),
            'anilist_id': row.get('anilist_id'),
            'kitsu_id':   row.get('kitsu_id'),
            'anidb':      row.get('anidb_id'),
            'simkl':      row.get('simkl_id'),
            'tvdb':       row.get('thetvdb_id'),
            'tmdb':       row.get('themoviedb_id'),
            'imdb':       row.get('imdb_id'),
            'trakt':      row.get('trakt_id'),
        }


def get_mal_ids(anime_id, send_id):
    with SQL(control.mappingDB) as cur:
        cur.execute(
            f'SELECT * FROM anime WHERE {send_id}=?', (anime_id,))
        return cur.fetchall() or []


def get_info(api_name):
    with SQL(control.infoDB) as cur:
        cur.execute('SELECT * FROM info WHERE api_name=?', (api_name,))
        return cur.fetchone()


def remove_from_database(table, mal_id):
    with SQL(control.malSyncDB) as cur:
        cur.execute(f'DELETE FROM {table} WHERE mal_id=?', (mal_id,))
        cur.connection.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Watchlist Cache
# ═══════════════════════════════════════════════════════════════════════════

def get_watchlist_cache(service, status, limit=None, offset=0):
    """Cached watchlist items, optionally paginated."""
    with SQL(control.malSyncDB) as cur:
        if limit:
            cur.execute(
                'SELECT * FROM watchlist_cache '
                'WHERE service=? AND status=? ORDER BY id LIMIT ? OFFSET ?',
                (service, status, limit, offset))
        else:
            cur.execute(
                'SELECT * FROM watchlist_cache '
                'WHERE service=? AND status=? ORDER BY id',
                (service, status))
        return cur.fetchall()


def get_watchlist_cache_count(service, status):
    """Count of cached items for a service / status pair."""
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'SELECT COUNT(*) as count FROM watchlist_cache '
            'WHERE service=? AND status=?', (service, status))
        row = cur.fetchone()
        return row['count'] if row else 0


def get_watchlist_cache_last_updated(service, status):
    """Oldest update timestamp for a service / status pair."""
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'SELECT MIN(last_updated) as last_updated FROM watchlist_cache '
            'WHERE service=? AND status=?', (service, status))
        row = cur.fetchone()
        return row['last_updated'] if row else None


def save_watchlist_cache(service, status, items):
    """Replace all cache entries for a service / status pair."""
    now = int(time.time())
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'DELETE FROM watchlist_cache WHERE service=? AND status=?',
            (service, status))
        for idx, item in enumerate(items):
            cur.execute(
                'INSERT INTO watchlist_cache '
                '(service, status, mal_id, item_order, data, last_updated) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (service, status, _extract_mal_id(service, item),
                 idx, pickle.dumps(item), now))
        cur.connection.commit()


def _extract_mal_id(service, item):
    """Pull MAL ID from a watchlist item based on service structure."""
    extractors = {
        'simkl':   lambda i: i.get('show', {}).get('ids', {}).get('mal'),
        'kitsu':   lambda i: i.get('mal_id'),
        'mal':     lambda i: i.get('node', {}).get('id'),
        'anilist': lambda i: i.get('media', {}).get('idMal'),
    }
    fn = extractors.get(service)
    return fn(item) if fn else None


def clear_watchlist_cache(service=None, status=None):
    """Clear cache, optionally filtered by service and/or status."""
    with SQL(control.malSyncDB) as cur:
        if service and status:
            cur.execute(
                'DELETE FROM watchlist_cache WHERE service=? AND status=?',
                (service, status))
        elif service:
            cur.execute(
                'DELETE FROM watchlist_cache WHERE service=?', (service,))
        else:
            cur.execute('DELETE FROM watchlist_cache')
        cur.connection.commit()


def is_watchlist_cache_valid(service, status, cache_hours=24):
    """Safety-net fallback (primary invalidation is activity-based)."""
    last = get_watchlist_cache_last_updated(service, status)
    return is_cache_valid(last, cache_hours) if last else False


# ═══════════════════════════════════════════════════════════════════════════
#  Watchlist Activity  (activity-based cache invalidation)
# ═══════════════════════════════════════════════════════════════════════════

def get_watchlist_activity(service):
    """Stored activity record for a watchlist service."""
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'SELECT * FROM watchlist_activity WHERE service=?', (service,))
        return cur.fetchone()


def save_watchlist_activity(service, activity_timestamp):
    """Save the last known activity timestamp for a service."""
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'REPLACE INTO watchlist_activity '
            '(service, activity_timestamp, last_checked) VALUES (?, ?, ?)',
            (service, str(activity_timestamp), int(time.time())))
        cur.connection.commit()


def clear_watchlist_activity(service=None):
    """Clear stored activity timestamps."""
    try:
        with SQL(control.malSyncDB) as cur:
            if service:
                cur.execute(
                    'DELETE FROM watchlist_activity WHERE service=?',
                    (service,))
            else:
                cur.execute('DELETE FROM watchlist_activity')
            cur.connection.commit()
    except Exception:
        pass  # table may not exist on first run


# ═══════════════════════════════════════════════════════════════════════════
#  AniList Enrichment Cache
# ═══════════════════════════════════════════════════════════════════════════

def get_all_watchlist_mal_ids():
    """All unique MAL IDs across every cached watchlist entry."""
    with SQL(control.malSyncDB) as cur:
        cur.execute(
            'SELECT DISTINCT mal_id FROM watchlist_cache '
            'WHERE mal_id IS NOT NULL')
        rows = cur.fetchall()
    result = []
    for row in rows:
        try:
            result.append(int(row['mal_id']))
        except (ValueError, TypeError):
            pass
    return result


def save_anilist_enrichment_batch(data_list):
    """Save AniList media objects keyed by ``idMal``."""
    if not data_list:
        return
    now = int(time.time())
    with SQL(control.malSyncDB) as cur:
        for item in data_list:
            mal_id = item.get('idMal')
            if not mal_id:
                continue
            cur.execute(
                'REPLACE INTO anilist_enrichment '
                '(mal_id, data, last_updated) VALUES (?, ?, ?)',
                (int(mal_id), pickle.dumps(item), now))
        cur.connection.commit()


def get_anilist_enrichment_batch(mal_ids, max_age_hours=168):
    """Cached AniList enrichment for given MAL IDs (default 7 days max)."""
    if not mal_ids:
        return {}
    cutoff = int(time.time()) - (max_age_hours * 3600)
    result = {}
    with SQL(control.malSyncDB) as cur:
        ph = ','.join('?' for _ in mal_ids)
        cur.execute(
            f'SELECT * FROM anilist_enrichment '
            f'WHERE mal_id IN ({ph}) AND last_updated > ?',
            [int(m) for m in mal_ids] + [cutoff])
        for row in cur.fetchall():
            try:
                result[row['mal_id']] = pickle.loads(row['data'])
            except Exception:
                pass
    return result


def clear_anilist_enrichment():
    """Clear all AniList enrichment data."""
    with SQL(control.malSyncDB) as cur:
        cur.execute('DELETE FROM anilist_enrichment')
        cur.connection.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Search History
# ═══════════════════════════════════════════════════════════════════════════

_SEARCH_TYPES = (
    'anime', 'movie', 'tv_show', 'tv_short',
    'special', 'ova', 'ona', 'music',
)


def _ensure_search_tables(cur):
    for t in _SEARCH_TYPES:
        cur.execute(f'CREATE TABLE IF NOT EXISTS {t} (value TEXT UNIQUE)')


def getSearchHistory(media_type):
    with SQL(control.searchHistoryDB) as cur:
        _ensure_search_tables(cur)
        cur.execute(f'SELECT * FROM {media_type}')
        history = cur.fetchall()
    history.reverse()
    seen = set()
    return [h['value'] for h in history[:50]
            if h['value'] not in seen and not seen.add(h['value'])]


def addSearchHistory(search_string, media_type):
    with SQL(control.searchHistoryDB) as cur:
        _ensure_search_tables(cur)
        cur.execute(
            f'REPLACE INTO {media_type} VALUES (?)', (search_string,))
        cur.connection.commit()


def clearSearchHistory():
    if not control.yesno_dialog(
            control.ADDON_NAME, "Clear all search history?"):
        return
    with SQL(control.searchHistoryDB) as cur:
        for t in _SEARCH_TYPES:
            cur.execute(f'DROP TABLE IF EXISTS {t}')
        cur.execute("VACUUM")
        cur.connection.commit()
    control.refresh()
    control.notify(
        control.ADDON_NAME, "Search History has been cleared", time=5000)


def clearSearchCatagory(media_type):
    if not control.yesno_dialog(
            control.ADDON_NAME, "Clear search history?"):
        return
    with SQL(control.searchHistoryDB) as cur:
        cur.execute(f'DROP TABLE IF EXISTS {media_type}')
        cur.execute(
            f'CREATE TABLE IF NOT EXISTS {media_type} (value TEXT UNIQUE)')
        cur.connection.commit()
    control.refresh()
    control.notify(
        control.ADDON_NAME, "Search History has been cleared", time=5000)


def remove_search(table, value):
    norm = value.strip()
    with SQL(control.searchHistoryDB) as cur:
        cur.execute(f'DELETE FROM {table} WHERE value=?', (norm,))
        deleted = cur.rowcount
        cur.connection.commit()
    control.refresh()
    if deleted == 0:
        control.notify(
            control.ADDON_NAME,
            f"Search item not found: '{norm}'", time=3000)
