import pickle

from resources.lib.ui import control, database

# Lazy browser initialization for improved startup performance
_BROWSER_INSTANCE = None


def _get_browser():
    """Lazy-load browser instance on first access"""
    global _BROWSER_INSTANCE
    if _BROWSER_INSTANCE is None:
        if control.getStr('browser.api') == 'otaku':
            from resources.lib.OtakuBrowser import OtakuBrowser
            _BROWSER_INSTANCE = OtakuBrowser()
        elif control.getStr('browser.api') == 'mal':
            from resources.lib.MalBrowser import MalBrowser
            _BROWSER_INSTANCE = MalBrowser()
        else:
            from resources.lib.AniListBrowser import AniListBrowser
            _BROWSER_INSTANCE = AniListBrowser()
    return _BROWSER_INSTANCE


# Backwards compatibility: BROWSER property that lazily initializes
class _BrowserProxy:
    """Proxy that provides attribute access to the lazily-loaded browser"""
    def __getattribute__(self, name):
        return getattr(_get_browser(), name)

BROWSER = _BrowserProxy()


def get_anime_init(mal_id):
    # Lazy import indexers - only import what's actually needed
    show_meta = database.get_show_meta(mal_id)
    if not show_meta:
        BROWSER.get_anime(mal_id)
        show_meta = database.get_show_meta(mal_id)
        if not show_meta:
            return [], 'episodes'

    if control.getBool('override.meta.api'):
        # Import only the specified indexer when override is enabled
        meta_api = control.getSetting('meta.api')
        if meta_api == 'simkl':
            from resources.lib.indexers import simkl
            data = simkl.SIMKLAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'anizip':
            from resources.lib.indexers import anizip
            data = anizip.ANIZIPAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'jikanmoe':
            from resources.lib.indexers import jikanmoe
            data = jikanmoe.JikanAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'anidb':
            from resources.lib.indexers import anidb
            data = anidb.ANIDBAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'kitsu':
            from resources.lib.indexers import kitsu
            data = kitsu.KitsuAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'otaku':
            from resources.lib.indexers import otaku
            data = otaku.OtakuAPI().get_episodes(mal_id, show_meta)
        else:
            data = None
    else:
        # Fallback chain - import indexers one by one as needed
        from resources.lib.indexers import simkl
        data = simkl.SIMKLAPI().get_episodes(mal_id, show_meta)
        if not data:
            from resources.lib.indexers import anizip
            data = anizip.ANIZIPAPI().get_episodes(mal_id, show_meta)
        if not data:
            from resources.lib.indexers import jikanmoe
            data = jikanmoe.JikanAPI().get_episodes(mal_id, show_meta)
        if not data:
            from resources.lib.indexers import anidb
            data = anidb.ANIDBAPI().get_episodes(mal_id, show_meta)
        if not data:
            from resources.lib.indexers import kitsu
            data = kitsu.KitsuAPI().get_episodes(mal_id, show_meta)
        if not data:
            data = []
    return data, 'episodes'


def get_sources(mal_id, episode, media_type, rescrape=False, source_select=False, silent=False):
    from resources.lib import pages
    if not (show := database.get_show(mal_id)):
        show = BROWSER.get_anime(mal_id)
    kodi_meta = pickle.loads(show['kodi_meta'])
    actionArgs = {
        'query': kodi_meta['query'],
        'mal_id': mal_id,
        'episode': episode,
        'episodes': kodi_meta['episodes'],
        'status': kodi_meta['status'],
        'duration': kodi_meta['duration'],
        'media_type': media_type,
        'rescrape': rescrape,
        'source_select': source_select,
        'silent': silent
    }

    sources = pages.getSourcesHelper(actionArgs)
    return sources
