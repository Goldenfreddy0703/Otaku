import datetime
import re
import time

from resources.lib.ui import client, control, database

api_info = database.get_info('Teamup')
api_key = api_info['api_key']
headers = {'Content-Type': "application/json", 'Teamup-Token': api_key}
token = "ksdhpfjcouprnauwda"
api_url = "https://api.teamup.com"


def get_dub_data(mal_id: int = None, en_title: str = None):
    if en_title:
        clean_title = re.sub(r'[:!]', '', en_title)
        if '-' in clean_title:
            query_search = clean_title.split('-')[0].strip()
        else:
            match = re.search(r'(?:the\s+)?(\w+(?:\s+\w+)?)', clean_title, re.IGNORECASE)
            query_search = match.group(1) if match else clean_title
        query_search = " ".join(query_search.split()[:2])
        params = {
            'query': query_search,
            'startDate': datetime.datetime.today().isoformat(),
            'endDate': (datetime.datetime.today().date() + datetime.timedelta(days=90)).isoformat()
        }
        response = client.get(f'{api_url}/{token}/events', headers=headers, params=params)
        if response:
            teamup_data = response.json().get('events', [])
            dub_list = []
            re_ep = re.compile(r"<strong>episode:</strong>\s*(\d+)", re.IGNORECASE)
            re_mal = re.compile(r"mal:\s*(\d+)", re.IGNORECASE)
            for teamup_dat in teamup_data:
                title = teamup_dat['title']
                end_dt = teamup_dat["end_dt"]
                notes = teamup_dat.get('notes', '')

                # Check MAL ID match if available
                mal_id_match = re_mal.search(notes) if notes else None
                teamup_mal_id = int(mal_id_match.group(1)) if mal_id_match else None
                if teamup_mal_id and mal_id and teamup_mal_id != mal_id:
                    continue

                # Try to extract episode from notes first
                episode_match = re_ep.search(notes) if notes else None
                episode = [int(episode_match.group(1))] if episode_match else None

                if mal_id and episode:
                    season = 0
                else:
                    episode, season = match_episode(title)

                if episode:
                    # More than one episode in teamup_dat
                    if len(episode) == 2:
                        ep_number1, ep_number2 = episode
                        try:
                            dub_time = datetime.datetime.strptime(end_dt, '%Y-%m-%dT%H:%M:%S%z')
                        except (ValueError, TypeError):
                            try:
                                control.log('Unsupported strptime format, using fromtimestamp', 'warning')
                                dub_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(end_dt[:16], '%Y-%m-%dT%H:%M')))
                            except:
                                continue
                        dub_time = str(dub_time.astimezone())[:16] if hasattr(dub_time, 'astimezone') else str(dub_time - datetime.timedelta(hours=5))[:16]
                        dub_list = [{"season": season, "episode": f'{i}', "release_time": dub_time} for i in range(int(ep_number1), int(ep_number2) + 1)]
                    # Only one episode in teamup_dat
                    elif len(episode) == 1:
                        ep_number = episode[0]
                        try:
                            dub_time = datetime.datetime.strptime(end_dt, '%Y-%m-%dT%H:%M:%S%z')
                        except (ValueError, TypeError):
                            try:
                                control.log('Unsupported strptime format, using fromtimestamp', 'warning')
                                dub_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(end_dt[:16], '%Y-%m-%dT%H:%M')))
                            except:
                                continue
                        dub_time = str(dub_time.astimezone())[:16] if hasattr(dub_time, 'astimezone') else str(dub_time - datetime.timedelta(hours=5))[:16]
                        dub_list.append({"season": season, "episode": ep_number, "release_time": dub_time})
            return dub_list
    return None


def match_episode(item) -> tuple:
    match = re.search(r"#?(\d+)(?:-(\d+))?", item)
    if match:
        episode_number = (int(match.group(1)), int(match.group(2))) if match.group(2) else (int(match.group(1)),)
        season_number_match = re.search(r"Season (\d+)", item)
        season_number = int(season_number_match.group(1)) if season_number_match else 0
    else:
        episode_number = None
        season_number = None
    return episode_number, season_number
