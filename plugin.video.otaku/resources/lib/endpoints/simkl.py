import json
import os
import datetime
from resources.lib.ui import client, control

baseUrl = 'https://data.simkl.in/calendar/anime.json'
monthUrl = 'https://data.simkl.in/calendar/{y}/{m}/anime.json'


class Simkl:
    def __init__(self):
        self.anime_cache = {}

    def update_calendar(self):
        response = client.request(baseUrl)
        if response:
            simkl_cache = json.loads(response)
            self.set_cached_data(simkl_cache)

    def get_calendar_data(self, mal_id):
        if mal_id in self.anime_cache:
            return self.anime_cache[mal_id]

        simkl_cache = self.get_cached_data()
        if simkl_cache:
            self.simkl_cache = simkl_cache
        else:
            response = client.request(baseUrl)
            if response:
                self.simkl_cache = json.loads(response)
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
            response = client.request(baseUrl)
            if response:
                self.simkl_cache = json.loads(response)
                self.set_cached_data(self.simkl_cache)
            else:
                return None

        for entry in self.simkl_cache:
            if entry['ids']['mal'] == str(mal_id):
                return entry
        return None

    def fetch_month_json(self, year, month):
        """Fetch monthly calendar JSON for specific year/month."""
        url = monthUrl.format(y=year, m=month)
        response = client.request(url)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return []
        return []

    def fetch_base_json(self):
        """Fetch base calendar JSON as fallback."""
        response = client.request(baseUrl)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return []
        return []

    def get_calendar_range(self, start_dt, end_dt):
        """
        Get calendar data for date range, fetching multiple months if needed.
        Handles month boundary crossings and deduplicates entries.
        """
        # Determine which months we need to fetch
        months = {(start_dt.year, start_dt.month), (end_dt.year, end_dt.month)}
        
        merged = []
        fetched_months = []
        
        # Fetch each required month
        for (year, month) in sorted(months):
            month_data = self.fetch_month_json(year, month)
            if month_data:
                merged.extend(month_data)
                fetched_months.append(f"{year}-{month:02d}")
        
        # Fallback to base calendar if no monthly data found
        if not merged:
            merged = self.fetch_base_json()
            fetched_months = ["base"]
        
        # Log which months were fetched
        control.log(f"[DEBUG] Fetched Simkl months: {', '.join(fetched_months)}", 'debug')
        
        # Deduplicate raw entries by (mal_id, episode, date)
        seen = set()
        unique_entries = []
        
        for item in merged:
            mal_id = (item.get('ids') or {}).get('mal')
            episode = ((item.get('episode') or {}).get('episode')) or 0
            date = item.get('date')
            
            key = (mal_id, episode, date)
            
            if mal_id and date and key not in seen:
                seen.add(key)
                unique_entries.append(item)
        
        control.log(f"[DEBUG] Raw entries: {len(merged)}, unique entries: {len(unique_entries)}", 'debug')
        
        return unique_entries
    
    def get_cached_data(self):
        if os.path.exists(control.simkl_calendar_json):
            with open(control.simkl_calendar_json, 'r') as f:
                return json.load(f)
        return None

    def set_cached_data(self, data):
        with open(control.simkl_calendar_json, 'w') as f:
            json.dump(data, f)