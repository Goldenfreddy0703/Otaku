import os
import re
from resources.lib.ui import control, client, database
from six import StringIO, iteritems
from kodi_six import xbmcvfs


def allocate_item(name, url, is_dir=False, image='', info='', fanart=None, poster=None, cast=[], landscape=None, banner=None, clearart=None, clearlogo=None):
    if image and '/' not in image:
        genre_image = os.path.join(control.genrePath(), image)
        art_image = os.path.join(control.artPath(), image)
        image = genre_image if os.path.exists(genre_image) else art_image
    if fanart and not isinstance(fanart, list) and '/' not in fanart:
        genre_fanart = os.path.join(control.genrePath(), fanart)
        art_fanart = os.path.join(control.artPath(), fanart)
        fanart = genre_fanart if os.path.exists(genre_fanart) else art_fanart
    if poster and '/' not in poster:
        genre_poster = os.path.join(control.genrePath(), poster)
        art_poster = os.path.join(control.artPath(), poster)
        poster = genre_poster if os.path.exists(genre_poster) else art_poster
    new_res = {
        'is_dir': is_dir,
        'name': name,
        'url': url,
        'info': info,
        'cast': cast,
        'image': {
                'poster': poster or image,
                'icon': image,
                'thumb': image,
                'fanart': fanart,
                'landscape': landscape,
                'banner': banner,
                'clearart': clearart,
                'clearlogo': clearlogo
        }
    }
    return new_res


def get_sub(sub_url, sub_lang):
    content = client.request(sub_url)
    subtitle = control.TRANSLATEPATH('special://temp/')
    fname = 'TemporarySubs.{0}.srt'.format(sub_lang)
    fpath = os.path.join(subtitle, fname)
    if sub_url.endswith('.vtt'):
        if control._kodiver > 19.8:
            fname = fname.replace('.srt', '.vtt')
            fpath = fpath.replace('.srt', '.vtt')
        else:
            replacement = re.sub(r'([\d]+)\.([\d]+)', r'\1,\2', content)
            replacement = re.sub(r'WEBVTT\n\n', '', replacement)
            replacement = re.sub(r'^\d+\n', '', replacement)
            replacement = re.sub(r'\n\d+\n', '\n', replacement)
            replacement = StringIO(replacement)
            idx = 1
            content = ''
            for line in replacement:
                if '-->' in line:
                    if len(line.split(' --> ')[0]) < 12:
                        line = re.sub(
                            r'([\d]+):([\d]+),([\d]+)', r'00:\1:\2,\3', line)
                    content += '%s\n%s' % (idx, line)
                    idx += 1
                else:
                    content += line

    if control.PY3:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        with open(fpath, 'w') as f:
            f.write(content.encode('utf8'))

    return 'special://temp/' + fname


def del_subs():
    dirs, files = xbmcvfs.listdir('special://temp/')
    for fname in files:
        if fname.startswith('TemporarySubs'):
            xbmcvfs.delete('special://temp/' + fname)
    return


def get_season(res):
    regexes = [r'season\s(\d+)', r'\s(\d+)st\sseason(?:\s|$)', r'\s(\d+)nd\sseason(?:\s|$)',
               r'\s(\d+)rd\sseason(?:\s|$)', r'\s(\d+)th\sseason(?:\s|$)']
    s_ids = []
    for regex in regexes:
        if isinstance(res.get('title'), dict):
            s_ids += [re.findall(regex, name, re.IGNORECASE) for lang, name in iteritems(res.get('title')) if name is not None]
        else:
            s_ids += [re.findall(regex, name, re.IGNORECASE) for name in res.get('title')]
        s_ids += [re.findall(regex, name, re.IGNORECASE) for name in res.get('synonyms')]
    s_ids = [s[0] for s in s_ids if s]
    if not s_ids:
        regex = r'\s(\d+)$'
        cour = False
        if isinstance(res.get('title'), dict):
            for lang, name in iteritems(res.get('title')):
                if name is not None and (' part ' in name.lower() or ' cour ' in name.lower()):
                    cour = True
                    break
            if not cour:
                s_ids += [re.findall(regex, name, re.IGNORECASE) for lang, name in iteritems(res.get('title')) if name is not None]
                s_ids += [re.findall(regex, name, re.IGNORECASE) for name in res.get('synonyms')]
        else:
            for name in res.get('title'):
                if ' part ' in name.lower() or ' cour ' in name.lower():
                    cour = True
                    break
            if not cour:
                s_ids += [re.findall(regex, name, re.IGNORECASE) for name in res.get('title')]
                s_ids += [re.findall(regex, name, re.IGNORECASE) for name in res.get('synonyms')]
        s_ids = [s[0] for s in s_ids if s and int(s[0]) < 20]

    return s_ids


def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


def get_unique_ids(anilist_id):
    unique_ids = database.get_all_ids(anilist_id)

    if 'imdb' not in list(unique_ids.keys()):
        if unique_ids.get('tvdb'):
            from resources.lib.indexers.tvdb import TVDBAPI
            imdb_id = TVDBAPI().get_imdb_id(unique_ids.get('tvdb'))
            if imdb_id:
                unique_ids.update({'imdb': imdb_id})

    if 'imdb' not in list(unique_ids.keys()):
        if unique_ids.get('tmdb'):
            from resources.lib.indexers.tmdb import TMDBAPI
            imdb_id = TMDBAPI().get_imdb_id(unique_ids.get('tmdb'))
            if imdb_id:
                unique_ids.update({'imdb': imdb_id})

    return unique_ids
