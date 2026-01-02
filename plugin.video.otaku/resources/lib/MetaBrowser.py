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


# Lazy-loaded Next Up API instance
_NEXT_UP_API = None


def _get_next_up_api():
    """Lazy-load Next Up API instance"""
    global _NEXT_UP_API
    if _NEXT_UP_API is None:
        from resources.lib.indexers import otaku_next_up
        _NEXT_UP_API = otaku_next_up.Otaku_Next_Up_API()
    return _NEXT_UP_API


def get_next_up_meta(mal_id, episode_num):
    """
    Fetch episode metadata for Next Up feature.
    Used by all watchlist flavors for consistent episode metadata.
    
    Args:
        mal_id: MyAnimeList ID
        episode_num: Episode number to fetch metadata for
        
    Returns:
        dict with: title, image, plot, aired, rating
    """
    next_up_api = _get_next_up_api()
    
    episode_meta = {
        'title': None,
        'image': None,
        'plot': None,
        'aired': None,
        'rating': None
    }

    # First try database cache
    episodes = database.get_episode_list(mal_id)
    if episodes:
        try:
            # Episodes are 1-indexed, list is 0-indexed
            ep_data = episodes[episode_num - 1] if episode_num <= len(episodes) else None
            if ep_data:
                kodi_meta = pickle.loads(ep_data.get('kodi_meta', b''))
                if kodi_meta:
                    info = kodi_meta.get('info', {})
                    image = kodi_meta.get('image', {})
                    episode_meta['title'] = info.get('title')
                    episode_meta['plot'] = info.get('plot')
                    episode_meta['aired'] = info.get('aired')
                    episode_meta['image'] = image.get('thumb') or image.get('icon')
                    if info.get('rating'):
                        episode_meta['rating'] = info['rating'].get('score')
                    
                    # If we have good data, return early
                    if episode_meta['title'] and episode_meta['title'] != f'Episode {episode_num}':
                        return episode_meta
        except (IndexError, TypeError, KeyError) as e:
            control.log(f"Episode cache lookup failed for {mal_id} ep {episode_num}: {str(e)}")

    # Fetch from APIs if cache miss or incomplete
    try:
        # Try Simkl first (best quality metadata)
        simkl_eps = next_up_api.get_simkl_episode_meta(mal_id)
        if simkl_eps:
            for ep in simkl_eps:
                if ep.get('type') == 'episode' and str(ep.get('episode')) == str(episode_num):
                    if not episode_meta['title']:
                        episode_meta['title'] = ep.get('title')
                    if not episode_meta['plot']:
                        episode_meta['plot'] = ep.get('description')
                    if not episode_meta['aired']:
                        episode_meta['aired'] = ep.get('date', '')[:10] if ep.get('date') else None
                    if ep.get('img') and not episode_meta['image']:
                        episode_meta['image'] = next_up_api.simklImagePath % ep['img']
                    break
    except Exception as e:
        control.log(f"Simkl episode meta fetch failed: {str(e)}")

    # Try AniZip as fallback
    if not episode_meta['title']:
        try:
            anizip_eps = next_up_api.get_anizip_episode_meta(mal_id)
            if anizip_eps:
                for ep in anizip_eps:
                    if str(ep.get('episode')) == str(episode_num):
                        if not episode_meta['title'] and ep.get('title'):
                            episode_meta['title'] = ep['title'].get('en') or ep['title'].get('x-jat')
                        if not episode_meta['plot']:
                            episode_meta['plot'] = ep.get('overview')
                        if not episode_meta['aired']:
                            episode_meta['aired'] = ep.get('airDate', '')[:10] if ep.get('airDate') else None
                        if not episode_meta['image']:
                            episode_meta['image'] = ep.get('image')
                        break
        except Exception as e:
            control.log(f"AniZip episode meta fetch failed: {str(e)}")

    # Final fallback
    if not episode_meta['title']:
        episode_meta['title'] = f'Episode {episode_num}'

    return episode_meta
