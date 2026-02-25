import json
import time
import os
from resources.lib.ui import client, control


class Mal:
    _BASE_URL = "https://api.jikan.moe/v4"

    def update_calendar(self, page=1):
        days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        list_ = []

        for day in days_of_week:
            day_results = []
            current_page = page
            request_count = 0

            while True:
                retries = 3
                popular = None
                while retries > 0:
                    popular = self.get_airing_calendar_res(day, current_page)
                    if popular and 'data' in popular:
                        break
                    retries -= 1
                    time.sleep(1)  # Add delay before retrying

                if not popular or 'data' not in popular:
                    break

                day_results.extend(popular['data'])

                if not popular.get('pagination', {}).get('has_next_page'):
                    break

                current_page += 1
                request_count += 1

                if request_count >= 3:
                    time.sleep(1)  # Add delay to respect API rate limit
                    request_count = 0

            day_results.reverse()
            list_.extend(day_results)
            self.set_cached_data(list_)

    @staticmethod
    def get_base_res(url, params=None):
        response = client.get(url, params=params)
        if response:
            try:
                return response.json()
            except (ValueError, AttributeError):
                return None

    def get_airing_calendar_res(self, day, page=1):
        url = f'{self._BASE_URL}/schedules?kids=false&sfw=false&limit=25&page={page}&filter={day}'
        results = self.get_base_res(url)
        return results

    def get_cached_data(self):
        if os.path.exists(control.mal_calendar_json):
            try:
                with open(control.mal_calendar_json, 'r') as f:
                    return json.load(f)
            except (ValueError, json.JSONDecodeError):
                return None
        return None

    def set_cached_data(self, data):
        with open(control.mal_calendar_json, 'w') as f:
            json.dump(data, f)
