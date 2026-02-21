import concurrent.futures
import random

from resources.lib.endpoints import fanart, tmdb, tvdb
from resources.lib.ui import database, control


def collect_meta(anime_list):
    # Prepare list of anime that need metadata
    anime_to_fetch = []

    for anime in anime_list:
        if 'media' in anime.keys():
            anime = anime.get('media')

        if 'entry' in anime.keys():
            anime = anime.get('entry')

        mal_id = anime.get('idMal') or anime.get('mal_id')

        if not mal_id:
            continue

        if not database.get_show_meta(mal_id):
            if (anime.get('format') or anime.get('type')) in ['MOVIE', 'ONA', 'OVA', 'SPECIAL', 'Movie', 'Special'] and anime.get('episodes') == 1:
                mtype = 'movies'
            else:
                mtype = 'tv'
            anime_to_fetch.append((mal_id, mtype))

    # Fetch metadata in parallel with controlled thread pool (max 8 workers)
    if anime_to_fetch:
        # Fetch AniList banners in batch if enabled
        banner_map = {}
        if control.getBool('artwork.banner'):
            mal_ids = [mal_id for mal_id, _ in anime_to_fetch]
            from resources.lib.endpoints.anilist import Anilist
            anilist = Anilist()
            banner_map = anilist.get_banners_batch(mal_ids)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(update_meta, mal_id, mtype, banner_map.get(mal_id)) for mal_id, mtype in anime_to_fetch]
            # Wait for all to complete
            concurrent.futures.wait(futures)


def update_meta(mal_id, mtype='tv', anilist_banner=None):
    """
    Fetch and combine artwork from all providers (Fanart.tv, TMDB, TVDB)
    Respects artwork settings for provider preference and limits

    Args:
        mal_id: MyAnimeList ID
        mtype: Media type ('tv' or 'movies')
        anilist_banner: AniList banner URL (from batch fetch) or None
    """
    meta_ids = database.get_mappings(mal_id, 'mal_id')

    # Read artwork settings
    artwork_preference = control.getInt('artwork.preference')  # 0=Fanart-TV, 1=TMDb, 2=TVDB, 3=All
    artwork_fanart_count = control.getInt('artwork.fanart.count')
    artwork_fanart_enabled = control.getBool('artwork.fanart')
    artwork_clearlogo_enabled = control.getBool('artwork.clearlogo')
    artwork_clearart_enabled = control.getBool('artwork.clearart')
    artwork_banner_enabled = control.getBool('artwork.banner')
    artwork_landscape_enabled = control.getBool('artwork.landscape')

    # Fetch AniList banner individually if not provided from batch and banner is enabled
    if artwork_banner_enabled and not anilist_banner:
        from resources.lib.endpoints.anilist import Anilist
        anilist = Anilist()
        anilist_banner = anilist.get_banner(mal_id)

    # Check if ANY artwork is enabled - if all disabled, return empty
    if not (artwork_fanart_enabled or artwork_banner_enabled or artwork_landscape_enabled or artwork_clearlogo_enabled or artwork_clearart_enabled):
        database.update_show_meta(mal_id, meta_ids, {})
        return

    # Scrape art from providers based on preference (only if fanart is enabled)
    def fetch_fanart():
        try:
            return fanart.getArt(meta_ids, mtype, limit=artwork_fanart_count)
        except Exception as e:
            control.log(f"Fanart.tv fetch failed: {str(e)}")
            return {}

    def fetch_tmdb():
        try:
            return tmdb.getArt(meta_ids, mtype, limit=artwork_fanart_count)
        except Exception as e:
            control.log(f"TMDB fetch failed: {str(e)}")
            return {}

    def fetch_tvdb():
        try:
            return tvdb.getArt(meta_ids, mtype, limit=artwork_fanart_count)
        except Exception as e:
            control.log(f"TVDB fetch failed: {str(e)}")
            return {}

    # Determine which providers to fetch from based on preference
    fanart_art = {}
    tmdb_art = {}
    tvdb_art = {}

    if artwork_preference == 0:  # Fanart-TV only
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            fanart_future = executor.submit(fetch_fanart)
            fanart_art = fanart_future.result()
    elif artwork_preference == 1:  # TMDb only
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            tmdb_future = executor.submit(fetch_tmdb)
            tmdb_art = tmdb_future.result()
    elif artwork_preference == 2:  # TVDB only
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            tvdb_future = executor.submit(fetch_tvdb)
            tvdb_art = tvdb_future.result()
    else:  # All providers (3 or default)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fanart_future = executor.submit(fetch_fanart)
            tmdb_future = executor.submit(fetch_tmdb)
            tvdb_future = executor.submit(fetch_tvdb)

            # Wait for all to complete
            concurrent.futures.wait([fanart_future, tmdb_future, tvdb_future])

            fanart_art = fanart_future.result()
            tmdb_art = tmdb_future.result()
            tvdb_art = tvdb_future.result()

    # Combine art from providers with settings applied
    combined_art = merge_artwork(
        fanart_art, tmdb_art, tvdb_art,
        fanart_limit=artwork_fanart_count,
        clearlogo_enabled=artwork_clearlogo_enabled,
        clearart_enabled=artwork_clearart_enabled,
        banner_enabled=artwork_banner_enabled,
        landscape_enabled=artwork_landscape_enabled,
        anilist_banner=anilist_banner
    )

    # Title-based artwork search fallback when ID lookups produced no useful artwork
    if not combined_art.get('fanart') and not combined_art.get('thumb') and control.getBool('artwork.titlesearch'):
        title = meta_ids.get('mal_title')
        if not title:
            # Fallback: try title from show's kodi_meta
            show = database.get_show(mal_id)
            if show and show.get('kodi_meta'):
                try:
                    import pickle
                    km = pickle.loads(show['kodi_meta'])
                    title = km.get('title_userPreferred') or km.get('title_english') or km.get('title_romaji')
                except Exception:
                    pass
        if title:
            control.log(f"Artwork: ID lookup returned no art for mal_id={mal_id}, trying title search: '{title}'")
            discovered = False
            if not meta_ids.get('themoviedb_id'):
                try:
                    found_id = tmdb.searchByTitle(title, mtype)
                    if found_id:
                        meta_ids['themoviedb_id'] = found_id
                        discovered = True
                        control.log(f"Artwork: Discovered TMDB ID {found_id} via title search")
                except Exception as e:
                    control.log(f"Artwork: TMDB title search error: {e}")
            if not meta_ids.get('thetvdb_id'):
                try:
                    found_id = tvdb.searchByTitle(title, mtype)
                    if found_id:
                        meta_ids['thetvdb_id'] = found_id
                        discovered = True
                        control.log(f"Artwork: Discovered TVDB ID {found_id} via title search")
                except Exception as e:
                    control.log(f"Artwork: TVDB title search error: {e}")
            if discovered:
                # Re-fetch artwork with newly discovered IDs (closures see updated meta_ids)
                f_art, t_art, tv_art = {}, {}, {}
                if artwork_preference == 0:
                    f_art = fetch_fanart()
                elif artwork_preference == 1:
                    t_art = fetch_tmdb()
                elif artwork_preference == 2:
                    tv_art = fetch_tvdb()
                else:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        f1 = executor.submit(fetch_fanart)
                        f2 = executor.submit(fetch_tmdb)
                        f3 = executor.submit(fetch_tvdb)
                        concurrent.futures.wait([f1, f2, f3])
                        f_art = f1.result()
                        t_art = f2.result()
                        tv_art = f3.result()
                combined_art = merge_artwork(
                    f_art, t_art, tv_art,
                    fanart_limit=artwork_fanart_count,
                    clearlogo_enabled=artwork_clearlogo_enabled,
                    clearart_enabled=artwork_clearart_enabled,
                    banner_enabled=artwork_banner_enabled,
                    landscape_enabled=artwork_landscape_enabled,
                    anilist_banner=anilist_banner
                )

    database.update_show_meta(mal_id, meta_ids, combined_art)


def merge_artwork(fanart_art, tmdb_art, tvdb_art, fanart_limit=1,
                  clearlogo_enabled=True, clearart_enabled=True, banner_enabled=True, landscape_enabled=True, anilist_banner=None):
    """
    Merge artwork from multiple providers, combining lists and preferring quality sources.
    Applies limits and respects enable/disable settings.
    Pre-selects single items for clearart/clearlogo/landscape/banner to optimize performance.

    Args:
        fanart_art: Artwork from Fanart-TV
        tmdb_art: Artwork from TMDb
        tvdb_art: Artwork from TVDB
        fanart_limit: Maximum number of fanart images to keep
        clearlogo_enabled: Whether to include clearlogo
        clearart_enabled: Whether to include clearart
        banner_enabled: Whether to include banner
        landscape_enabled: Whether to include landscape/thumb
        anilist_banner: AniList banner URL (prioritized over provider banners)
    """
    merged = {}

    # Merge fanart (backgrounds) and apply limit
    fanart_images = []
    fanart_images.extend(fanart_art.get('fanart', []))
    fanart_images.extend(tmdb_art.get('fanart', []))
    fanart_images.extend(tvdb_art.get('fanart', []))
    if fanart_images:
        merged['fanart'] = fanart_images[:fanart_limit]  # Apply limit

    # Merge thumbs/landscape if enabled - always limit to 1 (users only need one thumbnail)
    if landscape_enabled:
        thumb_images = []
        thumb_images.extend(fanart_art.get('thumb', []))
        thumb_images.extend(tmdb_art.get('thumb', []))
        thumb_images.extend(tvdb_art.get('thumb', []))
        if thumb_images:
            merged['thumb'] = thumb_images[:1]  # Always use first/best thumbnail

    # Merge clearart if enabled - pre-select single item for performance
    if clearart_enabled:
        clearart_images = []
        clearart_images.extend(fanart_art.get('clearart', []))
        clearart_images.extend(tmdb_art.get('clearart', []))
        clearart_images.extend(tvdb_art.get('clearart', []))
        if clearart_images:
            # Pre-select one random clearart and store as single string
            merged['clearart'] = random.choice(clearart_images)

    # Merge clearlogo with language preference - pre-select single item
    if clearlogo_enabled:
        clearlogo_images = []
        clearlogo_images.extend(fanart_art.get('clearlogo', []))
        clearlogo_images.extend(tmdb_art.get('clearlogo', []))
        clearlogo_images.extend(tvdb_art.get('clearlogo', []))
        if clearlogo_images:
            # Remove duplicates while preserving order
            seen = set()
            unique_logos = []
            for logo in clearlogo_images:
                if logo not in seen:
                    seen.add(logo)
                    unique_logos.append(logo)
            # Pre-select one random clearlogo and store as single string
            merged['clearlogo'] = random.choice(unique_logos)

    # Merge banner if enabled - prioritize AniList banner (highest quality, official)
    if banner_enabled:
        if anilist_banner:
            # Use AniList banner if available (highest priority)
            merged['banner'] = anilist_banner
        else:
            # Fallback to artwork provider banners if AniList banner not available
            banner_images = []
            banner_images.extend(fanart_art.get('banner', []))
            banner_images.extend(tmdb_art.get('banner', []))
            banner_images.extend(tvdb_art.get('banner', []))
            if banner_images:
                # Pre-select one random banner from providers
                merged['banner'] = random.choice(banner_images)

    return merged
