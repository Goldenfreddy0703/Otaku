import sys
import xbmc

def main():
    arg = sys.argv[1]
    item = sys.listitem
    path = item.getPath()
    plugin = 'plugin://plugin.video.otaku'
    if arg == 'findrecommendations':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin('ActivateWindow(Videos,%s/find_recommendations/%s)' % (plugin, path))
    elif arg == 'findrelations':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin('ActivateWindow(Videos,%s/find_relations/%s)' % (plugin, path))
    elif arg == 'getwatchorder':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin('ActivateWindow(Videos,%s/watch_order/%s)' % (plugin, path))
    elif arg == 'rescrape':
        resume_time = item.getVideoInfoTag().getResumeTime()
        path += "?rescrape=true"
        if resume_time > 0:
            path += "&resume=%s" % resume_time
        xbmc.executebuiltin('PlayMedia(%s)' % path)
    elif arg == 'sourceselect':
        resume_time = item.getVideoInfoTag().getResumeTime()
        path += '?source_select=true'
        if resume_time > 0:
            path += "&resume=%s" % resume_time
        xbmc.executebuiltin('PlayMedia(%s)' % path)
    elif arg == 'logout':
        path = path.split('%s/watchlist' % plugin, 1)[1]
        xbmc.executebuiltin('RunPlugin(%s/watchlist_logout%s)' % (plugin, path))
    elif arg == 'deletefromdatabase':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin('RunPlugin(%s/delete_anime_database%s)' % (plugin, path))
    elif arg == 'watchlist':
        path = path.split(plugin, 1)[1]
        xbmc.executebuiltin('RunPlugin(%s/watchlist_manager/%s)' % (plugin, path))
    elif arg == 'markedaswatched':
        path = path.split('%s/play' % plugin, 1)[1]
        xbmc.executebuiltin('RunPlugin(%s/marked_as_watched/%s)' % (plugin, path))
    else:
        raise KeyError("Could Not find %s in Context Menu Action" % arg)


if __name__ == "__main__":
    main()
