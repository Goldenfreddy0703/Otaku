import sys
import xbmc
import xbmcgui
from urllib import parse


def get_video_info(li: xbmcgui.ListItem) -> dict:
    params = {}
    vinfo: xbmc.InfoTagVideo = li.getVideoInfoTag()
    # Meta Data
    if title := vinfo.getTitle():
        params['title'] = title
    if mediatype := vinfo.getMediaType():
        params['mediatype'] = mediatype
    if tvshow_title := vinfo.getTVShowTitle():
        params['tvshowtitle'] = tvshow_title
    if plot := vinfo.getPlot():
        params['plot'] = plot
    if year := vinfo.getYear():
        params['year'] = str(year)
    if premiered := vinfo.getPremieredAsW3C():
        params['premiered'] = premiered
    if season := vinfo.getSeason():
        params['season'] = str(season)
    if episode := vinfo.getEpisode():
        params['episode'] = str(episode)
    if aired := vinfo.getFirstAiredAsW3C():
        params['aired'] = aired
    if rating := vinfo.getRating():
        params['rating'] = {'score': rating, 'votes': 0}  # Assuming votes are not available
    if resume := vinfo.getResumeTime():
        params['resume'] = str(resume)

    # Artwork
    if poster := li.getArt('poster'):
        params['poster'] = poster
    if tvshowposter := li.getArt('tvshow.poster'):
        params['tvshow.poster'] = tvshowposter
    if icon := li.getArt('icon'):
        params['icon'] = icon
    if thumb := li.getArt('thumb'):
        params['thumb'] = thumb
    if fanart := li.getArt('fanart'):
        params['fanart'] = fanart
    if landscape := li.getArt('landscape'):
        params['landscape'] = landscape
    if banner := li.getArt('banner'):
        params['banner'] = banner
    if clearart := li.getArt('clearart'):
        params['clearart'] = clearart
    if clearlogo := li.getArt('clearlogo'):
        params['clearlogo'] = clearlogo

    return params


def main():
    arg = sys.argv[1]
    item = sys.listitem
    path = item.getPath()
    plugin = 'plugin://plugin.video.otaku'
    if arg == 'findrecommendations':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/find_recommendations{path})")
    elif arg == 'findrelations':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/find_relations{path})")
    elif arg == 'getwatchorder':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/watch_order{path})")
    elif arg == 'viewreviews':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/anime_reviews{path})")
    elif arg == 'viewstatistics':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/anime_statistics{path})")
    elif arg == 'rescrape':
        params = get_video_info(item)
        params['rescrape'] = 'true'
        path = f"{path}?{parse.urlencode(params)}"
        xbmc.executebuiltin(f"PlayMedia({path})")
    elif arg == 'sourceselect':
        params = get_video_info(item)
        params['source_select'] = 'true'
        path = f"{path}?{parse.urlencode(params)}"
        xbmc.executebuiltin(f"PlayMedia({path})")
    elif arg == 'logout':
        path = path.split(f'{plugin}/watchlist', 1)[1]
        xbmc.executebuiltin(f"RunPlugin({plugin}/watchlist_logout{path})")
    elif arg == 'deletefromdatabase':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"RunPlugin({plugin}/delete_anime_database{path})")
    elif arg == 'watchlist':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"RunPlugin({plugin}/watchlist_manager{path})")
    elif arg == 'markedaswatched':
        path = path.split(f'{plugin}/play', 1)[1]
        xbmc.executebuiltin(f"RunPlugin({plugin}/marked_as_watched{path})")
    elif arg == 'fanartselect':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin(f"Container.Update({plugin}/fanart_select{path})")
    else:
        raise KeyError("Could Not find %s in Context Menu Action" % arg)


if __name__ == "__main__":
    main()
