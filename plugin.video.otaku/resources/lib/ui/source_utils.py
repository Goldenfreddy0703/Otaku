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
    
    if control.getSetting('consistent.torrentInspection') == 'false':
        prioritize_season = control.getSetting("menu.prioritize_season")
        prioritize_part = control.getSetting("menu.prioritize_part")
        prioritize_episode = control.getSetting("menu.prioritize_episode")

    else:
        prioritize_season = control.getSetting("consistent.prioritize_season")
        prioritize_part = control.getSetting("consistent.prioritize_part")
        prioritize_episode = control.getSetting("consistent.prioritize_episode")

    # info.season
    if any(i.format(prioritize_season) in release_title for i in ['season {}', 'season 0{}', 'season{}', 'season0{}', 's{}', 's0{}']):
        info.append('SEASON')

    # info.part
    if any(i.format(prioritize_part) in release_title for i in ['part {}', 'part 0{}', 'cour {}', 'cour 0{}', 'part{}', 'part0{}', 'cour{}', 'cour0{}']):
        info.append('PART')

    # info.episode
    if any(i.format(prioritize_episode) in release_title for i in ['episode {}', 'episode 0{}', 'ep {}', 'ep 0{}','episode{}', 'episode0{}', 'ep{}', 'ep0{}', 'e{}', 'e0{}']):
        info.append('EPISODE')

    # info.subtitles
    if any(i in release_title for i in ['multi-sub', 'multi sub', 'multiple subtitle']):
        info.append('MULTI-SUBS')

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
    if any(i in release_title for i in ['batch']):
        info.append('BATCH')

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
    if any(i in release_title for i in ['dual audio']):
        info.append('DUAL-AUDIO')

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


def get_best_match(dict_key, dictionary_list, episode):
    regex = get_cache_check_reg(episode)

    files = []
    for i in dictionary_list:
        path = re.sub(r'\[.*?\]', '', i[dict_key].split('/')[-1])
        i['regex_matches'] = regex.findall(path)
        files.append(i)

    if control.getSetting('general.manual.select') == 'true':
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
