import datetime
import re
import time

from bs4 import BeautifulSoup
from resources.lib.ui import client, database

base_url = "https://animeschedule.net/api/v3"
dub_list = []


def get_route(mal_id):
    params = {
        "mal-ids": mal_id
    }
    response = client.get(f"{base_url}/anime", params=params)
    if response:
        data = response.json()
        anime_list = data.get('anime', [])
        if anime_list:
            return anime_list[0].get('route', '')
    return ''


def get_dub_time(mal_id):
    show = database.get_show(mal_id)
    route = show['anime_schedule_route']
    if not route:
        route = get_route(mal_id)
        database.update_show(mal_id, show['kodi_meta'], route)
    response = client.get(f'https://animeschedule.net/anime/{route}')
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        soup_all = soup.find_all('div', class_='release-time-wrapper')
        for soup in soup_all:
            if 'dub:' in soup.text.lower():
                dub_soup = soup
                dub_text = dub_soup.span.text
                date_time = dub_soup.time.get('datetime')

                if '-' in dub_text:
                    match = re.match(r'Episodes (\d+)-(\d+)', dub_text)
                    if match:
                        ep_begin = int(match.group(1))
                        ep_end = int(match.group(2))
                        for ep_number in range(ep_begin, ep_end):
                            add_to_list(ep_number, date_time)
                else:
                    match = re.match(r'Episode (\d+)', dub_text)
                    if match:
                        ep_number = int(match.group(1))
                        add_to_list(ep_number, date_time)
                return dub_list


def add_to_list(ep_number, date_time):
    dub_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(date_time[:16], '%Y-%m-%dT%H:%M')))
    dub_time = str(dub_time - datetime.timedelta(hours=5))[:16]
    dub_list.append({"season": 0, "episode": ep_number, "release_time": dub_time})
