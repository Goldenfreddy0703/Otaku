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


def _refresh_localized_show_meta(mal_id):
    """
    Refresh localized title/plot in show's kodi_meta using TMDB/TVDB fallback.
    This keeps UI pages that rely on cached kodi_meta in sync with localized metadata.
    """
    show = database.get_show(mal_id)
    if not show or not show.get('kodi_meta'):
        return

    try:
        kodi_meta = pickle.loads(show.get('kodi_meta'))
    except Exception:
        return

    current_title = kodi_meta.get('title_userPreferred') or kodi_meta.get('name')
    current_plot = kodi_meta.get('plot')
    meta_ids = database.get_unique_ids(mal_id, 'mal_id') or {}
    if not meta_ids:
        return

    localized_title = current_title
    localized_plot = current_plot

    try:
        from resources.lib.endpoints import tmdb
        localized_tmdb = database.get(
            tmdb.get_show_localized_meta,
            168,
            meta_ids,
            key=f'tmdb_show_locale_v1_{mal_id}'
        )
    except Exception:
        localized_tmdb = {}

    if isinstance(localized_tmdb, dict):
        if localized_tmdb.get('plot'):
            localized_plot = localized_tmdb.get('plot')

    if not localized_plot:
        try:
            from resources.lib.endpoints import tvdb
            localized_tvdb = database.get(
                tvdb.get_show_localized_meta,
                168,
                meta_ids,
                key=f'tvdb_show_locale_v1_{mal_id}'
            )
        except Exception:
            localized_tvdb = {}

        if isinstance(localized_tvdb, dict):
            if not localized_plot and localized_tvdb.get('plot'):
                localized_plot = localized_tvdb.get('plot')

    changed = False
    if localized_plot and localized_plot != kodi_meta.get('plot'):
        kodi_meta['plot'] = localized_plot
        changed = True

    if changed:
        database.update_kodi_meta(mal_id, kodi_meta)


def get_anime_init(mal_id):
    # Lazy import indexers - only import what's actually needed
    show_meta = database.get_show_meta(mal_id)
    if not show_meta:
        BROWSER.get_anime(mal_id)
        show_meta = database.get_show_meta(mal_id)
        if not show_meta:
            return [], 'episodes'

    # Ensure cached show metadata is localized for UI screens that read from kodi_meta
    _refresh_localized_show_meta(mal_id)

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

    # Try TMDB localized metadata (e.g. Italian) to improve title/plot language
    try:
        from resources.lib.ui import utils
        from resources.lib.endpoints import tmdb

        meta_ids = database.get_unique_ids(mal_id, 'mal_id') or {}
        if meta_ids:
            show = database.get_show(mal_id) or {}
            kodi_meta = {}
            if show.get('kodi_meta'):
                try:
                    kodi_meta = pickle.loads(show['kodi_meta'])
                except Exception:
                    kodi_meta = {}

            title_candidates = [
                kodi_meta.get('title_userPreferred'),
                kodi_meta.get('tvshowtitle'),
                kodi_meta.get('name')
            ]
            title_candidates = [x for x in title_candidates if x]
            season_num = utils.get_season(title_candidates, mal_id) if title_candidates else 1

            localized = database.get(
                tmdb.get_episode_localized_meta,
                168,
                meta_ids,
                int(season_num),
                int(episode_num),
                key=f'tmdb_ep_locale_v2_{mal_id}_{season_num}_{episode_num}'
            )

            if isinstance(localized, dict):
                if localized.get('title'):
                    episode_meta['title'] = localized.get('title')
                if localized.get('plot'):
                    episode_meta['plot'] = localized.get('plot')
            if not (isinstance(localized, dict) and (localized.get('title') or localized.get('plot'))):
                from resources.lib.endpoints import tvdb
                localized_tvdb = database.get(
                    tvdb.get_episode_localized_meta,
                    168,
                    meta_ids,
                    int(season_num),
                    int(episode_num),
                    key=f'tvdb_ep_locale_v1_{mal_id}_{season_num}_{episode_num}'
                )
                if isinstance(localized_tvdb, dict):
                    if localized_tvdb.get('title'):
                        episode_meta['title'] = localized_tvdb.get('title')
                    if localized_tvdb.get('plot'):
                        episode_meta['plot'] = localized_tvdb.get('plot')
    except Exception as e:
        control.log(f"TMDB localized episode meta fetch failed: {str(e)}")

    # Final fallback
    if not episode_meta['title']:
        episode_meta['title'] = f'Episode {episode_num}'

    return episode_meta
