import ast
import hashlib
import pickle
import re
import time

from kodi_six import xbmcvfs
from resources.lib.ui import control

try:
    from sqlite3 import OperationalError
    from sqlite3 import dbapi2 as db
except ImportError:
    from pysqlite2 import OperationalError
    from pysqlite2 import dbapi2 as db

cache_table = 'cache'


def get(function, duration, *args, **kwargs):
    # type: (function, int, object) -> object or None
    """
    Gets cached value for provided function with optional arguments, or executes and stores the result
    :param function: Function to be executed
    :param duration: Duration of validity of cache in hours
    :param args: Optional arguments for the provided function
    """
    try:
        sources = False
        reload = False
        if 'otaku_reload' in kwargs:
            reload = kwargs['otaku_reload']
            kwargs.pop('otaku_reload')

        if 'animepahe_sources' in kwargs:
            sources = True
            kwargs.pop('otaku_sources')

        key = _hash_function(function, args, kwargs)
        cache_result = cache_get(key)
        if not reload:
            if cache_result:
                if _is_cache_valid(cache_result['date'], duration):
                    try:
                        return_data = ast.literal_eval(cache_result['value'])
                        return return_data
                    except:
                        return ast.literal_eval(cache_result['value'])

        fresh_result = repr(function(*args, **kwargs))

        if fresh_result is None or fresh_result == 'None':
            # If the cache is old, but we didn't get fresh result, return the old cache
            if cache_result:
                return cache_result
            return None

        data = ast.literal_eval(fresh_result)

        # Because I'm lazy, I've added this crap code so sources won't cache if there are no results
        if not sources:
            cache_insert(key, fresh_result)
        elif len(data[1]) > 0:
            cache_insert(key, fresh_result)
        else:
            return None

        return data

    except Exception:
        import traceback
        traceback.print_exc()
        return None


def remove(function, *args, **kwargs):
    # type: (function, object) -> object or None
    """
    Gets cached value for provided function with optional arguments, or executes and stores the result
    :param function: Function to be executed
    :param args: Optional arguments for the provided function
    """
    try:
        key = _hash_function(function, args, kwargs)
        cache_remove(key)
        return True

    except Exception:
        import traceback
        traceback.print_exc()
        return False


def _hash_function(function_instance, *args):
    return _get_function_name(function_instance) + _generate_md5(args)


def _get_function_name(function_instance):
    return re.sub(r'.+\smethod\s|.+function\s|\sat\s.+|\sof\s.+', '', repr(function_instance))


def _generate_md5(*args):
    md5_hash = hashlib.md5()
    try:
        [md5_hash.update(str(arg)) for arg in args]
    except:
        [md5_hash.update(str(arg).encode('utf-8')) for arg in args]
    return str(md5_hash.hexdigest())


def cache_get(key):
    try:
        control.cacheFile_lock.acquire()
        cursor = _get_connection_cursor(control.cacheFile)
        cursor.execute("SELECT * FROM %s WHERE key = ?" % cache_table, [key])
        results = cursor.fetchone()
        cursor.close()
        return results
    except OperationalError:
        return None
    finally:
        control.try_release_lock(control.cacheFile_lock)


def cache_insert(key, value):
    control.cacheFile_lock.acquire()
    try:
        cursor = _get_connection_cursor(control.cacheFile)
        now = int(time.time())
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS %s (key TEXT, value TEXT, date INTEGER, UNIQUE(key))"
            % cache_table
        )
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_%s ON %s (key)" % (cache_table, cache_table))
        cursor.execute("REPLACE INTO %s (key, value, date) VALUES (?, ?, ?)" % cache_table, (key, value, now))
        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        pass
    finally:
        control.try_release_lock(control.cacheFile_lock)


def cache_remove(key):
    control.cacheFile_lock.acquire()
    try:
        cursor = _get_connection_cursor(control.cacheFile)
        cursor.execute('''DELETE FROM %s WHERE key = "%s"''' % (cache_table, key))
        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        pass
    finally:
        control.try_release_lock(control.cacheFile_lock)


def cache_clear():
    try:
        control.cacheFile_lock.acquire()
        cursor = _get_connection_cursor(control.cacheFile)

        for t in [cache_table, 'rel_list', 'rel_lib']:
            try:
                cursor.execute("DROP TABLE IF EXISTS %s" % t)
                cursor.execute("VACUUM")
                cursor.connection.commit()
            except:
                pass
        control.showDialog.notification('{}: {}'.format(control.ADDON_NAME, control.lang(30200)), control.lang(30201), time=5000, sound=False)
    except:
        pass
    finally:
        control.try_release_lock(control.cacheFile_lock)


def _is_cache_valid(cached_time, cache_timeout):
    now = int(time.time())
    diff = now - cached_time
    return (cache_timeout * 3600) > diff


def makeFile(path):
    try:
        xbmcvfs.mkdir(path)
    except:
        try:
            file = open(path, 'a+')
            file.close()
        except:
            pass


def _get_connection_cursor(filepath):
    conn = _get_connection(filepath)
    return conn.cursor()


def _get_connection(filepath):
    makeFile(control.dataPath)
    conn = db.connect(filepath)
    conn.row_factory = _dict_factory
    return conn


def _get_db_connection():
    makeFile(control.dataPath)
    conn = db.connect(control.anilistSyncDB, timeout=60.0)
    conn.row_factory = _dict_factory
    return conn


def _get_cursor():
    conn = _get_db_connection()
    conn.execute("PRAGMA FOREIGN_KEYS = 1")
    cursor = conn.cursor()
    return cursor


def _build_lists_table():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    cursor.execute('CREATE TABLE IF NOT EXISTS shows ('
                   'mal_id INTEGER,'
                   'name TEXT NOT NULL, '
                   'image TEXT NOT NULL,'
                   'slug TEXT NOT NULL,'
                   'PRIMARY KEY (mal_id)) '
                   )
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_shows ON "shows" (mal_id ASC )')
    try:
        cursor.execute(
            "REPLACE INTO shows ("
            "mal_id, name, image, slug)"
            "VALUES "
            "(?, ?, ?, ?)",
            (1, 'ss', 'hhtp', 'dfd-sds'))
        cursor.connection.commit()
        cursor.close()
    except:
        cursor.close()

        import traceback
        traceback.print_exc()
        pass
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def build_tables():
    _build_episode_table()
    _build_season_table()
    _build_show_table()


def _build_show_table():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS shows '
                   '(anilist_id INTEGER PRIMARY KEY, '
                   'mal_id INTEGER,'
                   'simkl_id INTEGER,'
                   'kitsu_id INTEGER,'
                   'kodi_meta BLOB NOT NULL, '
                   'last_updated TEXT NOT NULL, '
                   'air_date TEXT, '
                   'UNIQUE(anilist_id))')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_shows ON "shows" (anilist_id ASC )')
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def _build_showmeta_table():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS shows_meta '
                   '(anilist_id INTEGER PRIMARY KEY, '
                   'meta_ids BLOB,'
                   'art BLOB, '
                   'UNIQUE(anilist_id))')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_shows_meta ON "shows_meta" (anilist_id ASC )')
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def _build_season_table():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS seasons ('
                   'anilist_id INTEGER NOT NULL, '
                   'season INTEGER NOT NULL, '
                   'kodi_meta BLOB NOT NULL, '
                   'air_date TEXT, '
                   'FOREIGN KEY(anilist_id) REFERENCES shows(anilist_id) ON DELETE CASCADE)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_season ON seasons (anilist_id ASC, season ASC)')
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def _build_episode_table():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS episodes ('
                   'anilist_id INTEGER NOT NULL, '
                   'season INTEGER NOT NULL, '
                   'kodi_meta BLOB NOT NULL, '
                   'last_updated TEXT NOT NULL, '
                   'number INTEGER NOT NULL, '
                   'number_abs INTEGER,'
                   'air_date TEXT, '
                   'FOREIGN KEY(anilist_id) REFERENCES shows(anilist_id) ON DELETE CASCADE)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_episodes ON episodes (anilist_id ASC, season ASC, number ASC)')
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def get_mapping(anilist_id='', mal_id='', kitsu_id='', tmdb_id=''):
    control.mappingDB_lock.acquire()
    conn = db.connect(control.mappingDB, timeout=60.0)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA FOREIGN_KEYS = 1")
    cursor = conn.cursor()
    mapping = {}
    id_type, id_val = '', ''
    if anilist_id:
        id_type, id_val = 'anilist_id', anilist_id
    elif mal_id:
        id_type, id_val = 'mal_id', mal_id
    elif kitsu_id:
        id_type, id_val = 'kitsu_id', kitsu_id
    elif tmdb_id:
        id_type, id_val = 'themoviedb_id', tmdb_id
    if id_type and id_val:
        db_query = 'SELECT * FROM anime WHERE {0} IN ({1})'.format(id_type, id_val)
        cursor.execute(db_query)
        mapping = cursor.fetchone()
        cursor.close()
    control.try_release_lock(control.mappingDB_lock)
    return mapping


def _update_show(anilist_id, mal_id, kodi_meta, last_updated=''):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(kodi_meta, dict):
        kodi_meta = pickle.dumps(kodi_meta)
    try:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute(
            "REPLACE INTO shows ("
            "anilist_id, mal_id, kodi_meta, last_updated, air_date)"
            "VALUES "
            "(?, ?, ?, ?, ?)",
            (anilist_id, mal_id, kodi_meta, last_updated, ''))
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.connection.commit()
        cursor.close()

    except:
        cursor.close()

        import traceback
        traceback.print_exc()
        pass
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def update_show_meta(anilist_id, meta_ids, art):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(meta_ids, dict):
        meta_ids = pickle.dumps(meta_ids)
    if isinstance(art, dict):
        art = pickle.dumps(art)
    try:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute(
            "REPLACE INTO shows_meta ("
            "anilist_id, meta_ids, art)"
            "VALUES "
            "(?, ?, ?)",
            (anilist_id, meta_ids, art))
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.connection.commit()
        cursor.close()

    except:
        cursor.close()
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def add_meta_ids(anilist_id, meta_ids):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(meta_ids, dict):
        meta_ids = pickle.dumps(meta_ids)
    cursor.execute('UPDATE shows_meta SET meta_ids=? WHERE anilist_id=?', (meta_ids, anilist_id))
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def add_mapping_id(anilist_id, column, value):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('UPDATE shows SET %s=? WHERE anilist_id=?' % column, (value, anilist_id))
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def add_fanart(anilist_id, kodi_meta):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(kodi_meta, dict):
        kodi_meta = pickle.dumps(kodi_meta)
    cursor.execute('UPDATE shows SET kodi_meta=? WHERE anilist_id=?', (kodi_meta, anilist_id))
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def update_kodi_meta(anilist_id, kodi_meta):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(kodi_meta, dict):
        kodi_meta = pickle.dumps(kodi_meta)
    cursor.execute('UPDATE shows SET kodi_meta=? WHERE anilist_id=?', (kodi_meta, anilist_id))
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def _update_season(show_id, season):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    try:
        cursor.execute(
            "REPLACE INTO seasons ("
            "anilist_id, season, kodi_meta, air_date)"
            "VALUES "
            "(?, ?, ?, ?)",
            (int(show_id), str(season), '', ''))
        cursor.connection.commit()
        cursor.close()

    except:
        cursor.close()
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def _update_episode(show_id, season=0, number=0, number_abs=0, update_time='', kodi_meta={}, air_date=''):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    if isinstance(kodi_meta, dict):
        kodi_meta = pickle.dumps(kodi_meta)
    try:
        cursor.execute(
            "REPLACE INTO episodes ("
            "anilist_id, season, kodi_meta, last_updated, number, number_abs, air_date)"
            "VALUES "
            "(?, ?, ?, ?, ?, ?, ?)",
            (show_id, season, kodi_meta, update_time, number, number_abs, air_date))
        cursor.connection.commit()
        cursor.close()

    except:
        cursor.close()
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def _get_show_list():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    cursor.execute('SELECT * FROM shows')
    shows = cursor.fetchall()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return shows


def get_season_list(show_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('SELECT* FROM seasons WHERE anilist_id = ?', (show_id,))
    seasons = cursor.fetchone()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return seasons


def get_episode_list(show_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    cursor.execute('SELECT* FROM episodes WHERE anilist_id = ?', (show_id,))
    episodes = cursor.fetchall()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return episodes


def get_show(anilist_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    db_query = 'SELECT * FROM shows WHERE anilist_id IN (%s)' % anilist_id
    try:
        cursor.execute(db_query)
    except OperationalError:
        pass  # Avoid missing DB error when executing unit tests
    shows = cursor.fetchone()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return shows


def get_show_meta(anilist_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    db_query = 'SELECT * FROM shows_meta WHERE anilist_id IN (%s)' % anilist_id
    try:
        cursor.execute(db_query)
    except OperationalError:
        pass  # Avoid missing DB error when executing unit tests
    shows = cursor.fetchone()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return shows


def get_show_mal(mal_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    db_query = 'SELECT * FROM shows WHERE mal_id IN (%s)' % mal_id
    cursor.execute(db_query)
    shows = cursor.fetchone()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)
    return shows


def mark_episode_unwatched_by_id():
    control.anilistSyncDB_lock.acquire()
    cursor = _get_connection_cursor(control.anilistSyncDB)
    cursor.execute('UPDATE shows SET trakt_id=? WHERE anilist_id=?', (69, 2))
    cursor.connection.commit()
    cursor.close()
    control.try_release_lock(control.anilistSyncDB_lock)


def remove_season(anilist_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    try:
        cursor.execute("DELETE FROM seasons WHERE anilist_id = ?", (anilist_id,))
        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def remove_episodes(anilist_id):
    control.anilistSyncDB_lock.acquire()
    cursor = _get_cursor()
    try:
        cursor.execute("DELETE FROM episodes WHERE anilist_id = ?", (anilist_id,))
        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.anilistSyncDB_lock)


def build_searchdb():
    control.searchHistoryDB_lock.acquire()
    cursor = _get_connection_cursor(control.searchHistoryDB)
    cursor.execute('CREATE TABLE IF NOT EXISTS show (value TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS movie (value TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS both (value TEXT)')
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_show ON show (value)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_movie ON movie (value)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_both ON both (value)")
    cursor.connection.commit()
    cursor.close()


def getSearchHistory(table):
    try:
        control.searchHistoryDB_lock.acquire()
        cursor = _get_connection_cursor(control.searchHistoryDB)
        cursor.execute("SELECT * FROM %s" % table)
        history = cursor.fetchall()
        cursor.close()
        history.reverse()
        history = history[:50]
        filter = []
        for i in history:
            if i['value'] not in filter:
                filter.append(i['value'])

        return filter
    except:
        try:
            cursor.close()
        except:
            pass
        return []
    finally:
        control.try_release_lock(control.searchHistoryDB_lock)


def addSearchHistory(table, search_string):
    try:
        control.searchHistoryDB_lock.acquire()
        cursor = _get_connection_cursor(control.searchHistoryDB)
        cursor.execute(
            "REPLACE INTO %s Values (?)"
            % table, (search_string,)
        )
        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        return []
    finally:
        control.try_release_lock(control.searchHistoryDB_lock)


def clearAllSearchHistory():
    try:
        control.searchHistoryDB_lock.acquire()
        confirmation = control.yesno_dialog(control.ADDON_NAME, "Clear search history?")
        if not confirmation:
            return

        # Clear search history database
        cursor = _get_connection_cursor(control.searchHistoryDB)
        cursor.execute("DROP TABLE IF EXISTS movie")
        cursor.execute("DROP TABLE IF EXISTS show")
        cursor.execute("DROP TABLE IF EXISTS both")
        try:
            cursor.execute("VACUUM")
        except:
            pass
        cursor.connection.commit()

        # initialise search history database
        cursor.execute('CREATE TABLE IF NOT EXISTS show (value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS movie (value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS both (value TEXT)')
        cursor.connection.commit()
        cursor.close()
        control.refresh()
        control.showDialog.notification(control.ADDON_NAME, "Search History has been cleared", time=5000)

    except:
        import traceback
        traceback.print_exc()
        return []

    finally:
        control.try_release_lock(control.searchHistoryDB_lock)


def clearSearchHistory(media_type):
    try:
        control.searchHistoryDB_lock.acquire()
        confirmation = control.yesno_dialog(control.ADDON_NAME, "Clear search history?")
        if not confirmation:
            return
        cursor = _get_connection_cursor(control.searchHistoryDB)
        cursor.execute("DROP TABLE IF EXISTS %s" % media_type)
        try:
            cursor.execute("VACCUM")
        except:
            pass
        cursor.connection.commit()
        cursor.execute('CREATE TABLE IF NOT EXISTS %s (value TEXT)' % media_type)
        cursor.connection.commit()
        cursor.close()
        control.refresh()
        control.showDialog.notification(control.ADDON_NAME, "Search History has been cleared", '', 5000, False)
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        return []
    finally:
        control.try_release_lock(control.searchHistoryDB_lock)


def remove_search(table, value):
    try:
        control.searchHistoryDB_lock.acquire()
        cursor = _get_connection_cursor(control.searchHistoryDB)
        cursor.execute('DELETE from {0} where value="{1}"'.format(table, value))
        cursor.connection.commit()
        cursor.close()
        control.refresh()
    except:
        try:
            cursor.close()
        except:
            pass
    finally:
        control.try_release_lock(control.searchHistoryDB_lock)


def getTorrentList(anilist_id):
    control.torrentScrapeCacheFile_lock.acquire()
    try:
        cursor = _get_connection_cursor(control.torrentScrapeCacheFile)
        _try_create_torrent_cache(cursor)
        cursor.execute("SELECT * FROM %s WHERE anilist_id=?" % cache_table, (anilist_id,))
        torrent_list = cursor.fetchone()
        zfill_int = None
        cursor.close()

        if torrent_list:
            zfill_int = torrent_list['zfill']
            torrent_list = pickle.loads(torrent_list['sources'])

        return [torrent_list, zfill_int]

    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        return []
    finally:
        control.try_release_lock(control.torrentScrapeCacheFile_lock)


def _try_create_torrent_cache(cursor):
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS %s ("
        "anilist_id INTEGER NOT NULL, "
        "sources BLOB, "
        "zfill INTEGER,"
        "UNIQUE(anilist_id))"
        % cache_table
    )
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_%s ON %s (anilist_id)" % (cache_table, cache_table))


def addTorrentList(anilist_id, torrent_list, zfill_int):
    try:
        control.torrentScrapeCacheFile_lock.acquire()
        cursor = _get_connection_cursor(control.torrentScrapeCacheFile)
        _try_create_torrent_cache(cursor)

        if isinstance(torrent_list, list):
            torrent_list = pickle.dumps(torrent_list)

        try:
            cursor.execute("REPLACE INTO %s (anilist_id, sources, zfill) "
                           "VALUES (?, ?, ?)" % cache_table,
                           (anilist_id, torrent_list, int(zfill_int)))
        except:
            import traceback
            traceback.print_exc()

        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        return []
    finally:
        control.try_release_lock(control.torrentScrapeCacheFile_lock)


def updateSlugs(anilist_id, sources):
    try:
        control.torrentScrapeCacheFile_lock.acquire()
        cursor = _get_connection_cursor(control.torrentScrapeCacheFile)
        _try_create_torrent_cache(cursor)

        try:
            cursor.execute('UPDATE cache SET sources=? WHERE anilist_id=?', (sources, anilist_id))
        except:
            import traceback
            traceback.print_exc()

        cursor.connection.commit()
        cursor.close()
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        return []
    finally:
        control.try_release_lock(control.torrentScrapeCacheFile_lock)


def torrent_cache_clear():
    # confirmation = control.yesno_dialog(control.ADDON_NAME, "Are you sure you wish to clear the cache?")
    # if not confirmation:
    #     return
    try:
        control.torrentScrapeCacheFile_lock.acquire()
        cursor = _get_connection_cursor(control.torrentScrapeCacheFile)
        for t in [cache_table, 'rel_list', 'rel_lib']:
            try:
                cursor.execute("DROP TABLE IF EXISTS %s" % t)
                cursor.execute("VACUUM")
                cursor.connection.commit()
            except:
                pass
    except:
        try:
            cursor.close()
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        control.try_release_lock(control.torrentScrapeCacheFile_lock)

    control.showDialog.notification('{}: {}'.format(control.ADDON_NAME, control.lang(30200)), control.lang(30202), time=5000, sound=False)


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
