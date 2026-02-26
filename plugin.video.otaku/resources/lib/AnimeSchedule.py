import datetime
import json
import os
import re
from html import unescape

from resources.lib.ui import client, database, control, utils
from resources.lib.endpoints import mdblist, anilist

BASE_URL = "https://animeschedule.net/api/v3"
WEBSITE_URL = "https://animeschedule.net"


class AnimeScheduleCalendar:
    """
    Fetches anime calendar data from AnimeSchedule.net API
    Filters and enriches data with MAL IDs and airing information
    Uses Bearer token authentication for timetables endpoints
    """

    def __init__(self):
        """Initialize with API credentials from database"""
        self.api_info = database.get_info('AnimeSchedule')
        if not self.api_info:
            control.log("AnimeSchedule API info not found in database", "error")
            self.token = None
        else:
            # Use 'client_secret' as the Bearer token
            self.token = self.api_info.get('client_secret')

        # Cache for /anime endpoint data (keyed by route)
        self._anime_cache = {}

        # Cache file path
        self.cache_file = control.animeschedule_calendar_json

        # Cache duration in seconds (default: 24 hours)
        self.cache_duration = 86400  # 24 hours

    def get_calendar_data(self, days=7, types=['sub', 'dub', 'raw'], force_refresh=False):
        """
        Fetch calendar data using optimized two-step strategy with caching:
        1. Check cache first (if not forcing refresh)
        2. If cache is valid, return cached data
        3. Otherwise, fetch fresh data:
           a. Fetch timetables (SUB, DUB, RAW)
           b. Fetch season anime until all pages exhausted
        4. Save fetched data to cache

        Args:
            days (int): Number of days to fetch (default: 7 for weekly view)
            types (list): Release types to fetch ['sub', 'dub', 'raw']
            force_refresh (bool): If True, bypass cache and fetch fresh data

        Returns:
            list: List of anime airing data with enriched information
        """
        try:
            # Check cache first (unless forced refresh)
            if not force_refresh:
                cached_data = self._load_cache()
                if cached_data:
                    control.log("AnimESchedule: Using cached calendar data", "info")
                    return cached_data

            control.log("AnimESchedule: Fetching fresh calendar data", "info")

            if not self.token:
                control.log("AnimESchedule token not found, cannot fetch timetables", "warning")
                return []

            # Get current year and week
            today = datetime.datetime.now()
            year = today.year
            week = today.isocalendar()[1]

            # Determine current season
            month = today.month
            if month in [12, 1, 2]:
                season = 'winter'
            elif month in [3, 4, 5]:
                season = 'spring'
            elif month in [6, 7, 8]:
                season = 'summer'
            else:  # 9, 10, 11
                season = 'fall'

            # STEP 1: Fetch timetables and collect unique routes
            all_timetable_anime = []
            unique_routes = set()

            # Build parallel requests for all three timetables
            timetable_requests = []
            for release_type in types:
                timetable_requests.append({
                    'func': self._fetch_timetable,
                    'args': (release_type, year, week),
                    'kwargs': {}
                })

            # Execute all timetable fetches in parallel
            timetable_results = utils.parallel_fetch(timetable_requests, max_workers=3)

            # Process results
            for release_type, anime_data in zip(types, timetable_results):
                if anime_data:
                    for anime in anime_data:
                        route = anime.get('route')
                        all_timetable_anime.append({
                            'route': route,
                            'type': release_type,
                            'data': anime
                        })
                        unique_routes.add(route)

            unique_count = len(unique_routes)
            control.log(f"AnimESchedule: Found {unique_count} unique anime from timetables", "info")

            # STEP 2: Fetch season anime in parallel (fixed number of pages)
            season_anime = {}
            matched_routes = set()

            # Fetch first 10 pages (covers ~180 anime, enough for most ongoing seasons)
            max_pages_to_fetch = 10

            control.log(f"AnimESchedule: Fetching {max_pages_to_fetch} pages in parallel", "info")

            # Create parallel requests for multiple pages
            page_requests = [
                {
                    'func': self._fetch_season_anime,
                    'args': (year, season, page),
                    'kwargs': {}
                }
                for page in range(1, max_pages_to_fetch + 1)
            ]

            # Fetch all pages in parallel with 10 workers
            page_results = utils.parallel_fetch(page_requests, max_workers=10)

            # Process all results
            for page_data in page_results:
                if page_data:
                    for anime in page_data:
                        route = anime.get('route')
                        if route not in season_anime:
                            season_anime[route] = anime

                        if route in unique_routes:
                            matched_routes.add(route)

            control.log(f"AnimESchedule: Matched {len(matched_routes)}/{unique_count} from season pages", "info")

            # STEP 3: Individual searches for unmatched routes (parallel with retry)
            unmatched_routes = unique_routes - matched_routes
            if unmatched_routes:
                control.log(f"AnimESchedule: Fetching {len(unmatched_routes)} unmatched routes individually", "info")

                # Create search requests for parallel fetching
                search_requests = [
                    {
                        'func': self._search_anime_by_route,
                        'args': (route,),
                        'kwargs': {}
                    }
                    for route in sorted(unmatched_routes)
                ]

                # Parallel search with 25 workers (increased from 20)
                search_results = utils.parallel_fetch(search_requests, max_workers=25)

                # Process results
                found_count = 0
                for result in search_results:
                    if result and isinstance(result, dict):
                        route = result.get('route')
                        if route and route in unmatched_routes:
                            season_anime[route] = result
                            matched_routes.add(route)
                            found_count += 1

                control.log(f"AnimESchedule: Individual fetch found {found_count}/{len(unmatched_routes)}", "info")

                # Retry any remaining failures with reduced workers (only if needed)
                still_unmatched = unmatched_routes - matched_routes
                if still_unmatched and len(still_unmatched) > 0:
                    import time
                    control.log(f"AnimESchedule: Retrying {len(still_unmatched)} failed routes", "info")

                    # Only delay if many failures (>10) to avoid rate limiting
                    if len(still_unmatched) > 10:
                        time.sleep(0.5)

                    retry_requests = [
                        {
                            'func': self._search_anime_by_route,
                            'args': (route,),
                            'kwargs': {}
                        }
                        for route in sorted(still_unmatched)
                    ]

                    # Use 12 workers for retry (increased from 10)
                    retry_results = utils.parallel_fetch(retry_requests, max_workers=12)

                    retry_found = 0
                    for result in retry_results:
                        if result and isinstance(result, dict):
                            route = result.get('route')
                            if route and route in still_unmatched:
                                season_anime[route] = result
                                matched_routes.add(route)
                                retry_found += 1

                    control.log(f"AnimESchedule: Retry found {retry_found}/{len(still_unmatched)}", "info")

            control.log(f"AnimESchedule: Total enriched {len(matched_routes)}/{unique_count}", "info")

            # Process and return results - GROUP by route to combine all release types
            anime_by_route = {}

            for timetable_entry in all_timetable_anime:
                route = timetable_entry['route']
                release_type = timetable_entry['type']
                raw_anime = timetable_entry['data']

                # Initialize route entry if not exists
                if route not in anime_by_route:
                    # Get enriched data from season fetch
                    enriched_data = season_anime.get(route)

                    # Extract MAL ID
                    mal_id = None
                    if enriched_data:
                        mal_id = self._extract_mal_id(enriched_data)

                    anime_by_route[route] = {
                        'route': route,
                        'mal_id': mal_id,
                        'title': raw_anime.get('title'),
                        'romaji': raw_anime.get('romaji'),
                        'english': raw_anime.get('english'),
                        'native': raw_anime.get('native'),
                        'image': self._get_image_url(raw_anime, mal_id),
                        'total_episodes': enriched_data.get('episodes') if enriched_data else None,
                        'status': enriched_data.get('status') if enriched_data else None,
                        'airing_status': raw_anime.get('airingStatus'),
                        'length_min': raw_anime.get('lengthMin'),
                        'is_donghua': raw_anime.get('donghua', False),
                        'media_types': [m['name'] for m in raw_anime.get('mediaTypes', [])],
                        'genres': [g['name'] for g in enriched_data.get('genres', [])] if enriched_data else [],
                        'studios': [s['name'] for s in enriched_data.get('studios', [])] if enriched_data else [],
                        'description': enriched_data.get('description') if enriched_data else None,
                        'websites': enriched_data.get('websites', {}) if enriched_data else {},
                        'stats': enriched_data.get('stats', {}) if enriched_data else {},
                        'streams': raw_anime.get('streams', []),
                        # Initialize release type data
                        'releases': {}
                    }

                # Add release type specific data
                anime_by_route[route]['releases'][release_type] = {
                    'episode_number': raw_anime.get('episodeNumber'),
                    'episode_date': raw_anime.get('episodeDate'),
                }

            result = list(anime_by_route.values())

            mal_id_count = len([a for a in result if a.get('mal_id')])
            control.log(f"AnimESchedule: Returned {len(result)} anime with {mal_id_count} MAL IDs", "info")

            # Save to cache
            self._save_cache(result)

            return result

        except Exception as e:
            control.log(f"Error fetching AnimeSchedule calendar: {str(e)}", "error")
            return []

    def _load_cache(self):
        """
        Load calendar data from cache file if it exists and is not expired

        Returns:
            list: Cached anime data, or None if cache is invalid/expired
        """
        try:
            if not os.path.exists(self.cache_file):
                control.log("AnimESchedule: No cache file found", "debug")
                return None

            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check cache timestamp
            cached_time = cache_data.get('timestamp', 0)
            current_time = datetime.datetime.now().timestamp()

            if current_time - cached_time > self.cache_duration:
                control.log(f"AnimESchedule: Cache expired (age: {int(current_time - cached_time)}s)", "debug")
                return None

            anime_data = cache_data.get('data', [])
            control.log(f"AnimESchedule: Cache valid ({len(anime_data)} anime, age: {int(current_time - cached_time)}s)", "info")
            return anime_data

        except Exception as e:
            control.log(f"Error loading cache: {str(e)}", "error")
            return None

    def _save_cache(self, anime_data):
        """
        Save calendar data to cache file with timestamp

        Args:
            anime_data (list): Anime data to cache
        """
        try:
            # Ensure directory exists
            cache_dir = os.path.dirname(self.cache_file)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

            cache_data = {
                'timestamp': datetime.datetime.now().timestamp(),
                'data': anime_data
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            control.log(f"AnimESchedule: Saved {len(anime_data)} anime to cache", "info")

        except Exception as e:
            control.log(f"Error saving cache: {str(e)}", "error")

    def clear_cache(self):
        """Clear the calendar cache file"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                control.log("AnimESchedule: Cache cleared", "info")
                return True
            return False
        except Exception as e:
            control.log(f"Error clearing cache: {str(e)}", "error")
            return False

    def _fetch_timetable(self, release_type, year, week):
        """
        Fetch timetable data from AnimESchedule API with Bearer token auth

        Args:
            release_type (str): 'sub', 'dub', or 'raw'
            year (int): Year (e.g., 2025)
            week (int): Week number (1-53)

        Returns:
            list: Anime data for the specified week
        """
        try:
            url = f"{BASE_URL}/timetables/{release_type}"
            params = {
                'year': year,
                'week': week
            }
            headers = {
                'Authorization': f'Bearer {self.token}'
            }

            # Note: client.get() might not support headers, so we use client directly
            response = client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                control.log(f"Failed to fetch {release_type} timetable: {response.status_code}", "error")
                return None

        except Exception as e:
            control.log(f"Error in _fetch_timetable: {str(e)}", "error")
            return None

    def _fetch_season_anime(self, year, season, page):
        """
        Fetch anime for a specific season and year

        Args:
            year (int): Year (e.g., 2025)
            season (str): Season ('winter', 'spring', 'summer', 'fall')
            page (int): Page number (1-indexed)

        Returns:
            list: Anime list for the page, or empty list on error
        """
        try:
            url = f"{BASE_URL}/anime"
            params = {
                'year': year,
                'seasons': season,
                'airing-statuses': 'ongoing',
                'page': page
            }

            response = client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                anime_list = data.get('anime', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                return anime_list

            return []

        except Exception as e:
            control.log(f"Error fetching season anime page {page}: {str(e)}", "debug")
            return []

    def _search_anime_by_route(self, route):
        """
        Fetch anime by route slug using direct endpoint with retry logic

        Args:
            route (str): Anime route slug

        Returns:
            dict: Anime data if found, None otherwise
        """
        import time

        max_attempts = 2
        retry_delay = 0.2  # Reduced from 0.3 for faster retries

        for attempt in range(max_attempts):
            try:
                # Use direct route endpoint: /anime/{route}
                url = f"{BASE_URL}/anime/{route}"

                response = client.get(url, timeout=6)  # Reduced from 8 to 6 seconds

                if response.status_code == 200:
                    data = response.json()
                    # Direct endpoint returns single anime object, not a list
                    if data and isinstance(data, dict):
                        return data

                # If we got here, no results or bad status - try again
                if attempt < max_attempts - 1:
                    time.sleep(retry_delay)

            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(retry_delay)
                else:
                    control.log(f"Error fetching route {route} after {max_attempts} attempts: {str(e)}", "debug")

        return None

    def _extract_mal_id(self, anime):
        """Extract MAL ID from anime data"""
        # Check websites.mal link for MAL ID
        websites = anime.get('websites', {})
        mal_link = websites.get('mal', '')

        if mal_link:
            # Extract from URL like "myanimelist.net/anime/5114/Title"
            parts = mal_link.split('/anime/')
            if len(parts) > 1:
                mal_id_str = parts[1].split('/')[0]
                return control.safe_call(int, mal_id_str)

        return None

    def _get_image_url(self, anime, mal_id=None):
        """
        Get image URL from AnimESchedule - fast and reliable
        No validation needed, Kodi handles 404s gracefully
        """
        image_route = anime.get('imageVersionRoute')
        if image_route:
            return f"https://img.animeschedule.net/production/assets/public/img/{image_route}"
        return None

    def _clean_html(self, text):
        """
        Clean HTML tags and decode HTML entities from text
        Converts HTML formatting to Kodi formatting tags

        Args:
            text (str): Text with HTML tags/entities

        Returns:
            str: Cleaned text with Kodi formatting
        """
        if not text:
            return ''

        # Decode HTML entities first (&#39; -> ', &amp; -> &, etc.)
        text = unescape(text)

        # Convert HTML formatting to Kodi formatting (following maintainer pattern)
        text = text.replace('<i>', '[I]').replace('</i>', '[/I]')
        text = text.replace('<b>', '[B]').replace('</b>', '[/B]')
        text = text.replace('<br>', '[CR]').replace('<br/>', '[CR]').replace('<br />', '[CR]')

        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Add space after period if missing (e.g., "Monogatari.Sato" -> "Monogatari. Sato")
        text = re.sub(r'\.([A-Z])', r'. \1', text)

        # Clean up extra whitespace but preserve [CR] line breaks
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.replace('\n', '').strip()

        return text

    def format_for_anichart(self, anime_list):
        """
        Transform enriched anime data into Anichart display format

        Args:
            anime_list (list): List of enriched anime entries from get_calendar_data()

        Returns:
            list: List of formatted anime items for Anichart window
        """
        from resources.lib.ui import control

        # Get user's title language preference (0=romaji, 1=english)
        title_lang_pref = control.getInt("titlelanguage")

        # Collect all MAL IDs for batch ratings fetch
        mal_ids = [anime.get('mal_id') for anime in anime_list if anime.get('mal_id')]

        # Fetch ratings for all anime in one batch request (MDBList and AniList)
        ratings_map = {}
        anilist_ratings_map = {}
        if mal_ids:
            ratings_map = control.safe_call(mdblist.get_ratings_for_mal_ids, mal_ids, default={})
            anilist_ratings_map = control.safe_call(anilist.get_anilist_ratings_for_mal_ids, mal_ids, default={})

        formatted_items = []

        for anime in anime_list:
            try:
                # Select title based on user preference
                if title_lang_pref == 1:  # English
                    title = anime.get('english') or anime.get('romaji') or anime.get('title')
                else:  # Romaji (default)
                    title = anime.get('romaji') or anime.get('english') or anime.get('title')

                # Format stats
                stats = anime.get('stats', {})
                score_raw = stats.get('averageScore', 0)
                # API returns score as float64 on 0-100 scale (e.g., 68.753, 97.1)
                # Convert to integer to remove decimals for clean display
                score = int(score_raw) if score_raw else 0
                popularity = stats.get('popularity', 0)
                rank = stats.get('rank', 0)

                # Format genres and studios
                genres = ', '.join(anime.get('genres', []))
                studios = ', '.join(anime.get('studios', []))

                # Format streams/episodes info
                streams = anime.get('streams', [])
                stream_info = self._format_streams(streams)

                # Process all release types
                releases = anime.get('releases', {})

                # RAW release data
                raw_data = releases.get('raw', {})
                raw_ep = raw_data.get('episode_number', 0)
                raw_date = raw_data.get('episode_date', '')
                raw_day = self._format_episode_day(raw_date)
                raw_date_formatted = self._format_episode_date(raw_date)
                raw_time = self._format_episode_time(raw_date)
                raw_countdown = self._format_countdown(raw_date)

                # SUB release data
                sub_data = releases.get('sub', {})
                sub_ep = sub_data.get('episode_number', 0)
                sub_date = sub_data.get('episode_date', '')
                sub_day = self._format_episode_day(sub_date)
                sub_date_formatted = self._format_episode_date(sub_date)
                sub_time = self._format_episode_time(sub_date)
                sub_countdown = self._format_countdown(sub_date)

                # DUB release data
                dub_data = releases.get('dub', {})
                dub_ep = dub_data.get('episode_number', 0)
                dub_date = dub_data.get('episode_date', '')
                dub_day = self._format_episode_day(dub_date)
                dub_date_formatted = self._format_episode_date(dub_date)
                dub_time = self._format_episode_time(dub_date)
                dub_countdown = self._format_countdown(dub_date)

                # Determine primary release (first available: raw > sub > dub)
                primary_ep = raw_ep or sub_ep or dub_ep
                primary_date = raw_date or sub_date or dub_date

                # Get MDBList ratings for this anime
                mal_id = anime.get('mal_id')
                mdblist_ratings = ratings_map.get(mal_id, {}) if mal_id else {}

                rating_mal = mdblist_ratings.get('mal', 0.0)

                # If MDBList has no MAL rating (0.0), fallback to database score
                if rating_mal == 0.0 and mal_id:
                    db_mapping = database.get_mappings(mal_id, 'mal_id')
                    if db_mapping and db_mapping.get('score'):
                        try:
                            # Round to 1 decimal place (8.64 -> 8.6)
                            rating_mal = round(float(db_mapping.get('score')), 1)
                            # Cap 10.0 scores at 9.9
                            if rating_mal == 10.0:
                                rating_mal = 9.9
                        except (ValueError, TypeError):
                            rating_mal = 0.0

                rating_imdb = mdblist_ratings.get('imdb', 0.0)
                rating_trakt = mdblist_ratings.get('trakt', 0.0)
                rating_tmdb = mdblist_ratings.get('tmdb', 0.0)
                # score_average is already 0-100 scale from MDBList API
                rating_average = mdblist_ratings.get('score_average', 0)

                # Get AniList rating for this anime
                anilist_ratings = anilist_ratings_map.get(mal_id, {}) if mal_id else {}
                # anilist_score is 0-100 scale from AniList API, convert to 0-10 decimal
                anilist_score_raw = anilist_ratings.get('anilist_score', 0)
                rating_anilist = round(anilist_score_raw / 10.0, 1) if anilist_score_raw > 0 else 0.0

                # If MDBList has no average rating, fallback to AniList score (both are 0-100 scale)
                if rating_average == 0 and anilist_score_raw > 0:
                    rating_average = anilist_score_raw

                # Convert 0 or 0.0 ratings to "-" for display
                rating_mal = "-" if rating_mal in (0, 0.0) else str(rating_mal)
                rating_imdb = "-" if rating_imdb in (0, 0.0) else str(rating_imdb)
                rating_trakt = "-" if rating_trakt in (0, 0.0) else str(rating_trakt)
                rating_tmdb = "-" if rating_tmdb in (0, 0.0) else str(rating_tmdb)
                rating_average = "-" if rating_average in (0, 0.0) else f"{rating_average}%"
                rating_anilist = "-" if rating_anilist in (0, 0.0) else str(rating_anilist)

                # Build Anichart item
                anichart_item = {
                    'id': anime.get('mal_id') or anime.get('route'),
                    'release_title': title,
                    'title': title,
                    'romaji': anime.get('romaji', ''),
                    'english': anime.get('english', ''),
                    'native': anime.get('native', ''),
                    'poster': anime.get('image', ''),
                    'plot': self._clean_html(anime.get('description', '')),
                    'genres': genres,
                    'studios': studios,
                    'total_episodes': anime.get('total_episodes', 0),
                    'status': anime.get('status', ''),
                    'airing_status': anime.get('airing_status', ''),
                    'length_min': anime.get('length_min', 0),
                    'media_type': ', '.join(anime.get('media_types', [])),
                    'is_donghua': 'Yes' if anime.get('is_donghua') else 'No',
                    'mal_id': anime.get('mal_id', 0),
                    'route': anime.get('route', ''),
                    # Stats
                    'averageScore': score,
                    'popularity': popularity,
                    'rank': rank,
                    # RAW release
                    'raw_episode': raw_ep,
                    'raw_date': raw_date,
                    'raw_day': raw_day,
                    'raw_date_formatted': raw_date_formatted,
                    'raw_time': raw_time,
                    'raw_countdown': raw_countdown,
                    # SUB release
                    'sub_episode': sub_ep,
                    'sub_date': sub_date,
                    'sub_day': sub_day,
                    'sub_date_formatted': sub_date_formatted,
                    'sub_time': sub_time,
                    'sub_countdown': sub_countdown,
                    # DUB release
                    'dub_episode': dub_ep,
                    'dub_date': dub_date,
                    'dub_day': dub_day,
                    'dub_date_formatted': dub_date_formatted,
                    'dub_time': dub_time,
                    'dub_countdown': dub_countdown,
                    # Primary/default values (for backward compatibility)
                    'episode_number': primary_ep,
                    'episode_date': primary_date,
                    # Streams
                    'streams': stream_info,
                    'websites': str(anime.get('websites', {})),
                    # MDBList Ratings
                    'rating_mal': rating_mal,
                    'rating_imdb': rating_imdb,
                    'rating_trakt': rating_trakt,
                    'rating_tmdb': rating_tmdb,
                    'rating_average': rating_average,
                    # AniList Rating
                    'rating_anilist': rating_anilist,
                }

                formatted_items.append(anichart_item)

            except Exception as e:
                control.log(f"Error formatting anime for Anichart: {str(e)}", "error")
                continue

        return formatted_items

    def _format_episode_day(self, episode_date):
        """
        Format episode day

        Args:
            episode_date (str): ISO format datetime string

        Returns:
            str: Formatted day (e.g., "Thursday")
        """
        if not episode_date or episode_date == '0001-01-01T00:00:00Z':
            return 'TBA'

        try:
            dt = datetime.datetime.fromisoformat(episode_date.replace('Z', '+00:00'))
            return dt.strftime('%A')
        except:
            return episode_date

    def _format_episode_date(self, episode_date):
        """
        Format episode date

        Args:
            episode_date (str): ISO format datetime string

        Returns:
            str: Formatted date (e.g., "06 Nov")
        """
        if not episode_date or episode_date == '0001-01-01T00:00:00Z':
            return 'TBA'

        try:
            dt = datetime.datetime.fromisoformat(episode_date.replace('Z', '+00:00'))
            return dt.strftime('%d %b')
        except:
            return episode_date

    def _format_episode_time(self, episode_date):
        """
        Format episode time

        Args:
            episode_date (str): ISO format datetime string

        Returns:
            str: Formatted time (e.g., "12:00 PM")
        """
        if not episode_date or episode_date == '0001-01-01T00:00:00Z':
            return 'TBA'

        try:
            dt = datetime.datetime.fromisoformat(episode_date.replace('Z', '+00:00'))
            return dt.strftime('%I:%M %p')
        except:
            return episode_date

    def _format_countdown(self, episode_date):
        """
        Calculate countdown to episode release

        Args:
            episode_date (str): ISO format datetime string

        Returns:
            str: Formatted countdown (e.g., "14h 54m" or "Released")
        """
        if not episode_date or episode_date == '0001-01-01T00:00:00Z':
            return 'TBA'

        try:
            # Parse ISO format date
            dt = datetime.datetime.fromisoformat(episode_date.replace('Z', '+00:00'))
            now = datetime.datetime.now(dt.tzinfo)

            # Calculate difference
            diff = dt - now

            if diff.total_seconds() < 0:
                return 'Released'

            # Convert to hours and minutes
            total_minutes = int(diff.total_seconds() / 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60

            if hours > 24:
                days = hours // 24
                hours = hours % 24
                return f"{days}d {hours}h {minutes}m"
            else:
                return f"{hours}h {minutes}m"
        except:
            return 'TBA'

    def _format_streams(self, streams):
        """Format streaming service information"""
        if not streams:
            return 'Not specified'

        stream_names = []
        for stream in streams:
            if isinstance(stream, dict):
                name = stream.get('name') or stream.get('title')
                if name:
                    stream_names.append(name)
            else:
                stream_names.append(str(stream))

        return ', '.join(stream_names) if stream_names else 'Not specified'

    def _calculate_current_episode(self, premier_date, airing_time, total_episodes):
        """
        Calculate the current airing episode based on premier date and airing schedule

        Args:
            premier_date (str): ISO format datetime string of premiere
            airing_time (str): ISO format datetime string of weekly airing time
            total_episodes (int): Total number of episodes

        Returns:
            int: Current episode number, or 0 if not yet aired
        """
        try:
            # Check for invalid/placeholder dates
            if not premier_date or premier_date == '0001-01-01T00:00:00Z':
                return 0
            if not airing_time or airing_time == '0001-01-01T00:00:00Z':
                return 0

            # Parse dates
            premier = datetime.datetime.fromisoformat(premier_date.replace('Z', '+00:00'))
            now = datetime.datetime.now(premier.tzinfo)

            # If hasn't premiered yet
            if now < premier:
                return 0

            # Calculate weeks since premiere
            time_diff = now - premier
            weeks_since_premier = int(time_diff.total_seconds() / (7 * 24 * 60 * 60))

            # Current episode is weeks since premier + 1 (episode 1 airs on week 0)
            current_episode = weeks_since_premier + 1

            # Cap at total episodes if specified
            if total_episodes and total_episodes > 0:
                current_episode = min(current_episode, total_episodes)

            return current_episode

        except Exception as e:
            control.log(f"Error calculating current episode: {str(e)}", "debug")
            return 0

    def get_anime_by_mal_id(self, mal_id):
        """
        Get specific anime's data by MAL ID with calculated current episode

        Args:
            mal_id (int): MyAnimeList ID

        Returns:
            dict: Anime data with airing information and current episode
        """
        try:
            params = {
                "mal-ids": mal_id
            }

            response = client.get(f"{BASE_URL}/anime", params=params)

            if response:
                data = response.json()
                anime_list = data.get('anime', [])

                if anime_list:
                    anime = anime_list[0]

                    # Get premiere and airing time for RAW (Japanese release)
                    premier_date = anime.get('premier')
                    jpn_time = anime.get('jpnTime')
                    total_episodes = anime.get('episodes')

                    # Calculate current RAW episode
                    current_episode = self._calculate_current_episode(premier_date, jpn_time, total_episodes)

                    enriched_anime = {
                        'mal_id': mal_id,
                        'route': anime.get('route'),
                        'title': anime.get('title'),
                        'image': self._get_image_url(anime, mal_id),
                        'description': anime.get('description'),
                        'episodes': total_episodes,
                        'current_episode': current_episode,
                        'genres': [g['name'] for g in anime.get('genres', [])],
                        'status': anime.get('status'),
                        'studios': [s['name'] for s in anime.get('studios', [])],
                        'airing_info': {
                            'sub': {
                                'time': anime.get('subTime'),
                                'delayed_from': anime.get('subDelayedFrom'),
                                'delayed_until': anime.get('subDelayedUntil'),
                            },
                            'dub': {
                                'time': anime.get('dubTime'),
                                'delayed_from': anime.get('dubDelayedFrom'),
                                'delayed_until': anime.get('dubDelayedUntil'),
                            },
                            'delay_description': anime.get('delayedDesc'),
                        },
                        'stats': anime.get('stats', {}),
                        'websites': anime.get('websites', {}),
                        'raw_data': anime
                    }

                    return enriched_anime
                else:
                    control.log(f"No anime found for MAL ID: {mal_id}", "warning")
                    return None
            else:
                control.log(f"Failed to fetch anime data for MAL ID: {mal_id}", "error")
                return None

        except Exception as e:
            control.log(f"Error in get_anime_by_mal_id: {str(e)}", "error")
            return None


# Convenience functions for direct usage
def get_calendar(days=7, force_refresh=False):
    """
    Get calendar data for upcoming days

    Args:
        days (int): Number of days to fetch (default: 7)
        force_refresh (bool): If True, bypass cache and fetch fresh data

    Returns:
        list: Anime calendar data
    """
    scheduler = AnimeScheduleCalendar()
    return scheduler.get_calendar_data(days=days, force_refresh=force_refresh)


def clear_calendar_cache():
    """Clear the calendar cache"""
    scheduler = AnimeScheduleCalendar()
    return scheduler.clear_cache()


def get_anime_schedule(mal_id):
    """Get schedule for specific anime by MAL ID"""
    scheduler = AnimeScheduleCalendar()
    return scheduler.get_anime_by_mal_id(mal_id)
