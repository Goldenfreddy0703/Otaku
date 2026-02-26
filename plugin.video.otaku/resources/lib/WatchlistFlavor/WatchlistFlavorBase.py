import pickle
import random

from resources.lib.ui import control, client, database, utils


class WatchlistFlavorBase:
    _URL = None
    _TITLE = None
    _NAME = None
    _IMAGE = None

    def __init__(self, auth_var=None, username=None, password=None, user_id=None, token=None, refresh=None, sort=None, order=None):
        self.auth_var = auth_var
        self.username = username
        self.password = password
        self.user_id = user_id
        self.token = token
        self.refresh = refresh
        self.sort = sort
        self.order = order
        self.title_lang = ["romaji", 'english'][control.getInt("titlelanguage")]

    @classmethod
    def name(cls):
        return cls._NAME

    @property
    def flavor_name(self):
        return self._NAME

    @property
    def url(self):
        return self._URL

    @property
    def title(self):
        return self._TITLE

    @property
    def image(self):
        return self._IMAGE

    @staticmethod
    def login():
        raise NotImplementedError('Should Not be called Directly')

    @staticmethod
    def get_watchlist_status(status, next_up, offset, page, cache_only=False):
        raise NotImplementedError('Should Not be called Directly')

    @staticmethod
    def watchlist():
        raise NotImplementedError('Should Not be called Directly')

    def _should_refresh_cache(self):
        """Check the API's activity endpoint to see if the watchlist has changed remotely.
        Uses rate-limiting (2 min) so we don't hit the API on every page navigation.
        Returns True if the cache was invalidated (data changed remotely)."""
        from resources.lib.ui.database import (
            get_watchlist_activity, save_watchlist_activity,
            clear_watchlist_cache, is_cache_valid
        )

        # Rate limit: only check the activity API every 2 minutes
        stored = get_watchlist_activity(self._NAME)
        if stored and is_cache_valid(stored['last_checked'], 0.033):  # 0.033 hours ~ 2 minutes
            return False  # Recently checked, trust current cache

        try:
            remote_timestamp = self.get_last_activity_timestamp()
        except Exception:
            # On error (network issue, etc.), don't invalidate — serve stale cache
            return False

        if not remote_timestamp:
            return False

        if stored and str(stored['activity_timestamp']) == str(remote_timestamp):
            # Activity hasn't changed since last check, just update the check time
            save_watchlist_activity(self._NAME, remote_timestamp)
            return False

        # Activity changed! Clear all watchlist caches for this service and save new timestamp
        control.log(f"[{self._NAME}] Watchlist activity changed remotely, refreshing cache", level='info')
        clear_watchlist_cache(self._NAME)
        save_watchlist_activity(self._NAME, remote_timestamp)
        return True

    def get_last_activity_timestamp(self):
        """Override in subclass to return a timestamp/hash from a lightweight API call.
        Used to detect remote changes without re-fetching the full watchlist.
        Should return a string that changes whenever the user's anime list is modified."""
        return None

    def build_next_up_item(self, data):
        """
        Shared Next Up episode item builder used by all watchlist flavors.

        Args:
            data: dict with keys:
                - mal_id (str/int or None)
                - anilist_id (str/int or None)
                - kitsu_id (str/int or None, optional)
                - progress (int): episodes watched
                - show_title (str): show name
                - total_eps (int): total episodes (0 = unknown/ongoing)
                - poster (str or None): poster URL
                - is_movie (bool): whether this is a movie
                - next_airing_episode (int or None): AniList's next airing ep number
                - average_score (float or None): 0-10 scale
                - duration (int or None): episode duration in seconds
                - genres (list or None)
                - studios (list or None): list of studio name strings
                - status (str or None)
                - country (str or None)
                - start_date (dict or None): {'year', 'month', 'day'}
                - year (int or None)
                - characters (list or None): [{'name', 'role', 'thumbnail', 'index'}]
                - trailer (str or None): full plugin URL
                - mpaa (str or None)

        Returns:
            Parsed view item dict, or None if episode should be skipped.
        """
        from resources.lib import MetaBrowser

        mal_id = data.get('mal_id')
        anilist_id = data.get('anilist_id')
        kitsu_id = data.get('kitsu_id')
        progress = data.get('progress', 0)
        show_title = data.get('show_title', '')
        total_eps = data.get('total_eps', 0)
        poster = data.get('poster')
        next_airing_episode = data.get('next_airing_episode')

        next_ep_num = progress + 1

        # Check if we should limit to aired episodes only
        if not control.getBool('playlist.unaired'):
            from resources.lib.AnimeSchedule import get_anime_schedule
            airing_anime = get_anime_schedule(mal_id)
            if airing_anime and airing_anime.get('current_episode'):
                max_aired = airing_anime['current_episode']
                if next_ep_num > max_aired:
                    return None
            # Also use AniList's nextAiringEpisode as a fallback filter
            if next_airing_episode and next_ep_num >= next_airing_episode:
                return None

        # Skip if next episode would be beyond known total
        if total_eps > 0 and next_ep_num > total_eps:
            return None

        # Get episode metadata via MetaBrowser (centralized for all watchlists)
        episode_meta = MetaBrowser.get_next_up_meta(mal_id, next_ep_num) if mal_id else {}

        # Fallback: if episode has an aired date in the future, hide it
        if not control.getBool('playlist.unaired') and episode_meta.get('aired'):
            from resources.lib.indexers import should_hide_unaired_episode
            if should_hide_unaired_episode(episode_meta['aired']):
                return None

        # Get season number
        season = utils.get_season([show_title], mal_id) if show_title and mal_id else 1

        # Build the display title: "Show Name 01x13 - Episode Title"
        season_str = str(season).zfill(2)
        ep_str = str(next_ep_num).zfill(2)
        ep_title = episode_meta.get('title', f'Episode {next_ep_num}')

        if control.getBool('interface.cleantitles'):
            display_title = f"{show_title} {season_str}x{ep_str}"
        else:
            display_title = f"{show_title} {season_str}x{ep_str} - {ep_title}"

        # Get artwork from show meta database
        show_meta = database.get_show_meta(mal_id) if mal_id else None
        art = pickle.loads(show_meta['art']) if show_meta else {}

        # Fanart
        fanart = art.get('fanart', poster)
        if isinstance(fanart, list):
            fanart = random.choice(fanart) if fanart else poster

        # Landscape (show-level widescreen thumbnail)
        landscape = None
        if art.get('thumb'):
            landscape = random.choice(art['thumb']) if isinstance(art['thumb'], list) else art['thumb']

        # Episode thumbnail
        ep_thumb = episode_meta.get('image')

        # Main image fallback: episode thumbnail → landscape → poster
        ep_image = ep_thumb or landscape or poster

        # Episode plot
        ep_plot = episode_meta.get('plot', '')
        if not ep_plot:
            ep_plot = f"Episode {next_ep_num} of {show_title}"

        # Aired date and episode rating
        aired = episode_meta.get('aired', '')
        ep_rating = episode_meta.get('rating')

        # Rating: prefer episode rating, fallback to show rating
        info_rating = None
        if ep_rating:
            info_rating = {'score': ep_rating}
        elif data.get('average_score'):
            info_rating = {'score': data['average_score']}

        # Premiered/year from start_date
        premiered = None
        year = data.get('year')
        if data.get('start_date'):
            sd = data['start_date']
            if isinstance(sd, dict):
                try:
                    premiered = '{}-{:02}-{:02}'.format(
                        int(sd.get('year', 0) or 0),
                        int(sd.get('month', 1) or 1),
                        int(sd.get('day', 1) or 1)
                    )
                    year = int(sd.get('year', 0) or 0) if sd.get('year') else year
                except (TypeError, ValueError):
                    pass

        # UniqueIDs
        unique_ids = {}
        if anilist_id:
            unique_ids['anilist_id'] = str(anilist_id)
            unique_ids.update(database.get_unique_ids(anilist_id, 'anilist_id'))
        if mal_id:
            unique_ids['mal_id'] = str(mal_id)
            unique_ids.update(database.get_unique_ids(mal_id, 'mal_id'))
        if kitsu_id:
            unique_ids['kitsu_id'] = str(kitsu_id)
            unique_ids.update(database.get_unique_ids(kitsu_id, 'kitsu_id'))

        # Build info dict
        info = {
            'UniqueIDs': unique_ids,
            'title': display_title,
            'tvshowtitle': show_title,
            'season': season,
            'episode': next_ep_num,
            'plot': ep_plot,
            'duration': data.get('duration'),
            'status': data.get('status'),
            'mediatype': 'episode',
        }

        # Add optional fields
        if aired:
            info['aired'] = aired
        if info_rating:
            info['rating'] = info_rating
        if data.get('genres'):
            info['genre'] = data['genres']
        if data.get('studios'):
            info['studio'] = data['studios']
        if data.get('country'):
            info['country'] = [data['country']] if isinstance(data['country'], str) else data['country']
        if premiered:
            info['premiered'] = premiered
        if year:
            info['year'] = year
        if data.get('characters'):
            info['cast'] = data['characters']
        if data.get('trailer'):
            info['trailer'] = data['trailer']
        if data.get('mpaa'):
            info['mpaa'] = data['mpaa']

        # Build the base item with all artwork
        base = {
            "name": display_title,
            "url": f"play/{mal_id}/{next_ep_num}" if mal_id else f"watchlist_to_ep/{anilist_id or kitsu_id}/{progress}",
            "image": ep_image,
            "info": info,
            "fanart": fanart,
            "poster": poster
        }

        if ep_thumb:
            base['thumb'] = ep_thumb
        if art.get('banner'):
            base['banner'] = art['banner']
        if landscape:
            base['landscape'] = landscape
        if art.get('clearart'):
            clearart = art['clearart']
            base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
        if art.get('clearlogo'):
            clearlogo = art['clearlogo']
            base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo

        # Handle movies
        if data.get('is_movie') and mal_id:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub=False)

        return utils.parse_view(base, False, True, dub=False)

    @staticmethod
    def _extract_anilist_enrichment(anilist_res):
        """Extract common metadata from AniList enrichment data used by all non-AniList flavors."""
        if not anilist_res:
            return {}

        data = {}

        # Score (AniList uses 0-100, convert to 0-10)
        if anilist_res.get('averageScore'):
            data['average_score'] = anilist_res['averageScore'] / 10.0

        # Duration (AniList gives minutes, convert to seconds)
        if anilist_res.get('duration'):
            data['duration'] = anilist_res['duration'] * 60 if isinstance(anilist_res['duration'], int) else anilist_res['duration']

        # Genres
        if anilist_res.get('genres'):
            data['genres'] = anilist_res['genres']

        # Studios
        if anilist_res.get('studios'):
            studios = anilist_res['studios']
            if isinstance(studios, list):
                data['studios'] = [s.get('name') for s in studios]
            elif isinstance(studios, dict) and 'edges' in studios:
                data['studios'] = [s['node'].get('name') for s in studios['edges']]

        # Status
        if anilist_res.get('status'):
            data['status'] = anilist_res['status']

        # Country
        if anilist_res.get('countryOfOrigin'):
            data['country'] = anilist_res['countryOfOrigin']

        # Start date
        if anilist_res.get('startDate') and isinstance(anilist_res['startDate'], dict):
            data['start_date'] = anilist_res['startDate']
            if anilist_res['startDate'].get('year'):
                data['year'] = int(anilist_res['startDate']['year'])

        # Characters/Cast
        if anilist_res.get('characters') and anilist_res['characters'].get('edges'):
            try:
                cast = []
                for i, x in enumerate(anilist_res['characters']['edges']):
                    role = x['node']['name']['userPreferred']
                    actor = x['voiceActors'][0]['name']['userPreferred']
                    actor_hs = x['voiceActors'][0]['image'].get('large', '')
                    cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
                if cast:
                    data['characters'] = cast
            except (IndexError, KeyError, TypeError):
                pass

        # Trailer
        if anilist_res.get('trailer'):
            try:
                if anilist_res['trailer']['site'] == 'youtube':
                    data['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={anilist_res['trailer']['id']}"
                else:
                    data['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={anilist_res['trailer']['id']}&mode=playVideo"
            except (KeyError, TypeError):
                pass

        # MPAA
        if anilist_res.get('countryOfOrigin'):
            data['mpaa'] = anilist_res['countryOfOrigin']

        # AniList ID
        if anilist_res.get('id'):
            data['anilist_id'] = anilist_res['id']

        # Poster from AniList
        if anilist_res.get('coverImage'):
            data['poster'] = anilist_res['coverImage'].get('extraLarge') or anilist_res['coverImage'].get('large')

        return data

    def _get_mapping_id(self, mal_id, flavor):
        show = database.get_show(mal_id)
        mapping_id = show[flavor] if show and show.get(flavor) else self.get_flavor_id_vercel(mal_id, flavor)
        if not mapping_id:
            mapping_id = self.get_flavor_id_findmyanime(mal_id, flavor)
        return mapping_id

    @staticmethod
    def get_flavor_id_vercel(mal_id, flavor):
        params = {
            'type': "mal",
            "id": mal_id
        }
        response = client.get('https://armkai.vercel.app/api/search', params=params)
        res = response.json() if response else {}
        flavor_id = res.get(flavor[:-3])
        database.add_mapping_id(mal_id, flavor, flavor_id)
        return flavor_id

    @staticmethod
    def get_flavor_id_findmyanime(mal_id, flavor):
        if flavor == 'anilist_id':
            mapping = 'Anilist'
        elif flavor == 'mal_id':
            mapping = 'MyAnimeList'
        elif flavor == 'kitsu_id':
            mapping = 'Kitsu'
        else:
            mapping = None
        params = {
            'id': mal_id,
            'providor': 'MyAnimeList'
        }
        response = client.get('https://find-my-anime.dtimur.de/api', params=params)
        res = response.json() if response else []
        flavor_id = res[0]['providerMapping'][mapping] if res else None
        database.add_mapping_id(mal_id, flavor, flavor_id)
        return flavor_id

    @staticmethod
    def get_flavor_id_simkl(mal_id, flavor):
        from resources.lib.indexers.simkl import SIMKLAPI
        ids = SIMKLAPI().get_mapping_ids_from_simkl(flavor, mal_id)
        flavor_id = ids[flavor]
        database.add_mapping_id(mal_id, flavor, flavor_id)
        return flavor_id
