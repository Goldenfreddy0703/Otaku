"""
MDBList API endpoint for fetching media ratings and information
API Documentation: https://mdblist.docs.apiary.io/
"""

from resources.lib.ui import client, database, control


class MDBListAPI:
    """
    MDBList API client for fetching ratings from multiple sources
    (MAL, IMDb, Trakt, TMDb)
    """

    def __init__(self):
        """Initialize with API credentials from database"""
        self.base_url = "https://api.mdblist.com"
        self.api_info = database.get_info('MDBList')

        if not self.api_info:
            control.log("MDBList API info not found in database", "warning")
            self.api_key = None
        else:
            self.api_key = self.api_info.get('api_key') or self.api_info.get('apikey')

    def get_ratings_batch(self, mal_ids):
        """
        Get ratings for multiple anime using MAL IDs in a single batch request

        Args:
            mal_ids (list): List of MyAnimeList IDs (integers or strings)

        Returns:
            dict: Dictionary mapping MAL IDs to their ratings data
                  Format: {mal_id: {'mal': score, 'imdb': score, 'trakt': score, 'tmdb': score, 'score_average': score}}
        """
        if not self.api_key:
            control.log("MDBList API key not available", "warning")
            return {}

        if not mal_ids:
            return {}

        try:
            # Convert all IDs to strings and filter out invalid ones
            valid_mal_ids = []
            for mal_id in mal_ids:
                if mal_id and mal_id != 0:
                    valid_mal_ids.append(str(mal_id))

            if not valid_mal_ids:
                return {}

            # Build request with MAL IDs as strings (per API docs)
            # MDBList batch API requires POST with JSON body

            # Prepare the POST body with IDs as strings
            post_data = {
                "ids": valid_mal_ids,  # Already strings from above
                "append_to_response": ["ids"]
            }

            # Build URL with API key as query parameter
            url = f"{self.base_url}/mal/any?apikey={self.api_key}"

            headers = {
                'Content-Type': 'application/json'
            }

            response = client.post(url, json_data=post_data, headers=headers, timeout=10)

            if response and response.status_code == 200:
                data = response.json()

                # Process response and extract ratings
                ratings_map = {}

                # Response is either a list (batch) or single object
                items = data if isinstance(data, list) else [data]

                for item in items:
                    if not item or not isinstance(item, dict):
                        continue

                    # Extract MAL ID from the ids object
                    ids_obj = item.get('ids', {})
                    mal_id = ids_obj.get('mal') if isinstance(ids_obj, dict) else None

                    if not mal_id:
                        continue

                    # Extract ratings from different sources
                    ratings = item.get('ratings', [])

                    rating_dict = {
                        'mal': 0.0,
                        'imdb': 0.0,
                        'trakt': 0.0,
                        'tmdb': 0.0,
                        'score_average': 0.0
                    }

                    # Parse ratings array
                    if ratings and isinstance(ratings, list):
                        for rating in ratings:
                            if not isinstance(rating, dict):
                                continue

                            source = rating.get('source', '').lower()
                            # Use 'value' field from ratings
                            score = rating.get('value')

                            # Skip null/None values
                            if score is None:
                                continue

                            # Try to convert score to float
                            score = control.safe_call(float, score, default=0.0)

                            # Map source to rating type
                            # Note: IMDb and MAL use 0-10 scale, Trakt and TMDb use 0-100 scale
                            if 'myanimelist' in source or 'mal' in source:
                                # MAL: 0-10 scale
                                rating_dict['mal'] = round(score, 1) if score > 0 else 0.0
                            elif 'imdb' in source:
                                # IMDb: 0-10 scale
                                rating_dict['imdb'] = round(score, 1) if score > 0 else 0.0
                            elif 'trakt' in source:
                                # Trakt: 0-100 scale, convert to 0-10
                                rating_dict['trakt'] = round(score / 10.0, 1) if score > 0 else 0.0
                            elif 'tmdb' in source or 'themoviedb' in source:
                                # TMDb: 0-100 scale, convert to 0-10
                                rating_dict['tmdb'] = round(score / 10.0, 1) if score > 0 else 0.0

                    # Get average score (already 0-100 scale from API)
                    avg_score = item.get('score_average', 0)
                    rating_dict['score_average'] = control.safe_call(int, avg_score, default=0) if avg_score else 0

                    ratings_map[int(mal_id)] = rating_dict

                return ratings_map

            else:
                return {}

        except Exception:
            return {}

    def get_single_rating(self, mal_id):
        """
        Get ratings for a single anime by MAL ID

        Args:
            mal_id (int/str): MyAnimeList ID

        Returns:
            dict: Ratings data or None if not found
                  Format: {'mal': score, 'imdb': score, 'trakt': score, 'tmdb': score, 'score_average': score}
        """
        if not mal_id or mal_id == 0:
            return None

        ratings_map = self.get_ratings_batch([mal_id])
        return ratings_map.get(int(mal_id))


# Convenience functions
def get_ratings_for_mal_ids(mal_ids):
    """
    Get ratings for multiple MAL IDs

    Args:
        mal_ids (list): List of MyAnimeList IDs

    Returns:
        dict: Dictionary mapping MAL IDs to ratings
    """
    api = MDBListAPI()
    return api.get_ratings_batch(mal_ids)


def get_rating_for_mal_id(mal_id):
    """
    Get ratings for a single MAL ID

    Args:
        mal_id (int/str): MyAnimeList ID

    Returns:
        dict: Ratings data or None
    """
    api = MDBListAPI()
    return api.get_single_rating(mal_id)
