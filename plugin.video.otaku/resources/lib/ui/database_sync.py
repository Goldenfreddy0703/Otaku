# -*- coding: utf-8 -*-
import os

from resources.lib.ui import control
from kodi_six import xbmcvfs

try:
    from sqlite3 import dbapi2 as db
except ImportError:
    from pysqlite2 import dbapi2 as db

database_path = control.anilistSyncDB


class AnilistSyncDatabase:
    def __init__(self):

        self.activites = {}

        self._build_show_table()
        self._build_showmeta_table()
        self._build_episode_table()
        self._build_sync_activities()
        self._build_season_table()

        # If you make changes to the required meta in any indexer that is cached in this database
        # You will need to update the below version number to match the new addon version
        # This will ensure that the metadata required for operations is available
        # You may also update this version number to force a rebuild of the database after updating Otaku
        self.last_meta_update = '0.2.3'

        control.anilistSyncDB_lock.acquire()

        self._refresh_activites()

        if self.activites is None:
            cursor = self._get_cursor()
            cursor.execute("DELETE FROM shows")
            cursor.execute("DELETE FROM seasons")
            cursor.execute("DELETE FROM episodes")
            cursor.connection.commit()

            self._set_base_activites()

            cursor.execute('SELECT * FROM activities WHERE sync_id=1')
            self.activites = cursor.fetchone()
            cursor.close()

        control.try_release_lock(control.anilistSyncDB_lock)

        if self.activites is not None:
            self._check_database_version()

    def _refresh_activites(self):
        cursor = self._get_cursor()
        cursor.execute('SELECT * FROM activities WHERE sync_id=1')
        self.activites = cursor.fetchone()
        cursor.close()

    def _set_base_activites(self):
        cursor = self._get_cursor()
        cursor.execute('INSERT INTO activities(sync_id, otaku_version)'
                       'VALUES(1, ?)',
                       (self.last_meta_update,))

        cursor.connection.commit()
        self.activites = cursor.fetchone()
        cursor.close()

    def _check_database_version(self):
        # Migrate from an old version before database migrations
        if 'otaku_version' not in self.activites:
            # control.log('Upgrading Trakt Sync Database Version')
            self.clear_all_meta()
            control.anilistSyncDB_lock.acquire()
            cursor = self._get_cursor()
            cursor.execute('ALTER TABLE activities ADD COLUMN otaku_version TEXT')
            cursor.execute('UPDATE activities SET otaku_version = ?', (self.last_meta_update,))
            cursor.connection.commit()
            cursor.close()
            control.try_release_lock(control.anilistSyncDB_lock)

        if self.check_version_numbers(self.activites['otaku_version'], self.last_meta_update):
            # control.log('Rebuilding Trakt Sync Database Version')
            self.re_build_database(True)
            return

    def check_version_numbers(self, current, new):
        # Compares version numbers and return True if new version is newer
        current = current.split('.')
        new = new.split('.')
        step = 0
        for i in current:
            if int(new[step]) > int(i):
                return True
            if int(i) == int(new[step]):
                step += 1
                continue

        return False

    def clear_all_meta(self):
        path = control.anilistSyncDB
        xbmcvfs.delete(path)
        file = open(path, 'a+')
        file.close()

        self._build_show_table()
        self._build_showmeta_table()
        self._build_episode_table()
        self._build_sync_activities()
        self._build_season_table()

    def _build_show_table(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
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

    def _build_showmeta_table(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS shows_meta '
                       '(anilist_id INTEGER PRIMARY KEY, '
                       'meta_ids BLOB,'
                       'art BLOB, '
                       'UNIQUE(anilist_id))')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_shows_meta ON "shows_meta" (anilist_id ASC )')
        cursor.connection.commit()
        cursor.close()
        control.try_release_lock(control.anilistSyncDB_lock)

    def _build_season_table(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
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

    def _build_episode_table(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
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

    def _build_sync_activities(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS activities ('
                       'sync_id INTEGER PRIMARY KEY, '
                       'otaku_version TEXT NOT NULL) '
                       )
        cursor.connection.commit()
        cursor.close()
        control.try_release_lock(control.anilistSyncDB_lock)

    def _build_lists_table(self):
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS lists ('
                       'trakt_id INTEGER NOT NULL, '
                       'media_type TEXT NOT NULL,'
                       'name TEXT NOT NULL, '
                       'username TEXT NOT NULL, '
                       'kodi_meta BLOB NOT NULL, '
                       'updated_at TEXT NOT NULL,'
                       'list_type TEXT NOT NULL,'
                       'item_count INT NOT NULL,'
                       'sort_by TEXT NOT NULL,'
                       'sort_how TEXT NOT NULL,'
                       'slug TEXT NOT NULL,'
                       'PRIMARY KEY (trakt_id, media_type)) '
                       )

        cursor.connection.commit()
        cursor.close()
        control.try_release_lock(control.anilistSyncDB_lock)

    def _get_cursor(self):
        conn = _get_connection()
        conn.execute("PRAGMA FOREIGN_KEYS = 1")
        cursor = conn.cursor()
        return cursor

    def flush_activities(self, clear_meta=False):
        if clear_meta:
            self.clear_all_meta()
        control.anilistSyncDB_lock.acquire()
        cursor = self._get_cursor()
        cursor.execute('DROP TABLE activities')
        cursor.connection.commit()
        cursor.close()
        control.try_release_lock(control.anilistSyncDB_lock)

    def re_build_database(self, silent=False):
        if not silent:
            confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30203))
            if confirm == 0:
                return

        path = control.anilistSyncDB
        xbmcvfs.delete(path)
        file = open(path, 'a+')
        file.close()

        self._build_show_table()
        self._build_showmeta_table()
        self._build_episode_table()
        self._build_sync_activities()
        self._build_season_table()

        self._set_base_activites()
        self._refresh_activites()

        # from resources.lib.modules.trakt_sync import activities
        # sync_errors = activities.TraktSyncDatabase().sync_activities(silent)

        # if sync_errors:
        #     control.showDialog.notification(control.addonName + ': Trakt', control.lang(40353), time=5000)
        # elif sync_errors is None:
        #     self._refresh_activites()
        #     return
        # else:
        #     control.showDialog.notification(control.addonName + ': Trakt', control.lang(40262), time=5000)

        control.showDialog.notification('{}: {}'.format(control.ADDON_NAME, control.lang(30204)), control.lang(30205), time=5000, sound=False)


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def makeFile(path):
    try:
        xbmcvfs.mkdir(path)
    except:
        try:
            file = open(path, 'a+')
            file.close()
        except:
            pass


def _get_connection():
    makeFile(control.dataPath)
    conn = db.connect(database_path, timeout=60.0)
    conn.row_factory = _dict_factory
    return conn
