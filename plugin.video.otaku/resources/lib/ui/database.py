import ast
import hashlib
import pickle
import re
import time
import threading
import xbmcvfs

from sqlite3 import OperationalError, dbapi2
from resources.lib.ui import control


def get(function, duration, *args, **kwargs):
    """
    Gets cached value for provided function with optional arguments, or executes and stores the result

    :param function: Function to be executed
    :param duration: Duration of validity of cache in hours
    :param args: Optional arguments for the provided function
    :param kwargs: Optional keyword arguments for the provided function
    """
    key = hash_function(function, args, kwargs)
    if 'key' in kwargs:
        key += kwargs.pop('key')
    cache_result = cache_get(key)
    if cache_result and is_cache_valid(cache_result['date'], duration):
        try:
            return_data = ast.literal_eval(cache_result['value'])
            return return_data
        except:
            import traceback
            control.log(traceback.format_exc(), level='error')
            # Cache is corrupted, invalidate it and fetch fresh data
            control.log("Cache corrupted for key: %s, fetching fresh data" % key, level='warning')
            # Don't return None, fall through to fetch fresh data

    fresh_result = repr(function(*args, **kwargs))
    cache_insert(key, fresh_result)
    if not fresh_result:
        return cache_result if cache_result else fresh_result
    data = ast.literal_eval(fresh_result)
    return data


def remove(function, *args, **kwargs):
    # type: (function, object) -> object or None
    """
    Removes cached value for provided function with optional arguments
    :param function: Function results to be deleted from cache
    :param args: Optional arguments for the provided function
    """
    try:
        key = hash_function(function, args, kwargs)
        cache_remove(key)
        return True

    except Exception:
        return False


def hash_function(function_instance, *args):
    function_name = re.sub(r'.+\smethod\s|.+function\s|\sat\s.+|\sof\s.+', '', repr(function_instance))
    return function_name + generate_md5(args)


def generate_md5(*args):
    md5_hash = hashlib.md5()
    [md5_hash.update(str(arg).encode()) for arg in args]
    return str(md5_hash.hexdigest())


def cache_get(key):
    with SQL(control.cacheFile) as cursor:
        cursor.execute('SELECT * FROM cache WHERE key=?', (key,))
        results = cursor.fetchone()
        return results


def cache_insert(key, value):
    now = int(time.time())
    with SQL(control.cacheFile) as cursor:
        cursor.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT, value TEXT, date INTEGER, UNIQUE(key))')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_cache ON cache (key)')
        cursor.execute('REPLACE INTO cache (key, value, date) VALUES (?, ?, ?)', (key, value, now))
        cursor.connection.commit()


def cache_remove(key):
    with SQL(control.cacheFile) as cursor:
        cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
        cursor.connection.commit()
        cursor.close()


def cache_clear():
    with SQL(control.cacheFile) as cursor:
        cursor.execute("DROP TABLE IF EXISTS cache")
        cursor.execute("VACUUM")
        cursor.connection.commit()
        cursor.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT, value TEXT, date INTEGER, UNIQUE(key))')
        control.notify(f'{control.ADDON_NAME}: {control.lang(30086)}', control.lang(30087), time=5000, sound=False)


def is_cache_valid(cached_time, cache_timeout):
    now = int(time.time())
    diff = now - cached_time
    return (cache_timeout * 3600) > diff


# ==================== Watchlist Cache Functions ====================

def get_watchlist_cache(service, status, limit=None, offset=0):
    """Get cached watchlist items with optional pagination"""
    with SQL(control.malSyncDB) as cursor:
        if limit:
            cursor.execute(
                'SELECT * FROM watchlist_cache WHERE service=? AND status=? ORDER BY id LIMIT ? OFFSET ?',
                (service, status, limit, offset)
            )
        else:
            cursor.execute(
                'SELECT * FROM watchlist_cache WHERE service=? AND status=? ORDER BY id',
                (service, status)
            )
        return cursor.fetchall()


def get_watchlist_cache_count(service, status):
    """Get total count of cached items for a service/status"""
    with SQL(control.malSyncDB) as cursor:
        cursor.execute(
            'SELECT COUNT(*) as count FROM watchlist_cache WHERE service=? AND status=?',
            (service, status)
        )
        result = cursor.fetchone()
        return result['count'] if result else 0


def get_watchlist_cache_last_updated(service, status):
    """Get the last updated timestamp for cached watchlist"""
    with SQL(control.malSyncDB) as cursor:
        cursor.execute(
            'SELECT MIN(last_updated) as last_updated FROM watchlist_cache WHERE service=? AND status=?',
            (service, status)
        )
        result = cursor.fetchone()
        return result['last_updated'] if result else None


def save_watchlist_cache(service, status, items):
    """Save watchlist items to cache (replaces existing cache for service/status)"""
    now = int(time.time())
    with SQL(control.malSyncDB) as cursor:
        # Clear existing cache for this service/status
        cursor.execute('DELETE FROM watchlist_cache WHERE service=? AND status=?', (service, status))
        # Insert new items with order index
        for idx, item in enumerate(items):
            mal_id = None
            # Extract mal_id based on service structure
            if service == 'simkl':
                mal_id = item.get('show', {}).get('ids', {}).get('mal')
            elif service == 'kitsu':
                mal_id = item.get('mal_id')  # Will be set during processing
            elif service == 'mal':
                mal_id = item.get('node', {}).get('id')
            elif service == 'anilist':
                mal_id = item.get('media', {}).get('idMal')

            data = pickle.dumps(item)
            cursor.execute(
                'INSERT INTO watchlist_cache (service, status, mal_id, item_order, data, last_updated) VALUES (?, ?, ?, ?, ?, ?)',
                (service, status, mal_id, idx, data, now)
            )
        cursor.connection.commit()


def clear_watchlist_cache(service=None, status=None):
    """Clear watchlist cache, optionally filtered by service and/or status"""
    with SQL(control.malSyncDB) as cursor:
        if service and status:
            cursor.execute('DELETE FROM watchlist_cache WHERE service=? AND status=?', (service, status))
        elif service:
            cursor.execute('DELETE FROM watchlist_cache WHERE service=?', (service,))
        else:
            cursor.execute('DELETE FROM watchlist_cache')
        cursor.connection.commit()


def is_watchlist_cache_valid(service, status, cache_hours=0.5):
    """Check if watchlist cache is still valid (default 30 minutes)"""
    last_updated = get_watchlist_cache_last_updated(service, status)
    if not last_updated:
        return False
    return is_cache_valid(last_updated, cache_hours)


# ==================== AniList Enrichment Cache Functions ====================

def get_all_watchlist_mal_ids():
    """Get all unique MAL IDs from the watchlist cache across all services."""
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('SELECT DISTINCT mal_id FROM watchlist_cache WHERE mal_id IS NOT NULL')
        rows = cursor.fetchall()
        mal_ids = []
        for row in rows:
            try:
                mal_ids.append(int(row['mal_id']))
            except (ValueError, TypeError):
                pass
        return mal_ids


def save_anilist_enrichment_batch(anilist_data_list):
    """Save a list of AniList media objects to the enrichment cache, keyed by idMal."""
    if not anilist_data_list:
        return
    now = int(time.time())
    with SQL(control.malSyncDB) as cursor:
        for item in anilist_data_list:
            mal_id = item.get('idMal')
            if not mal_id:
                continue
            data = pickle.dumps(item)
            cursor.execute(
                'REPLACE INTO anilist_enrichment (mal_id, data, last_updated) VALUES (?, ?, ?)',
                (int(mal_id), data, now)
            )
        cursor.connection.commit()


def get_anilist_enrichment_batch(mal_ids, max_age_hours=168):
    """
    Get cached AniList enrichment data for given MAL IDs.
    Returns dict {mal_id: anilist_data_dict}.
    Entries older than max_age_hours (default 7 days) are excluded.
    """
    if not mal_ids:
        return {}
    result = {}
    cutoff = int(time.time()) - (max_age_hours * 3600)
    with SQL(control.malSyncDB) as cursor:
        placeholders = ','.join('?' for _ in mal_ids)
        cursor.execute(
            f'SELECT * FROM anilist_enrichment WHERE mal_id IN ({placeholders}) AND last_updated > ?',
            [int(mid) for mid in mal_ids] + [cutoff]
        )
        rows = cursor.fetchall()
        for row in rows:
            try:
                result[row['mal_id']] = pickle.loads(row['data'])
            except Exception:
                pass
    return result


def clear_anilist_enrichment():
    """Clear all AniList enrichment cache."""
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('DELETE FROM anilist_enrichment')
        cursor.connection.commit()


def update_show(mal_id, kodi_meta, anime_schedule_route=''):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute('REPLACE INTO shows (mal_id, kodi_meta, anime_schedule_route) VALUES (?, ?, ?)', (mal_id, kodi_meta, anime_schedule_route))
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.connection.commit()


def update_show_meta(mal_id, meta_ids, art):
    meta_ids = pickle.dumps(meta_ids)
    art = pickle.dumps(art)
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute("REPLACE INTO shows_meta (mal_id, meta_ids, art) VALUES (?, ?, ?)", (mal_id, meta_ids, art))
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.connection.commit()


def add_mapping_id(mal_id, column, value):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('UPDATE shows SET %s=? WHERE mal_id=?' % column, (value, mal_id))
        cursor.connection.commit()


def update_kodi_meta(mal_id, kodi_meta):
    kodi_meta = pickle.dumps(kodi_meta)
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('UPDATE shows SET kodi_meta=? WHERE mal_id=?', (kodi_meta, mal_id))
        cursor.connection.commit()


def update_show_data(mal_id, data, last_updated=''):
    data = pickle.dumps(data)
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute("REPLACE INTO show_data (mal_id, data, last_updated) VALUES (?, ?, ?)", (mal_id, data, last_updated))
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.connection.commit()


def update_episode(mal_id, season, number, update_time, kodi_meta, filler='', anidb_ep_id=''):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('REPLACE INTO episodes (mal_id, season, kodi_meta, last_updated, number, filler, anidb_ep_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (mal_id, season, kodi_meta, update_time, number, filler, anidb_ep_id))
        cursor.connection.commit()


def update_episode_column(mal_id, episode, column, value):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('UPDATE episodes SET %s=? WHERE mal_id=? AND number=?' % column, (value, mal_id, episode))
        cursor.connection.commit()


def get_show_data(mal_id):
    with SQL(control.malSyncDB) as cursor:
        db_query = 'SELECT * FROM show_data WHERE mal_id IN (%s)' % mal_id
        cursor.execute(db_query)
        show_data = cursor.fetchone()
        return show_data


def get_episode_list(mal_id):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('SELECT * FROM episodes WHERE mal_id=?', (mal_id,))
        episodes = cursor.fetchall()
        return episodes


def get_episode(mal_id, episode=None):
    with SQL(control.malSyncDB) as cursor:
        if episode:
            cursor.execute('SELECT * FROM episodes WHERE mal_id=? AND number=?', (mal_id, episode))
        else:
            cursor.execute('SELECT * FROM episodes WHERE mal_id=?', (mal_id,))
        episode = cursor.fetchone()
        return episode


def get_show(mal_id):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('SELECT * FROM shows WHERE mal_id IN (%s)' % mal_id)
        shows = cursor.fetchone()
        return shows


def get_show_meta(mal_id):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute('SELECT * FROM shows_meta WHERE mal_id IN (%s)' % mal_id)
        shows = cursor.fetchone()
        return shows


def remove_from_database(table, mal_id):
    with SQL(control.malSyncDB) as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE mal_id=?", (mal_id,))
        cursor.connection.commit()


def get_info(api_name):
    with SQL(control.infoDB) as cursor:
        cursor.execute('SELECT * FROM info WHERE api_name=?', (api_name,))
        api_info = cursor.fetchone()
        return api_info


def get_mal_ids(anime_id, send_id):
    with SQL(control.mappingDB) as cursor:
        cursor.execute(f'SELECT * FROM anime WHERE {send_id}=?', (anime_id,))
        mappings = cursor.fetchall()
        return mappings if mappings else []


def get_mappings(anime_id, send_id):
    with SQL(control.mappingDB) as cursor:
        cursor.execute(f'SELECT * FROM anime WHERE {send_id}=?', (anime_id,))
        mappings = cursor.fetchall()
        return mappings[0] if mappings else {}


def get_unique_ids(anime_id, send_id):
    with SQL(control.mappingDB) as cursor:
        cursor.execute(f'SELECT mal_id, mal_dub_id, anilist_id, kitsu_id, anidb_id, simkl_id, thetvdb_id, themoviedb_id, imdb_id, trakt_id FROM anime WHERE {send_id}=?', (anime_id,))
        mappings = cursor.fetchone()
        if mappings:
            mappings_dict = {
                'mal_id': mappings.get('mal_id'),
                'mal_dub_id': mappings.get('mal_dub_id'),
                'anilist_id': mappings.get('anilist_id'),
                'kitsu_id': mappings.get('kitsu_id'),
                'anidb': mappings.get('anidb_id'),
                'simkl': mappings.get('simkl_id'),
                'tvdb': mappings.get('thetvdb_id'),
                'tmdb': mappings.get('themoviedb_id'),
                'imdb': mappings.get('imdb_id'),
                'trakt': mappings.get('trakt_id')
            }
            return mappings_dict
        return {}


def ensure_tables_and_indexes(cursor):
    tables = ['anime', 'movie', 'tv_show', 'tv_short', 'special', 'ova', 'ona', 'music']
    for table in tables:
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {table} (value TEXT)')
        cursor.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ix_history ON {table} (value)')


def getSearchHistory(media_type):
    with SQL(control.searchHistoryDB) as cursor:
        ensure_tables_and_indexes(cursor)
        cursor.execute(f"SELECT * FROM {media_type}")
        history = cursor.fetchall()
        history.reverse()
        history = history[:50]
        filter_ = []
        for i in history:
            if i['value'] not in filter_:
                filter_.append(i['value'])
        return filter_


def addSearchHistory(search_string, media_type):
    with SQL(control.searchHistoryDB) as cursor:
        ensure_tables_and_indexes(cursor)
        cursor.execute(f"REPLACE INTO {media_type} VALUES (?)", (search_string,))
        cursor.connection.commit()


def clearSearchHistory():
    confirmation = control.yesno_dialog(control.ADDON_NAME, "Clear all search history?")
    if not confirmation:
        return
    with SQL(control.searchHistoryDB) as cursor:
        tables = ['anime', 'movie', 'tv_show', 'tv_short', 'special', 'ova', 'ona', 'music']
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS {table}')
        cursor.execute("VACUUM")
        cursor.connection.commit()
        control.refresh()
        control.notify(control.ADDON_NAME, "Search History has been cleared", time=5000)


def clearSearchCatagory(media_type):
    confirmation = control.yesno_dialog(control.ADDON_NAME, "Clear search history?")
    if not confirmation:
        return
    with SQL(control.searchHistoryDB) as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS {media_type}')
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {media_type} (value TEXT)')
        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_history ON {media_type} (value)")
        cursor.connection.commit()
        control.refresh()
        control.notify(control.ADDON_NAME, "Search History has been cleared", time=5000)


def remove_search(table, value):
    norm_value = value.strip()
    with SQL(control.searchHistoryDB) as cursor:
        cursor.execute(f'DELETE FROM {table} WHERE value=?', (norm_value,))
        deleted = cursor.rowcount
        cursor.connection.commit()
        control.refresh()
        if deleted == 0:
            control.notify(control.ADDON_NAME, f"Search item not found: '{norm_value}'", time=3000)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class SQL:
    def __init__(self, path, timeout=60):
        self.lock = threading.Lock()
        self.path = path
        self.timeout = timeout

    def __enter__(self):
        self.lock.acquire()
        xbmcvfs.mkdir(control.dataPath)
        conn = dbapi2.connect(self.path, timeout=self.timeout)
        conn.row_factory = dict_factory
        conn.execute("PRAGMA FOREIGN_KEYS=1")
        self.cursor = conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        if self.lock.locked():
            self.lock.release()
        if exc_type:
            import traceback
            control.log('database error', level='error')
            control.log(f"{''.join(traceback.format_exception(exc_type, exc_val, exc_tb))}", level='error')
        if exc_type is OperationalError:
            import traceback
            control.log('database error', level='error')
            control.log(f"{''.join(traceback.format_exception(exc_type, exc_val, exc_tb))}", level='error')
            return True
