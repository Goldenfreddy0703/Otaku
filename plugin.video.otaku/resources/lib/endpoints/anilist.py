import json
from resources.lib.ui import client, control


class Anilist:
    _BASE_URL = "https://graphql.anilist.co"

    def get_anilist_by_mal_ids(self, mal_ids, page=1, media_type="ANIME"):
        query = '''
        query ($page: Int, $malIds: [Int], $type: MediaType) {
          Page(page: $page) {
            pageInfo {
              hasNextPage
              total
            }
            media(idMal_in: $malIds, type: $type) {
              id
              idMal
              title {
                romaji
                english
              }
              coverImage {
                extraLarge
              }
              bannerImage
              startDate {
                year
                month
                day
              }
              description
              synonyms
              format
              episodes
              status
              genres
              duration
              countryOfOrigin
              averageScore
              characters(
                page: 1
                sort: ROLE
                perPage: 10
              ) {
                edges {
                  node {
                    name {
                      userPreferred
                    }
                  }
                  voiceActors(language: JAPANESE) {
                    name {
                      userPreferred
                    }
                    image {
                      large
                    }
                  }
                }
              }
              studios {
                edges {
                  node {
                    name
                  }
                }
              }
              trailer {
                id
                site
              }
              stats {
                scoreDistribution {
                  score
                  amount
                }
              }
            }
          }
        }
        '''

        all_media = []
        page = 1
        while True:
            variables = {
                "page": page,
                "malIds": mal_ids,
                "type": media_type
            }
            result = client.request(self._BASE_URL, post={'query': query, 'variables': variables}, jpost=True)
            if not result:
                break
            results = json.loads(result)
            page_data = results.get('data', {}).get('Page', {})
            media = page_data.get('media', [])
            all_media.extend(media)
            has_next = page_data.get('pageInfo', {}).get('hasNextPage', False)
            if not has_next:
                break
            page += 1
        return all_media

    def get_enrichment_for_mal_ids(self, mal_ids):
        """
        Get AniList enrichment data using DB cache first, fetching only missing IDs from API.
        Returns list of AniList media objects (same format as get_anilist_by_mal_ids).
        """
        if not mal_ids:
            return []

        from resources.lib.ui.database import get_anilist_enrichment_batch, save_anilist_enrichment_batch

        # Check cache for existing data
        cached = get_anilist_enrichment_batch(mal_ids)
        cached_ids = set(cached.keys())
        missing = [mid for mid in mal_ids if int(mid) not in cached_ids]

        # Fetch missing from AniList API
        if missing:
            try:
                fresh = self.get_anilist_by_mal_ids(missing)
                if fresh:
                    save_anilist_enrichment_batch(fresh)
                    for item in fresh:
                        mal_id = item.get('idMal')
                        if mal_id:
                            cached[int(mal_id)] = item
            except Exception as e:
                control.log(f'AniList enrichment fetch failed: {e}', 'warning')

        return list(cached.values())


    def get_anilist_ratings_batch(self, mal_ids):
        """
        Get AniList ratings for multiple anime using MAL IDs in batch
        Fetches averageScore and meanScore from AniList API

        Args:
            mal_ids (list): List of MyAnimeList IDs (integers or strings)

        Returns:
            dict: Dictionary mapping MAL IDs to their AniList ratings
                  Format: {mal_id: {'anilist_score': score}}
                  Score is on 0-100 scale (e.g., 75 for 7.5/10)
        """
        if not mal_ids:
            return {}

        # Filter valid MAL IDs and convert to integers
        valid_mal_ids = []
        for mal_id in mal_ids:
            if mal_id and mal_id != 0:
                try:
                    valid_mal_ids.append(int(mal_id))
                except (ValueError, TypeError):
                    continue

        if not valid_mal_ids:
            return {}

        # AniList GraphQL query for ratings only
        query = '''
        query ($page: Int, $malIds: [Int], $type: MediaType) {
          Page(page: $page, perPage: 50) {
            pageInfo {
              hasNextPage
              total
            }
            media(idMal_in: $malIds, type: $type) {
              id
              idMal
              averageScore
              meanScore
            }
          }
        }
        '''

        ratings_map = {}
        page = 1

        try:
            while True:
                variables = {
                    "page": page,
                    "malIds": valid_mal_ids,
                    "type": "ANIME"
                }

                result = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})

                if not result:
                    break

                results = result.json()

                # Check for errors
                if "errors" in results:
                    control.log(f"AniList API error: {results['errors']}", "error")
                    break

                page_data = results.get('data', {}).get('Page', {})
                media_list = page_data.get('media', [])

                # Process each anime's rating
                for media in media_list:
                    mal_id = media.get('idMal')
                    if not mal_id:
                        continue

                    # AniList averageScore is already on 0-100 scale
                    avg_score = media.get('averageScore', 0)
                    mean_score = media.get('meanScore', 0)

                    # Use averageScore (community rating), fallback to meanScore if not available
                    score = avg_score if avg_score else mean_score

                    ratings_map[int(mal_id)] = {
                        'anilist_score': int(score) if score else 0
                    }

                # Check if there are more pages
                has_next = page_data.get('pageInfo', {}).get('hasNextPage', False)
                if not has_next:
                    break

                page += 1

            return ratings_map

        except Exception as e:
            control.log(f"Error fetching AniList ratings batch: {str(e)}", "error")
            return {}


    def get_banners_batch(self, mal_ids):
        """
        Get AniList banners for multiple anime using MAL IDs in batch
        Fetches bannerImage from AniList API

        Args:
            mal_ids (list): List of MyAnimeList IDs (integers or strings)

        Returns:
            dict: Dictionary mapping MAL IDs to their banner URLs
                  Format: {mal_id: 'banner_url'}
        """
        if not mal_ids:
            return {}

        # Filter valid MAL IDs and convert to integers
        valid_mal_ids = []
        for mal_id in mal_ids:
            if mal_id and mal_id != 0:
                try:
                    valid_mal_ids.append(int(mal_id))
                except (ValueError, TypeError):
                    continue

        if not valid_mal_ids:
            return {}

        # AniList GraphQL query for banners only
        query = '''
        query ($page: Int, $malIds: [Int], $type: MediaType) {
          Page(page: $page, perPage: 50) {
            pageInfo {
              hasNextPage
              total
            }
            media(idMal_in: $malIds, type: $type) {
              idMal
              bannerImage
            }
          }
        }
        '''

        banner_map = {}
        page = 1

        try:
            while True:
                variables = {
                    "page": page,
                    "malIds": valid_mal_ids,
                    "type": "ANIME"
                }

                result = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})

                if not result:
                    break

                results = result.json()

                # Check for errors
                if "errors" in results:
                    control.log(f"AniList API error: {results['errors']}", "error")
                    break

                page_data = results.get('data', {}).get('Page', {})
                media_list = page_data.get('media', [])

                # Process each anime's banner
                for media in media_list:
                    mal_id = media.get('idMal')
                    banner_url = media.get('bannerImage')

                    if mal_id and banner_url:
                        banner_map[int(mal_id)] = banner_url

                # Check if there are more pages
                has_next = page_data.get('pageInfo', {}).get('hasNextPage', False)
                if not has_next:
                    break

                page += 1

            return banner_map

        except Exception as e:
            control.log(f"Error fetching AniList banners batch: {str(e)}", "error")
            return {}


    def get_banner(self, mal_id):
        """
        Get AniList banner for a single anime using MAL ID

        Args:
            mal_id (int or str): MyAnimeList ID

        Returns:
            str: Banner URL or None if not found
        """
        if not mal_id:
            return None

        try:
            mal_id = int(mal_id)
        except (ValueError, TypeError):
            return None

        # AniList GraphQL query for single banner
        query = '''
        query ($malId: Int, $type: MediaType) {
          Media(idMal: $malId, type: $type) {
            bannerImage
          }
        }
        '''

        try:
            variables = {
                "malId": mal_id,
                "type": "ANIME"
            }

            result = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})

            if not result:
                return None

            results = result.json()

            # Check for errors
            if "errors" in results:
                control.log(f"AniList API error: {results['errors']}", "error")
                return None

            media = results.get('data', {}).get('Media', {})
            return media.get('bannerImage')

        except Exception as e:
            control.log(f"Error fetching AniList banner for MAL ID {mal_id}: {str(e)}", "error")
            return None


# Convenience functions
def get_anilist_ratings_for_mal_ids(mal_ids):
    """
    Get AniList ratings for multiple MAL IDs

    Args:
        mal_ids (list): List of MyAnimeList IDs

    Returns:
        dict: Dictionary mapping MAL IDs to AniList ratings
    """
    anilist = Anilist()
    return anilist.get_anilist_ratings_batch(mal_ids)
