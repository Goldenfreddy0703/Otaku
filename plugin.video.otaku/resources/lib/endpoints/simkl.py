import json
import os
import datetime
from resources.lib.ui import client, control

baseUrl = 'https://data.simkl.in/calendar/anime.json'


class Simkl:
    def __init__(self):
        self.anime_cache = {}

    def update_calendar(self):
        response = client.get(baseUrl)
        if response:
            simkl_cache = response.json()
            self.set_cached_data(simkl_cache)

    def get_calendar_data(self, mal_id):
        if mal_id in self.anime_cache:
            return self.anime_cache[mal_id]

        simkl_cache = self.get_cached_data()
        if simkl_cache:
            self.simkl_cache = simkl_cache
        else:
            response = client.get(baseUrl)
            if response:
                self.simkl_cache = response.json()
                self.set_cached_data(self.simkl_cache)
            else:
                return None

        for item in self.simkl_cache:
            if item.get('ids', {}).get('mal') == str(mal_id):
                episode_date_str = item.get('date')
                if episode_date_str:
                    episode_date = datetime.datetime.fromisoformat(episode_date_str)

                    # Check if episode has already aired
                    if datetime.datetime.now(datetime.timezone.utc) >= episode_date:
                        airing_episode = item.get('episode', {}).get('episode')
                        self.anime_cache[mal_id] = airing_episode
                        return airing_episode
                    else:
                        airing_episode = item.get('episode', {}).get('episode')
                        self.anime_cache[mal_id] = airing_episode - 1
                        return airing_episode - 1
        return None

    def fetch_and_find_simkl_entry(self, mal_id):
        simkl_cache = self.get_cached_data()
        if simkl_cache:
            self.simkl_cache = simkl_cache
        else:
            response = client.get(baseUrl)
            if response:
                self.simkl_cache = response.json()
                self.set_cached_data(self.simkl_cache)
            else:
                return None

        for entry in self.simkl_cache:
            if entry.get('ids', {}).get('mal') == str(mal_id):
                return entry
        return None

    def get_cached_data(self):
        if os.path.exists(control.simkl_calendar_json):
            with open(control.simkl_calendar_json, 'r') as f:
                return json.load(f)
        return None

    def set_cached_data(self, data):
        with open(control.simkl_calendar_json, 'w') as f:
            json.dump(data, f)
