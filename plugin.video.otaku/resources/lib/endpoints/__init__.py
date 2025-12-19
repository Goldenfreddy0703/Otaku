from resources.lib.ui import control


def get_second_label(info, dub_data, filler=None):
    if control.getBool('jz.filler') and filler:
        return filler

    code_dub = code_sub = code = None

    # if ani_data:
    #     episode_schedule = ani_data['airingSchedule']['nodes']
    #     if len(episode_schedule) != 0:
    #         from datetime import datetime
    #         for ep_sched in episode_schedule:
    #             if ep_sched['episode'] == episode:
    #                 # info['title'] = control.colorString(info['title'], color="red")
    #                 code_sub = f'{datetime.fromtimestamp(ep_sched["airingAt"])}'[:-3]

    if dub_data:
        episode = info['episode']
        for dub_dat in dub_data:
            season = int(info['season'])
            if (int(dub_dat['season']) == season or dub_dat['season'] == 0) and int(dub_dat['episode']) == episode:
                code_dub = dub_dat["release_time"]

    if code_dub and code_sub:
        code = f'Sub {code_sub} / Dub {code_dub}'
    elif code_dub:
        code = f'Dub {code_dub}'
    elif code_sub:
        code = code_sub
    return code
