import re
import string
from resources.lib.ui import control
from kodi_six import xbmc


def strip_non_ascii_and_unprintable(text):
    result = ''.join(char for char in text if char in string.printable)
    return result.encode('ascii', errors='ignore').decode('ascii', errors='ignore')


def getAudio_lang(release_title):
    lang = 0
    release_title = cleanTitle(release_title)
    if any(i in release_title for i in ['dual audio']):
        lang = 1
    if any(i in release_title for i in ['dub', 'dubbed']):
        lang = 2

    return lang


def getQuality(release_title):
    release_title = release_title.lower()
    quality = 'NA'
    if '4k' in release_title or '2160' in release_title:
        quality = '4K'
    if '1080' in release_title:
        quality = '1080p'
    if '720' in release_title:
        quality = '720p'
    if '480' in release_title:
        quality = 'NA'

    return quality


def getInfo(release_title):
    info = []
    release_title = cleanTitle(release_title)

    prioritize_season_value = ''
    prioritize_part_value = ''
    prioritize_episode_value = ''
    
    prioritize_dualaudio = False
    prioritize_multisubs = False
    prioritize_batches = False
    prioritize_season = False
    prioritize_part = False
    prioritize_episode = False 
    prioritize_consistently = False

    # info.video
    if any(i in release_title for i in ['x264', 'x 264', 'h264', 'h 264', 'avc']):
        info.append('AVC')
    if any(i in release_title for i in ['x265', 'x 265', 'h265', 'h 265', 'hevc']):
        info.append('HEVC')
    if any(i in release_title for i in ['xvid']):
        info.append('XVID')
    if any(i in release_title for i in ['divx']):
        info.append('DIVX')
    if any(i in release_title for i in ['mp4']):
        info.append('MP4')
    if any(i in release_title for i in ['wmv']):
        info.append('WMV')
    if any(i in release_title for i in ['mpeg']):
        info.append('MPEG')
    if any(i in release_title for i in ['remux', 'bdremux']):
        info.append('REMUX')
    if any(i in release_title for i in [' hdr ', 'hdr10', 'hdr 10']):
        info.append('HDR')
    if any(i in release_title for i in [' sdr ']):
        info.append('SDR')

    # info.audio
    if any(i in release_title for i in ['aac']):
        info.append('AAC')
    if any(i in release_title for i in ['dts']):
        info.append('DTS')
    if any(i in release_title for i in ['hd ma', 'hdma']):
        info.append('HD-MA')
    if any(i in release_title for i in ['atmos']):
        info.append('ATMOS')
    if any(i in release_title for i in ['truehd', 'true hd']):
        info.append('TRUEHD')
    if any(i in release_title for i in ['ddp', 'dd+', 'eac3']):
        info.append('DD+')
    if any(i in release_title for i in [' dd ', 'dd2', 'dd5', 'dd7', ' ac3']):
        info.append('DD')
    if any(i in release_title for i in ['mp3']):
        info.append('MP3')
    if any(i in release_title for i in [' wma']):
        info.append('WMA')
    if any(i in release_title for i in ['dub', 'dubbed']):
        info.append('DUB')

    # info.channels
    if any(i in release_title for i in ['2 0 ', '2 0ch', '2ch']):
        info.append('2.0')
    if any(i in release_title for i in ['5 1 ', '5 1ch', '6ch']):
        info.append('5.1')
    if any(i in release_title for i in ['7 1 ', '7 1ch', '8ch']):
        info.append('7.1')

    # info.source
    # no point at all with WEBRip vs WEB-DL cuz it's always labeled wrong with TV Shows
    # WEB = WEB-DL in terms of size and quality
    if any(i in release_title for i in ['bluray', 'blu ray', 'bdrip', 'bd rip', 'brrip', 'br rip']):
        info.append('BLURAY')
    if any(i in release_title for i in [' web ', 'webrip', 'webdl', 'web rip', 'web dl']):
        info.append('WEB')
    if any(i in release_title for i in ['hdrip', 'hd rip']):
        info.append('HDRIP')
    if any(i in release_title for i in ['dvdrip', 'dvd rip']):
        info.append('DVDRIP')
    if any(i in release_title for i in ['hdtv']):
        info.append('HDTV')
    if any(i in release_title for i in ['pdtv']):
        info.append('PDTV')
    if any(i in release_title for i in [' cam ', 'camrip', 'hdcam', 'hd cam', ' ts ', 'hd ts', 'hdts', 'telesync', ' tc ', 'hd tc', 'hdtc', 'telecine', 'xbet']):
        info.append('CAM')
    if any(i in release_title for i in ['dvdscr', ' scr ', 'screener']):
        info.append('SCR')
    if any(i in release_title for i in ['korsub', ' kor ', ' hc']):
        info.append('HC')
    if any(i in release_title for i in ['blurred']):
        info.append('BLUR')
    if any(i in release_title for i in [' 3d']):
        info.append('3D')

    if control.getSetting('general.sortsources') == '0':  # Torrents selected
        prioritize_dualaudio = control.getSetting('general.prioritize_dualaudio') == 'true'
        prioritize_multisubs = control.getSetting('general.prioritize_multisubs') == 'true'
        prioritize_batches = control.getSetting('general.prioritize_batches') == 'true'
        prioritize_consistently = control.getSetting('consistent.torrentInspection') == 'true'

        if prioritize_consistently:
            prioritize_season = control.getSetting('consistent.prioritize_season') == 'true'
            prioritize_part = control.getSetting('consistent.prioritize_part') == 'true'
            prioritize_episode = control.getSetting('consistent.prioritize_episode') == 'true'
        else:
            prioritize_season = control.getSetting('general.prioritize_season') == 'true'
            prioritize_part = control.getSetting('general.prioritize_part') == 'true'
            prioritize_episode = control.getSetting('general.prioritize_episode') == 'true'

        if not (prioritize_dualaudio or prioritize_multisubs or prioritize_batches or prioritize_season or prioritize_part or prioritize_episode):
            return info
    
        from itertools import chain, combinations
    
        # Define the order of the keys
        key_order = ['SEASON', 'PART', 'EPISODE', 'DUAL-AUDIO', 'MULTI-SUBS', 'BATCH']
    
        # Define the user's selected priorities
        selected_priorities = [prioritize_season, prioritize_part, prioritize_episode, prioritize_dualaudio, prioritize_multisubs, prioritize_batches]
        
        # Generate all possible combinations of the selected priorities
        selected_combinations = list(chain(*map(lambda x: combinations([key for key, selected in zip(key_order, selected_priorities) if selected], x), range(0, len(selected_priorities)+1))))

        # Initialize keyword as an empty list
        keyword = []
        
        for combination in selected_combinations:
            # Skip the empty combination
            if not combination:
                continue
        
            # Join the keys in the combination with '_OR_' and append to the keyword list
            keyword.append('_OR_'.join(combination))
        
        # Keep only the last combination in the keyword list
        keyword = [keyword[-1]] if keyword else []
        
        # Convert the keyword list to a string
        keyword = ' '.join(keyword) if keyword else ''

        if prioritize_consistently:
            prioritize_season_value = control.getSetting('consistent.prioritize_season_value')
            prioritize_part_value = control.getSetting('consistent.prioritize_part_value')
            prioritize_episode_value = control.getSetting('consistent.prioritize_episode_value')
        else:
            prioritize_season_value = control.getSetting('menu.prioritize_season_value')
            prioritize_part_value = control.getSetting('menu.prioritize_part_value')
            prioritize_episode_value = control.getSetting('menu.prioritize_episode_value')

        # Check if '_OR_' is in the keyword
        if '_OR_' in keyword:
            # Split the keyword into individual terms
            terms = keyword.split('_OR_')
            # Define the formats for each term
            term_formats = {
                'SEASON': ['season {}'.format(prioritize_season_value), 'season 0{}'.format(prioritize_season_value), 's{}'.format(prioritize_season_value), 's0{}'.format(prioritize_season_value)],
                'PART': ['part {}'.format(prioritize_part_value), 'part 0{}'.format(prioritize_part_value), 'cour {}'.format(prioritize_part_value), 'cour 0{}'.format(prioritize_part_value), 'part{}'.format(prioritize_part_value), 'part0{}'.format(prioritize_part_value), 'cour{}'.format(prioritize_part_value), 'cour0{}'.format(prioritize_part_value)],
                'EPISODE': ['episode {}'.format(prioritize_episode_value), 'episode 0{}'.format(prioritize_episode_value), 'ep {}'.format(prioritize_episode_value), 'ep 0{}'.format(prioritize_episode_value), 'episode{}'.format(prioritize_episode_value), 'episode0{}'.format(prioritize_episode_value), 'ep{}'.format(prioritize_episode_value), 'ep0{}'.format(prioritize_episode_value), 'e{}'.format(prioritize_episode_value), 'e0{}'.format(prioritize_episode_value)],
                'DUAL-AUDIO': ['dual audio'],
                'MULTI-SUBS': ['multi-sub', 'multi sub', 'multiple subtitle'],
                'BATCH': ['batch']
            }
            # Define the variables for each term
            term_variables = {
                'SEASON': str(prioritize_season_value),
                'PART': str(prioritize_part_value),
                'EPISODE': str(prioritize_episode_value)
            }

            # Create a new dictionary that only contains the keys that are in terms
            filtered_term_formats = {term: term_formats[term] for term in terms if term in term_formats}

            # Flatten the dictionary into a list
            flat_filtered_term_formats = [format_string for format_strings in filtered_term_formats.values() for format_string in format_strings]

            # Create a new list that only contains the values of the keys that are in terms
            filtered_term_variables_values = [term_variables[term] for term in terms if term in term_variables]

            # Join the list into a single string with a comma as a separator
            filtered_term_variables_string = ','.join(filtered_term_variables_values)

            # Check if all terms exist in the release_title and append the keyword to info
            if sum(i.format(filtered_term_variables_string) in release_title for i in flat_filtered_term_formats) >= len(terms):
                info.append(keyword)

        else:
            if keyword == None:
                pass
            else:
                # Define the keyword as the only term
                term = keyword
                # Define the formats for each term
                term_formats = {
                    'SEASON': ['season {}'.format(prioritize_season_value), 'season 0{}'.format(prioritize_season_value), 's{}'.format(prioritize_season_value), 's0{}'.format(prioritize_season_value)],
                    'PART': ['part {}'.format(prioritize_part_value), 'part 0{}'.format(prioritize_part_value), 'cour {}'.format(prioritize_part_value), 'cour 0{}'.format(prioritize_part_value), 'part{}'.format(prioritize_part_value), 'part0{}'.format(prioritize_part_value), 'cour{}'.format(prioritize_part_value), 'cour0{}'.format(prioritize_part_value)],
                    'EPISODE': ['episode {}'.format(prioritize_episode_value), 'episode 0{}'.format(prioritize_episode_value), 'ep {}'.format(prioritize_episode_value), 'ep 0{}'.format(prioritize_episode_value), 'episode{}'.format(prioritize_episode_value), 'episode0{}'.format(prioritize_episode_value), 'ep{}'.format(prioritize_episode_value), 'ep0{}'.format(prioritize_episode_value), 'e{}'.format(prioritize_episode_value), 'e0{}'.format(prioritize_episode_value)],
                    'DUAL-AUDIO': ['dual audio'],
                    'MULTI-SUBS': ['multi-sub', 'multi sub', 'multiple subtitle'],
                    'BATCH': ['batch']
                }
                # Define the variables for each term
                term_variables = {
                    'SEASON': str(prioritize_season_value),
                    'PART': str(prioritize_part_value),
                    'EPISODE': str(prioritize_episode_value),
                }

                # Create a new dictionary that only contains the keys that are in term
                filtered_term_formats = term_formats[term]

                if keyword == 'SEASON' or keyword == 'PART' or keyword == 'EPISODE':
                    # Create a new list that only contains the values of the keys that are in term
                    filtered_term_variables_values = term_variables[term]

                    # Join the list into a single string with a comma as a separator
                    filtered_term_variables_string = ','.join(filtered_term_variables_values)

                    # Check if any term exist in the release_title and append the keyword to info
                    if any(i.format(filtered_term_variables_string) in release_title for i in filtered_term_formats):
                        info.append(keyword)

                else:
                    if any(i in release_title for i in filtered_term_formats):
                        info.append(keyword)

    return info


def get_cache_check_reg(episode):
    try:
        playList = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        info = playList[playList.getposition()].getVideoInfoTag()
        season = str(info.getSeason()).zfill(2)
    except:
        season = ''

    reg_string = r'''(?ix)                              # Ignore case (i), and use verbose regex (x)
                 (?:                                    # non-grouping pattern
                   s|season                             # s or season
                   )?
                 ({})?                                  #season num format
                 (?:                                    # non-grouping pattern
                   e|x|episode|ep|ep\.|_|-|\(              # e or x or episode or start of a line
                   )                                    # end non-grouping pattern
                 \s*                                    # 0-or-more whitespaces
                 (?<![\d])
                 ({}|{})                                # episode num format: xx or xxx
                 (?![\d])
                 '''.format(season, episode.zfill(2), episode.zfill(3))

    return re.compile(reg_string)


def get_best_match(dict_key, dictionary_list, episode, pack_select=False):
    regex = get_cache_check_reg(episode)

    files = []
    for i in dictionary_list:
        path = re.sub(r'\[.*?\]', '', i[dict_key].split('/')[-1])
        i['regex_matches'] = regex.findall(path)
        files.append(i)

    if control.getSetting('general.manual.select') == 'true' or pack_select:
        files = user_select(files, dict_key)
    else:
        files = [i for i in files if len(i['regex_matches']) > 0]

        if len(files) == 0:
            return None

        files = sorted(files, key=lambda x: len(' '.join(list(x['regex_matches'][0]))), reverse=True)

        if len(files) != 1:
            files = user_select(files, dict_key)

    return files[0]


def cleanTitle(title):
    title = clean_title(title)
    return title


def clean_title(title, broken=None):
    title = title.lower()
    # title = tools.deaccentString(title)
    title = strip_non_ascii_and_unprintable(title)

    if broken == 1:
        apostrophe_replacement = ''
    elif broken == 2:
        apostrophe_replacement = ' s'
    else:
        apostrophe_replacement = 's'
    title = title.replace("\\'s", apostrophe_replacement)
    title = title.replace("'s", apostrophe_replacement)
    title = title.replace("&#039;s", apostrophe_replacement)
    title = title.replace(" 039 s", apostrophe_replacement)

    title = re.sub(r'\:|\\|\/|\,|\!|\?|\(|\)|\'|\"|\\|\[|\]|\-|\_|\.', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    title = re.sub(r'\&', 'and', title)

    return title.strip()


def is_file_ext_valid(file_name):
    try:
        COMMON_VIDEO_EXTENSIONS = xbmc.getSupportedMedia('video').split('|')

        COMMON_VIDEO_EXTENSIONS = [i for i in COMMON_VIDEO_EXTENSIONS if i != '' and i != '.zip']
    except:
        pass

    if '.' + file_name.split('.')[-1] not in COMMON_VIDEO_EXTENSIONS:
        return False

    return True


def filter_single_episode(episode, release_title):
    filename = re.sub(r'\[.*?\]', '', release_title)
    filename = filename.lower()

    try:
        playList = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        info = playList[playList.getposition()].getVideoInfoTag()
        season = str(info.getSeason()).zfill(2)
        season = 's' + season
    except:
        season = ''

    filter_episode = [
        '%se%s' % (season, episode.zfill(3)),
        '%se%s' % (season, episode.zfill(2)),
        episode.zfill(3),
        episode.zfill(2)
    ]

    if next((string for string in filter_episode if string in filename), False):
        return True

    return False

# def run_once(f):
#     def wrapper(*args, **kwargs):
#         if not wrapper.has_run:
#             wrapper.has_run = True
#             return f(*args, **kwargs)
#     wrapper.has_run = False
#     return wrapper

# @run_once


def user_select(files, dict_key):
    idx = control.select_dialog('Select File', [i[dict_key].rsplit('/')[-1] for i in files])
    if idx == -1:
        file = [{'path': ''}]
    else:
        file = [files[idx]]
    return file


def get_embedhost(url):
    s = re.search(r'(?://|\.)([^\.]+)\.', url)
    return s.group(1)
