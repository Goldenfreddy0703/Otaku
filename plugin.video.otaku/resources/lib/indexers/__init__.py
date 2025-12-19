import pickle

from datetime import date
from functools import partial
from resources.lib import endpoints
from resources.lib.ui import database, control, utils


def parse_episodes(res, eps_watched, dub_data=None):
    parsed = pickle.loads(res['kodi_meta'])
    if eps_watched and int(eps_watched) >= res['number']:
        parsed['info']['playcount'] = 1
    if control.getBool('interface.cleantitles') and parsed['info'].get('playcount') != 1:
        parsed['info']['title'] = f'Episode {res["number"]}'
        parsed['info']['plot'] = None
    code = endpoints.get_second_label(parsed['info'], dub_data, res['filler'])
    parsed['info']['code'] = code
    return parsed


def process_episodes(episodes, eps_watched, dub_data=None):
    mapfunc = partial(parse_episodes, eps_watched=eps_watched, dub_data=dub_data)
    # Parallelize episode parsing for faster processing
    all_results = utils.parallel_process(episodes, mapfunc, max_workers=8)
    return all_results


def process_dub(mal_id, ename):
    update_time = date.today().isoformat()
    if not (show_data := database.get_show_data(mal_id)) or show_data['last_updated'] != update_time:
        if control.getInt('jz.dub.api') == 0:
            from resources.lib.endpoints import teamup
            dub_data = teamup.get_dub_data(ename)
            data = {"dub_data": dub_data}
            database.update_show_data(mal_id, data, update_time)
        else:
            from resources.lib.endpoints import animeschedule
            dub_data = animeschedule.get_dub_time(mal_id)
            data = {"dub_data": dub_data}
            database.update_show_data(mal_id, data, update_time)
    else:
        dub_data = pickle.loads(show_data['data'])['dub_data']
    return dub_data


def get_diff(episodes_0):
    import datetime
    update_time = datetime.date.today().isoformat()
    try:
        last_updated = datetime.datetime.strptime(episodes_0.get('last_updated'), "%Y-%m-%d")
    except:
        import time
        control.log('Unsupported strptime using fromtimestamp', 'warning')
        last_updated = datetime.datetime.fromtimestamp(time.mktime(time.strptime(episodes_0.get('last_updated'), '%Y-%m-%d')))
    diff = (datetime.datetime.today() - last_updated).days
    return update_time, diff


def should_hide_unaired_episode(aired_date_str):
    """
    Check if an episode should be hidden based on aired date and interface.aired_episodes setting.
    Returns True if episode is unaired and should be hidden, False otherwise.
    """
    import datetime
    if not control.getBool('interface.aired_episodes'):
        return False
    
    if not aired_date_str:
        return False
    
    try:
        # Parse the aired date with fallback for compatibility
        try:
            aired_date = datetime.datetime.strptime(aired_date_str[:10], '%Y-%m-%d')
        except:
            import time
            aired_date = datetime.datetime.fromtimestamp(time.mktime(time.strptime(aired_date_str[:10], '%Y-%m-%d')))
        
        today = datetime.datetime.now()
        return aired_date > today
    except (ValueError, TypeError, AttributeError, Exception):
        # If date parsing fails, show the episode anyway
        return False


def update_database(mal_id, update_time, res, url, image, info, season, episode, episodes, title, fanart, poster, clearart, clearlogo, dub_data, filler, anidb_ep_id=None):
    code = endpoints.get_second_label(info, dub_data)
    if not code and control.getBool('jz.filler'):
        filler = code = control.colorstr(filler, color="red") if filler == 'Filler' else filler
    info['code'] = code
    landscape = None
    banner = None

    parsed = utils.allocate_item(title, f"play/{url}", False, True, [], image, info, fanart, poster, landscape, banner, clearart, clearlogo)
    kodi_meta = pickle.dumps(parsed)
    if not episodes or len(episodes) <= episode or kodi_meta != episodes[episode - 1]['kodi_meta']:
        database.update_episode(mal_id, season, episode, update_time, kodi_meta, filler, anidb_ep_id)

    if control.getBool('interface.cleantitles') and info.get('playcount') != 1:
        parsed['info']['title'] = f'Episode {res["episode"]}'
        parsed['info']['plot'] = None
    return parsed
