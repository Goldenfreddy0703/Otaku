"""
database_sync.py – Otaku Database Schema Manager
=================================================
Handles table creation and schema versioning.
Called from ``service.py`` on every addon startup.
"""

from resources.lib.ui import control

try:
    from sqlite3 import version as sqlite_version
except ImportError:
    from sqlite3 import sqlite_version  # noQA

from resources.lib.ui.database import SQL


class SyncDatabase:
    """Manages database schema creation and versioning.

    Instantiated once from ``service.py`` at startup.  Ensures every
    required table exists before the addon starts serving requests.
    """

    # Bump this whenever the metadata schema changes;
    # a mismatch triggers re_build_database(silent=True).
    SCHEMA_VERSION = '1.0.11'

    def __init__(self):
        self.activites = None

        # --- create every table the addon needs ---
        self._create_all_tables()

        # --- version check ---
        self.last_meta_update = self.SCHEMA_VERSION
        self.refresh_activites()
        self.check_database_version()

    # ─── Table Creation ──────────────────────────────────────────────

    def _create_all_tables(self):
        """Ensure every required table exists in malSyncDB."""
        self._build_activities()
        self._build_shows()
        self._build_shows_meta()
        self._build_episodes()
        self._build_show_data()
        self._build_watchlist_cache()
        self._build_watchlist_activity()
        self._build_anilist_enrichment()

    # --- individual table builders (static, idempotent) ---------------

    @staticmethod
    def _build_activities():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS activities '
                '(sync_id INTEGER PRIMARY KEY, '
                'otaku_version TEXT NOT NULL)')
            cur.connection.commit()

    @staticmethod
    def _build_shows():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS shows ('
                'mal_id INTEGER PRIMARY KEY, '
                'anilist_id INTEGER, '
                'simkl_id INTEGER, '
                'kitsu_id INTEGER, '
                'kodi_meta BLOB NOT NULL, '
                'anime_schedule_route TEXT NOT NULL, '
                'UNIQUE(mal_id))')
            cur.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_shows '
                'ON shows (mal_id ASC)')
            cur.connection.commit()

    @staticmethod
    def _build_shows_meta():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS shows_meta ('
                'mal_id INTEGER PRIMARY KEY, '
                'meta_ids BLOB, '
                'art BLOB, '
                'UNIQUE(mal_id))')
            cur.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_shows_meta '
                'ON shows_meta (mal_id ASC)')
            cur.connection.commit()

    @staticmethod
    def _build_episodes():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS episodes ('
                'mal_id INTEGER NOT NULL, '
                'season INTEGER NOT NULL, '
                'kodi_meta BLOB NOT NULL, '
                'last_updated TEXT NOT NULL, '
                'number INTEGER NOT NULL, '
                'filler TEXT, '
                'anidb_ep_id INTEGER, '
                'FOREIGN KEY(mal_id) REFERENCES shows(mal_id) '
                'ON DELETE CASCADE)')
            cur.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_episodes '
                'ON episodes (mal_id ASC, season ASC, number ASC)')
            cur.connection.commit()

    @staticmethod
    def _build_show_data():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS show_data ('
                'mal_id INTEGER PRIMARY KEY, '
                'data BLOB NOT NULL, '
                'last_updated TEXT NOT NULL, '
                'UNIQUE(mal_id))')
            cur.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_show_data '
                'ON show_data (mal_id ASC)')
            cur.connection.commit()

    @staticmethod
    def _build_watchlist_cache():
        with SQL(control.malSyncDB) as cur:
            # Migrate old table if item_order column is missing
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='watchlist_cache'")
            if cur.fetchone():
                cur.execute("PRAGMA table_info(watchlist_cache)")
                columns = [col['name'] for col in cur.fetchall()]
                if 'item_order' not in columns:
                    cur.execute('DROP TABLE watchlist_cache')

            cur.execute(
                'CREATE TABLE IF NOT EXISTS watchlist_cache ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                'service TEXT NOT NULL, '
                'status TEXT NOT NULL, '
                'mal_id INTEGER, '
                'item_order INTEGER NOT NULL, '
                'data BLOB NOT NULL, '
                'last_updated INTEGER NOT NULL, '
                'UNIQUE(service, status, item_order))')
            cur.execute(
                'CREATE INDEX IF NOT EXISTS idx_wl_service_status '
                'ON watchlist_cache(service, status)')
            cur.execute(
                'CREATE INDEX IF NOT EXISTS idx_wl_last_updated '
                'ON watchlist_cache(last_updated)')
            cur.connection.commit()

    @staticmethod
    def _build_watchlist_activity():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS watchlist_activity ('
                'service TEXT PRIMARY KEY, '
                'activity_timestamp TEXT NOT NULL, '
                'last_checked INTEGER NOT NULL)')
            cur.connection.commit()

    @staticmethod
    def _build_anilist_enrichment():
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS anilist_enrichment ('
                'mal_id INTEGER PRIMARY KEY, '
                'data BLOB NOT NULL, '
                'last_updated INTEGER NOT NULL)')
            cur.connection.commit()

    # ─── Activities & Version Management ─────────────────────────────

    def refresh_activites(self):
        with SQL(control.malSyncDB) as cur:
            cur.execute('SELECT * FROM activities WHERE sync_id=1')
            self.activites = cur.fetchone()

    def set_base_activites(self):
        with SQL(control.malSyncDB) as cur:
            cur.execute(
                'INSERT INTO activities(sync_id, otaku_version) VALUES(1, ?)',
                (self.last_meta_update,))
            cur.connection.commit()

    def check_database_version(self):
        if not self.activites or self.activites.get('otaku_version') != self.last_meta_update:
            first_time = control.getBool('first_time')

            if first_time:
                control.setInt('showchangelog', 1)
                choice = control.yesno_dialog(
                    f'{control.ADDON_NAME} - {control.lang(30415)}',
                    "Welcome to Otaku!!!\n"
                    "Would you like to go through the setup wizard?",
                    "No", "Yes")

                if choice == 1:
                    control.setBool('first_time', False)
                    control.execute(
                        'RunPlugin(plugin://plugin.video.otaku/setup_wizard)')
                elif choice == 0:
                    control.setBool('first_time', False)

            self.re_build_database(True)

            # Clear last_watched setting
            control.setSetting('addon.last_watched', '')

            # Update every menu configuration
            configs = [
                ('menu.mainmenu.config',
                 'last_watched', 'watch_history', 'next_up'),
                ('movie.mainmenu.config',
                 'last_watched_movie', 'watch_history_movie', 'next_up_movie'),
                ('tv_show.mainmenu.config',
                 'last_watched_tv_show', 'watch_history_tv_show', 'next_up_tv_show'),
                ('tv_short.mainmenu.config',
                 'last_watched_tv_short', 'watch_history_tv_short', 'next_up_tv_short'),
                ('special.mainmenu.config',
                 'last_watched_special', 'watch_history_special', 'next_up_special'),
                ('ova.mainmenu.config',
                 'last_watched_ova', 'watch_history_ova', 'next_up_ova'),
                ('ona.mainmenu.config',
                 'last_watched_ona', 'watch_history_ona', 'next_up_ona'),
                ('music.mainmenu.config',
                 'last_watched_music', 'watch_history_music', 'next_up_music'),
            ]
            for key, lw, wh, nu in configs:
                self._update_menu_config(key, lw, wh, nu)

    # ─── Menu Configuration Helpers ──────────────────────────────────

    @staticmethod
    def _update_menu_config(config_key, last_watched, watch_history, next_up):
        """Ensure last_watched, watch_history, and next_up exist in a menu."""
        menu = control.getStringList(config_key)
        if not menu:
            return

        # Process each item.  By the time we handle the second/third,
        # the previous items are guaranteed to be in the list.
        for item, insert_after in [
            (last_watched, None),
            (watch_history, last_watched),
            (next_up, watch_history),
        ]:
            if item not in menu:
                if insert_after and insert_after in menu:
                    menu.insert(menu.index(insert_after) + 1, item)
                else:
                    menu.insert(0, item)

        control.setStringList(config_key, menu)

    # ─── Database Rebuild ────────────────────────────────────────────

    def re_build_database(self, silent=False):
        import service

        if not silent:
            confirm = control.yesno_dialog(
                control.ADDON_NAME, control.lang(30088))
            if confirm == 0:
                return

        service.update_mappings_db()
        service.update_dub_json()

        with open(control.malSyncDB, 'w'):
            pass

        self._create_all_tables()
        self.set_base_activites()
        self.refresh_activites()

        if not silent:
            control.notify(
                f'{control.ADDON_NAME}: Database',
                'Metadata Database Successfully Cleared',
                sound=False)

    # ─── Legacy public aliases (kept for backward compat) ────────────

    def build_sync_activities(self):
        self._build_activities()

    def build_show_table(self):
        self._build_shows()

    def build_showmeta_table(self):
        self._build_shows_meta()

    def build_episode_table(self):
        self._build_episodes()

    def build_show_data_table(self):
        self._build_show_data()

    def build_watchlist_cache_table(self):
        self._build_watchlist_cache()

    def build_anilist_enrichment_table(self):
        self._build_anilist_enrichment()
