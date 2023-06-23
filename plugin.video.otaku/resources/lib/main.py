# -*- coding: utf-8 -*-
"""
    Otaku Add-on

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import pickle
import six
from resources.lib.AniListBrowser import AniListBrowser
from resources.lib.OtakuBrowser import OtakuBrowser
from resources.lib.ui import control, database, player, utils
from resources.lib.ui.router import route, router_process
from resources.lib.WatchlistIntegration import (add_watchlist, set_browser,
                                                watchlist_append,
                                                watchlist_completed,
                                                watchlist_remove,
                                                watchlist_update)

MENU_ITEMS = [
    (control.lang(50000), "anilist_airing", 'airing_anime_calendar.png'),
    (control.lang(50001), "anilist_airing_anime", 'airing_anime.png'),
    (control.lang(50002), "movies", 'movies.png'),
    (control.lang(50003), "tv_shows", 'tv_shows.png'),
    (control.lang(50004), "trending", 'trending.png'),
    (control.lang(50005), "popular", 'popular.png'),
    (control.lang(50006), "voted", 'voted.png'),
    (control.lang(50007), "completed", 'completed_01.png'),
    (control.lang(50008), "upcoming", 'upcoming.png'),
    (control.lang(50013), "anilist_trending_last_year", 'trending.png'),
    (control.lang(50014), "anilist_popular_last_year", 'popular.png'),
    (control.lang(50015), "anilist_voted_last_year", 'voted.png'),
    (control.lang(50016), "anilist_completed_last_year", 'completed_01.png'),
    (control.lang(50017), "anilist_upcoming_last_year", 'upcoming.png'),
    (control.lang(50018), "anilist_trending_this_year", 'trending.png'),
    (control.lang(50019), "anilist_popular_this_year", 'popular.png'),
    (control.lang(50020), "anilist_voted_this_year", 'voted.png'),
    (control.lang(50021), "anilist_completed_this_year", 'completed_01.png'),
    (control.lang(50022), "anilist_upcoming_this_year", 'upcoming.png'),
    (control.lang(50023), "anilist_upcoming_next_year", 'upcoming.png'),
    (control.lang(50024), "anilist_trending_last_season", 'trending.png'),
    (control.lang(50025), "anilist_popular_last_season", 'popular.png'),
    (control.lang(50026), "anilist_voted_last_season", 'voted.png'),
    (control.lang(50027), "anilist_completed_last_season", 'completed_01.png'),
    (control.lang(50028), "anilist_upcoming_last_season", 'upcoming.png'),
    (control.lang(50029), "anilist_trending_this_season", 'trending.png'),
    (control.lang(50030), "anilist_popular_this_season", 'popular.png'),
    (control.lang(50031), "anilist_voted_this_season", 'voted.png'),
    (control.lang(50032), "anilist_completed_this_season", 'completed_01.png'),
    (control.lang(50033), "anilist_upcoming_this_season", 'upcoming.png'),
    (control.lang(50034), "anilist_upcoming_next_season", 'upcoming.png'),
    (control.lang(50035), "anilist_all_time_trending", 'trending.png'),
    (control.lang(50036), "anilist_all_time_popular", 'popular.png'),
    (control.lang(50037), "anilist_all_time_voted", 'voted.png'),
    (control.lang(50009), "anilist_top_100_anime", 'top_100_anime.png'),
    (control.lang(50010), "anilist_genres", 'genres_&_tags.png'),
    (control.lang(50011), "search_history", 'search.png'),
    (control.lang(50012), "tools", 'tools.png'),
]
_TITLE_LANG = control.getSetting("titlelanguage")
_BROWSER = OtakuBrowser()
_ANILIST_BROWSER = AniListBrowser(_TITLE_LANG)

if control.ADDON_VERSION != control.getSetting('version'):
    database.cache_clear()
    database.torrent_cache_clear()
    showchangelog = control.getSetting("showchangelog")
    if showchangelog == "Yes":
        control.getChangeLog()
    control.setSetting('version', control.ADDON_VERSION)


@route('movies')
def MOVIES_MENU(payload, params):
    MOVIES_ITEMS = [
        (control.lang(50001), "anilist_airing_anime_movie", 'airing_anime.png'),
        (control.lang(50013), "anilist_trending_last_year_movie", 'trending.png'),
        (control.lang(50014), "anilist_popular_last_year_movie", 'popular.png'),
        (control.lang(50015), "anilist_voted_last_year_movie", 'voted.png'),
        (control.lang(50016), "anilist_completed_last_year_movie", 'completed_01.png'),
        (control.lang(50017), "anilist_upcoming_last_year_movie", 'upcoming.png'),
        (control.lang(50018), "anilist_trending_this_year_movie", 'trending.png'),
        (control.lang(50019), "anilist_popular_this_year_movie", 'popular.png'),
        (control.lang(50020), "anilist_voted_this_year_movie", 'voted.png'),
        (control.lang(50021), "anilist_completed_this_year_movie", 'completed_01.png'),
        (control.lang(50022), "anilist_upcoming_this_year_movie", 'upcoming.png'),
        (control.lang(50023), "anilist_upcoming_next_year_movie", 'upcoming.png'),
        (control.lang(50024), "anilist_trending_last_season_movie", 'trending.png'),
        (control.lang(50025), "anilist_popular_last_season_movie", 'popular.png'),
        (control.lang(50026), "anilist_voted_last_season_movie", 'voted.png'),
        (control.lang(50027), "anilist_completed_last_season_movie", 'completed_01.png'),
        (control.lang(50028), "anilist_upcoming_last_season_movie", 'upcoming.png'),
        (control.lang(50029), "anilist_trending_this_season_movie", 'trending.png'),
        (control.lang(50030), "anilist_popular_this_season_movie", 'popular.png'),
        (control.lang(50031), "anilist_voted_this_season_movie", 'voted.png'),
        (control.lang(50032), "anilist_completed_this_season_movie", 'completed_01.png'),
        (control.lang(50033), "anilist_upcoming_this_season_movie", 'upcoming.png'),
        (control.lang(50034), "anilist_upcoming_next_season_movie", 'upcoming.png'),
        (control.lang(50035), "anilist_all_time_trending_movie", 'trending.png'),
        (control.lang(50036), "anilist_all_time_popular_movie", 'popular.png'),
        (control.lang(50037), "anilist_all_time_voted_movie", 'voted.png'),
        (control.lang(50009), "anilist_top_100_anime_movie", 'top_100_anime.png'),
        (control.lang(50010), "anilist_genres", 'genres_&_tags.png'),
        (control.lang(50011), "search_history", 'search.png'),
    ]

    MOVIES_ITEMS_SETTINGS = MOVIES_ITEMS[:]
    for i in MOVIES_ITEMS:
        if control.getSetting(i[1]) != 'true':
            MOVIES_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in MOVIES_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('tv_shows')
def TV_SHOWS_MENU(payload, params):
    TV_SHOWS_ITEMS = [
        (control.lang(50001), "anilist_airing_anime_tv", 'airing_anime.png'),
        (control.lang(50013), "anilist_trending_last_year_tv", 'trending.png'),
        (control.lang(50014), "anilist_popular_last_year_tv", 'popular.png'),
        (control.lang(50015), "anilist_voted_last_year_tv", 'voted.png'),
        (control.lang(50016), "anilist_completed_last_year_tv", 'completed_01.png'),
        (control.lang(50017), "anilist_upcoming_last_year_tv", 'upcoming.png'),
        (control.lang(50018), "anilist_trending_this_year_tv", 'trending.png'),
        (control.lang(50019), "anilist_popular_this_year_tv", 'popular.png'),
        (control.lang(50020), "anilist_voted_this_year_tv", 'voted.png'),
        (control.lang(50021), "anilist_completed_this_year_tv", 'completed_01.png'),
        (control.lang(50022), "anilist_upcoming_this_year_tv", 'upcoming.png'),
        (control.lang(50023), "anilist_upcoming_next_year_tv", 'upcoming.png'),
        (control.lang(50024), "anilist_trending_last_season_tv", 'trending.png'),
        (control.lang(50025), "anilist_popular_last_season_tv", 'popular.png'),
        (control.lang(50026), "anilist_voted_last_season_tv", 'voted.png'),
        (control.lang(50027), "anilist_completed_last_season_tv", 'completed_01.png'),
        (control.lang(50028), "anilist_upcoming_last_season_tv", 'upcoming.png'),
        (control.lang(50029), "anilist_trending_this_season_tv", 'trending.png'),
        (control.lang(50030), "anilist_popular_this_season_tv", 'popular.png'),
        (control.lang(50031), "anilist_voted_this_season_tv", 'voted.png'),
        (control.lang(50032), "anilist_completed_this_season_tv", 'completed_01.png'),
        (control.lang(50033), "anilist_upcoming_this_season_tv", 'upcoming.png'),
        (control.lang(50034), "anilist_upcoming_next_season_tv", 'upcoming.png'),
        (control.lang(50035), "anilist_all_time_trending_tv", 'trending.png'),
        (control.lang(50036), "anilist_all_time_popular_tv", 'popular.png'),
        (control.lang(50037), "anilist_all_time_voted_tv", 'voted.png'),
        (control.lang(50009), "anilist_top_100_anime_tv", 'top_100_anime.png'),
        (control.lang(50010), "anilist_genres", 'genres_&_tags.png'),
        (control.lang(50011), "search_history", 'search.png'),
    ]

    TV_SHOWS_ITEMS_SETTINGS = TV_SHOWS_ITEMS[:]
    for i in TV_SHOWS_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TV_SHOWS_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TV_SHOWS_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('trending')
def TRENDING_MENU(payload, params):
    TRENDING_ITEMS = [
        (control.lang(50013), "anilist_trending_last_year_trending_trending", 'trending.png'),
        (control.lang(50018), "anilist_trending_this_year_trending_trending", 'trending.png'),
        (control.lang(50024), "anilist_trending_last_season_trending", 'trending.png'),
        (control.lang(50029), "anilist_trending_this_season_trending", 'trending.png'),
        (control.lang(50035), "anilist_all_time_trending_trending", 'trending.png'),
    ]

    TRENDING_ITEMS_SETTINGS = TRENDING_ITEMS[:]
    for i in TRENDING_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TRENDING_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TRENDING_ITEMS],
        contentType="addons",
        draw_cm=False
    )


@route('popular')
def POPULAR_MENU(payload, params):
    POPULAR_ITEMS = [
        (control.lang(50014), "anilist_popular_last_year_popular", 'popular.png'),
        (control.lang(50019), "anilist_popular_this_year_popular", 'popular.png'),
        (control.lang(50025), "anilist_popular_last_season_popular", 'popular.png'),
        (control.lang(50030), "anilist_popular_this_season_popular", 'popular.png'),
        (control.lang(50036), "anilist_all_time_popular_popular", 'popular.png'),
    ]

    POPULAR_ITEMS_SETTINGS = POPULAR_ITEMS[:]
    for i in POPULAR_ITEMS:
        if control.getSetting(i[1]) != 'true':
            POPULAR_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in POPULAR_ITEMS],
        contentType="addons",
        draw_cm=False
    )


@route('voted')
def VOTED_MENU(payload, params):
    VOTED_ITEMS = [
        (control.lang(50015), "anilist_voted_last_year_voted", 'voted.png'),
        (control.lang(50020), "anilist_voted_this_year_voted", 'voted.png'),
        (control.lang(50026), "anilist_voted_last_season_voted", 'voted.png'),
        (control.lang(50031), "anilist_voted_this_season_voted", 'voted.png'),
        (control.lang(50037), "anilist_all_time_voted_voted", 'voted.png'),
    ]

    VOTED_ITEMS_SETTINGS = VOTED_ITEMS[:]
    for i in VOTED_ITEMS:
        if control.getSetting(i[1]) != 'true':
            VOTED_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in VOTED_ITEMS],
        contentType="addons",
        draw_cm=False
    )


@route('completed')
def COMPLETED_MENU(payload, params):
    COMPLETED_ITEMS = [
        (control.lang(50016), "anilist_completed_last_year_completed", 'completed_01.png'),
        (control.lang(50021), "anilist_completed_this_year_completed", 'completed_01.png'),
        (control.lang(50027), "anilist_completed_last_season_completed", 'completed_01.png'),
        (control.lang(50032), "anilist_completed_this_season_completed", 'completed_01.png'),
    ]

    COMPLETED_ITEMS_SETTINGS = COMPLETED_ITEMS[:]
    for i in COMPLETED_ITEMS:
        if control.getSetting(i[1]) != 'true':
            COMPLETED_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in COMPLETED_ITEMS],
        contentType="addons",
        draw_cm=False
    )


@route('upcoming')
def UPCOMING_MENU(payload, params):
    UPCOMING_ITEMS = [
        (control.lang(50017), "anilist_upcoming_last_year_upcoming", 'upcoming.png'),
        (control.lang(50022), "anilist_upcoming_this_year_upcoming", 'upcoming.png'),
        (control.lang(50023), "anilist_upcoming_next_year_upcoming", 'upcoming.png'),
        (control.lang(50028), "anilist_upcoming_last_season_upcoming", 'upcoming.png'),
        (control.lang(50033), "anilist_upcoming_this_season_upcoming", 'upcoming.png'),
        (control.lang(50034), "anilist_upcoming_next_season_upcoming", 'upcoming.png'),
    ]

    UPCOMING_ITEMS_SETTINGS = UPCOMING_ITEMS[:]
    for i in UPCOMING_ITEMS:
        if control.getSetting(i[1]) != 'true':
            UPCOMING_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in UPCOMING_ITEMS],
        contentType="addons",
        draw_cm=False
    )


def _add_last_watched():
    anilist_id = control.getSetting("addon.last_watched")
    if not anilist_id:
        return

    try:
        kodi_meta = pickle.loads(database.get_show(anilist_id)['kodi_meta'])
        last_watched = kodi_meta.get('title_userPreferred')
        MENU_ITEMS.insert(0, (
            "%s[I]%s[/I]" % (control.lang(30000), last_watched.encode('utf-8') if six.PY2 else last_watched),
            "animes/%s/null/" % anilist_id,
            kodi_meta['poster']
        ))
    except:
        return


def get_animes_contentType(seasons=None):
    contentType = control.getSetting("contenttype.episodes")
    if seasons and seasons[0]['is_dir']:
        contentType = control.getSetting("contenttype.seasons")

    return contentType


# Will be called at handle_player
def on_percent():
    return int(control.getSetting('watchlist.percent'))


# Will be called when player is stopped in the middle of the episode
def on_stopped():
    return control.yesno_dialog(control.lang(30200), control.lang(30201), control.lang(30202))


# Will be called on genre page
def genre_dialog(genre_display_list):
    return control.multiselect_dialog(control.lang(50010), genre_display_list)


@route('season_correction/*')
def seasonCorrection(payload, params):
    anilist_id, mal_id, filter_lang = payload.split("/")[1:]
    trakt = _BROWSER.search_trakt_shows(anilist_id)
    return control.draw_items(trakt)


@route('season_correction_database/*')
def seasonCorrectionDatabase(payload, params):
    show_id, meta_ids = payload.rsplit("/")
    # clean_show = _BROWSER.clean_show(show_id, meta_ids)
    trakt, content_type = _BROWSER.get_anime_trakt(show_id, True)
    return control.draw_items(trakt, content_type)


@route('trakt_correction/*')
def traktCorrection(payload, params):
    anilist_id, mal_id, filter_lang = payload.split("/")[1:]
    _ANILIST_BROWSER.update_trakt_id(anilist_id)
    return


@route('find_recommendations/*')
def FIND_RECOMMENDATIONS(payload, params):
    payload_list = payload.split("/")[1:]
    if len(payload_list) == 2:
        mal_id, x = payload_list
        show_meta = database.get_show_mal(mal_id)
        anilist_id = show_meta['anilist_id']
    else:
        anilist_id, mal_id, filter_lang = payload_list
    return control.draw_items(_ANILIST_BROWSER.get_recommendations(anilist_id))


@route('recommendations_next/*')
def RECOMMENDATIONS_NEXT(payload, params):
    anilist_id, page = payload.split("/")
    return control.draw_items(_ANILIST_BROWSER.get_recommendations(anilist_id, int(page)))


@route('find_relations/*')
def FIND_RELATIONS(payload, params):
    payload_list = payload.split("/")[1:]
    if len(payload_list) == 2:
        mal_id, x = payload_list
        show_meta = database.get_show_mal(mal_id)
        anilist_id = show_meta['anilist_id']
    else:
        anilist_id, mal_id, filter_lang = payload_list
    return control.draw_items(_ANILIST_BROWSER.get_relations(anilist_id))


@route('find_all_anime/*')
def FIND_ALL_ANIME(payload, params):
    payload_list = payload.split("/")[1:]
    # Need help on this part


@route('authAllDebrid')
def authAllDebrid(payload, params):
    from resources.lib.debrid.all_debrid import AllDebrid
    AllDebrid().auth()


@route('authDebridLink')
def authDebridLink(payload, params):
    from resources.lib.debrid.debrid_link import DebridLink
    DebridLink().auth()


@route('authRealDebrid')
def authRealDebrid(payload, params):
    from resources.lib.debrid.real_debrid import RealDebrid
    RealDebrid().auth()


@route('authPremiumize')
def authPremiumize(payload, params):
    from resources.lib.debrid.premiumize import Premiumize
    Premiumize().auth()


@route('settings')
def SETTINGS(payload, params):
    database.cache_clear()
    return control.settingsMenu()


@route('clear_cache')
def CLEAR_CACHE(payload, params):
    # control.clear_cache()
    return database.cache_clear()


@route('clear_torrent_cache')
def CLEAR_TORRENT_CACHE(payload, params):
    return database.torrent_cache_clear()


@route('rebuild_database')
def REBUILD_DATABASE(payload, params):
    from resources.lib.ui.database_sync import AnilistSyncDatabase
    AnilistSyncDatabase().re_build_database()


@route('wipe_addon_data')
def WIPE_ADDON_DATA(payload, params):
    dialog = control.yesno_dialog(control.lang(30024), control.lang(30025))
    return control.clear_settings(dialog)


@route('change_log')
def CHANGE_LOG(payload, params):
    from resources.lib.ui import control
    return control.getChangeLog()


@route('consumet_inst')
def CONSUMET_INST(payload, params):
    from resources.lib.ui import control
    return control.getInstructions()


@route('animes/*')
def ANIMES_PAGE(payload, params):
    anilist_id, mal_id, filter_lang = payload.rsplit("/")
    anime_general, content = _BROWSER.get_anime_init(anilist_id, filter_lang)
    return control.draw_items(anime_general, content)


@route('animes_trakt/*')
def ANIMES_TRAKT(payload, params):
    show_id, season = payload.rsplit("/")
    database._update_season(show_id, season)
    return control.draw_items(_BROWSER.get_trakt_episodes(show_id, season), 'episodes')


@route('run_player_dialogs')
def RUN_PLAYER_DIALOGS(payload, params):
    from resources.lib.ui.player import PlayerDialogs
    try:
        PlayerDialogs().display_dialog()
    except:
        import traceback
        traceback.print_exc()


@route('anilist_airing')
def ANILIST_AIRING(payload, params):
    airing = _ANILIST_BROWSER.get_airing()
    from resources.lib.windows.anichart import Anichart

    anime = Anichart(*('anichart.xml', control.ADDON_PATH),
                     get_anime=_BROWSER.get_anime_init, anime_items=airing).doModal()

    if not anime:
        return

    anime, content_type = anime

    return control.draw_items(anime, content_type)


@route('anilist_airing_anime')
def ANILIST_AIRING_ANIME(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime())


@route('anilist_airing_anime/*')
def ANILIST_AIRING_ANIME_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime(int(payload)))


@route('anilist_trending_last_year')
def ANILIST_TRENDING_LAST_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year())


@route('anilist_trending_last_year/*')
def ANILIST_TRENDING_LAST_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year(int(payload)))


@route('anilist_popular_last_year')
def ANILIST_POPULAR_LAST_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year())


@route('anilist_popular_last_year/*')
def ANILIST_POPULAR_LAST_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year(int(payload)))


@route('anilist_voted_last_year')
def ANILIST_VOTED_LAST_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year())


@route('anilist_voted_last_year/*')
def ANILIST_VOTED_LAST_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year(int(payload)))


@route('anilist_completed_last_year')
def ANILIST_COMPLETED_LAST_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year())


@route('anilist_completed_last_year/*')
def ANILIST_COMPLETED_LAST_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year(int(payload)))


@route('anilist_upcoming_last_year')
def ANILIST_UPCOMING_LAST_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year())


@route('anilist_upcoming_last_year/*')
def ANILIST_UPCOMING_LAST_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year(int(payload)))


@route('anilist_trending_this_year')
def ANILIST_TRENDING_THIS_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year())


@route('anilist_trending_this_year/*')
def ANILIST_TRENDING_THIS_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year(int(payload)))


@route('anilist_popular_this_year')
def ANILIST_POPULAR_THIS_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year())


@route('anilist_popular_this_year/*')
def ANILIST_POPULAR_THIS_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year(int(payload)))


@route('anilist_voted_this_year')
def ANILIST_VOTED_THIS_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year())


@route('anilist_voted_this_year/*')
def ANILIST_VOTED_THIS_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year(int(payload)))


@route('anilist_completed_this_year')
def ANILIST_COMPLETED_THIS_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year())


@route('anilist_completed_this_year/*')
def ANILIST_COMPLETED_THIS_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year(int(payload)))


@route('anilist_upcoming_this_year')
def ANILIST_UPCOMING_THIS_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year())


@route('anilist_upcoming_this_year/*')
def ANILIST_UPCOMING_THIS_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year(int(payload)))


@route('anilist_upcoming_next_year')
def ANILIST_UPCOMING_NEXT_YEAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year())


@route('anilist_upcoming_next_year/*')
def ANILIST_UPCOMING_NEXT_YEAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year(int(payload)))


@route('anilist_trending_last_season')
def ANILIST_TRENDING_LAST_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season())


@route('anilist_trending_last_season/*')
def ANILIST_TRENDING_LAST_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season(int(payload)))


@route('anilist_popular_last_season')
def ANILIST_POPULAR_LAST_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season())


@route('anilist_popular_last_season/*')
def ANILIST_POPULAR_LAST_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season(int(payload)))


@route('anilist_voted_last_season')
def ANILIST_VOTED_LAST_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season())


@route('anilist_voted_last_season/*')
def ANILIST_VOTED_LAST_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season(int(payload)))


@route('anilist_completed_last_season')
def ANILIST_COMPLETED_LAST_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season())


@route('anilist_completed_last_season/*')
def ANILIST_COMPLETED_LAST_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season(int(payload)))


@route('anilist_upcoming_last_season')
def ANILIST_UPCOMING_LAST_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season())


@route('anilist_upcoming_last_season/*')
def ANILIST_UPCOMING_LAST_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season(int(payload)))


@route('anilist_trending_this_season')
def ANILIST_TRENDING_THIS_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season())


@route('anilist_trending_this_season/*')
def ANILIST_TRENDING_THIS_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season(int(payload)))


@route('anilist_popular_this_season')
def ANILIST_POPULAR_THIS_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season())


@route('anilist_popular_this_season/*')
def ANILIST_POPULAR_THIS_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season(int(payload)))


@route('anilist_voted_this_season')
def ANILIST_VOTED_THIS_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season())


@route('anilist_voted_this_season/*')
def ANILIST_VOTED_THIS_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season(int(payload)))


@route('anilist_completed_this_season')
def ANILIST_COMPLETED_THIS_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season())


@route('anilist_completed_this_season/*')
def ANILIST_COMPLETED_THIS_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season(int(payload)))


@route('anilist_upcoming_this_season')
def ANILIST_UPCOMING_THIS_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season())


@route('anilist_upcoming_this_season/*')
def ANILIST_UPCOMING_THIS_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season(int(payload)))


@route('anilist_upcoming_next_season')
def ANILIST_UPCOMING_NEXT_SEASON(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season())


@route('anilist_upcoming_next_season/*')
def ANILIST_UPCOMING_NEXT_SEASON_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season(int(payload)))


@route('anilist_all_time_trending')
def ANILIST_ALL_TIME_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending())


@route('anilist_all_time_trending/*')
def ANILIST_ALL_TIME_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending(int(payload)))


@route('anilist_all_time_popular')
def ANILIST_ALL_TIME_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular())


@route('anilist_all_time_popular/*')
def ANILIST_ALL_TIME_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular(int(payload)))


@route('anilist_all_time_voted')
def ANILIST_ALL_TIME_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted())


@route('anilist_all_time_voted/*')
def ANILIST_ALL_TIME_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted(int(payload)))


@route('anilist_top_100_anime')
def ANILIST_TOP_100_ANIME(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime())


@route('anilist_top_100_anime/*')
def ANILIST_TOP_100_ANIME_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime(int(payload)))


@route('anilist_airing_anime_movie')
def ANILIST_AIRING_ANIME_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_movie())


@route('anilist_airing_anime_movie/*')
def ANILIST_AIRING_ANIME_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_movie(int(payload)))


@route('anilist_trending_last_year_movie')
def ANILIST_TRENDING_LAST_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_movie())


@route('anilist_trending_last_year_movie/*')
def ANILIST_TRENDING_LAST_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_movie(int(payload)))


@route('anilist_popular_last_year_movie')
def ANILIST_POPULAR_LAST_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_movie())


@route('anilist_popular_last_year_movie/*')
def ANILIST_POPULAR_LAST_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_movie(int(payload)))


@route('anilist_voted_last_year_movie')
def ANILIST_VOTED_LAST_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_movie())


@route('anilist_voted_last_year_movie/*')
def ANILIST_VOTED_LAST_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_movie(int(payload)))


@route('anilist_completed_last_year_movie')
def ANILIST_COMPLETED_LAST_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_movie())


@route('anilist_completed_last_year_movie/*')
def ANILIST_COMPLETED_LAST_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_movie(int(payload)))


@route('anilist_upcoming_last_year_movie')
def ANILIST_UPCOMING_LAST_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_movie())


@route('anilist_upcoming_last_year_movie/*')
def ANILIST_UPCOMING_LAST_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_movie(int(payload)))


@route('anilist_trending_this_year_movie')
def ANILIST_TRENDING_THIS_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_movie())


@route('anilist_trending_this_year_movie/*')
def ANILIST_TRENDING_THIS_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_movie(int(payload)))


@route('anilist_popular_this_year_movie')
def ANILIST_POPULAR_THIS_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_movie())


@route('anilist_popular_this_year_movie/*')
def ANILIST_POPULAR_THIS_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_movie(int(payload)))


@route('anilist_voted_this_year_movie')
def ANILIST_VOTED_THIS_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_movie())


@route('anilist_voted_this_year_movie/*')
def ANILIST_VOTED_THIS_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_movie(int(payload)))


@route('anilist_completed_this_year_movie')
def ANILIST_COMPLETED_THIS_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_movie())


@route('anilist_completed_this_year_movie/*')
def ANILIST_COMPLETED_THIS_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_movie(int(payload)))


@route('anilist_upcoming_this_year_movie')
def ANILIST_UPCOMING_THIS_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_movie())


@route('anilist_upcoming_this_year_movie/*')
def ANILIST_UPCOMING_THIS_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_movie(int(payload)))


@route('anilist_upcoming_next_year_movie')
def ANILIST_UPCOMING_NEXT_YEAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_movie())


@route('anilist_upcoming_next_year_movie/*')
def ANILIST_UPCOMING_NEXT_YEAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_movie(int(payload)))


@route('anilist_trending_last_season_movie')
def ANILIST_TRENDING_LAST_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_movie())


@route('anilist_trending_last_season_movie/*')
def ANILIST_TRENDING_LAST_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_movie(int(payload)))


@route('anilist_popular_last_season_movie')
def ANILIST_POPULAR_LAST_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_movie())


@route('anilist_popular_last_season_movie/*')
def ANILIST_POPULAR_LAST_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_movie(int(payload)))


@route('anilist_voted_last_season_movie')
def ANILIST_VOTED_LAST_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_movie())


@route('anilist_voted_last_season_movie/*')
def ANILIST_VOTED_LAST_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_movie(int(payload)))


@route('anilist_completed_last_season_movie')
def ANILIST_COMPLETED_LAST_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_movie())


@route('anilist_completed_last_season_movie/*')
def ANILIST_COMPLETED_LAST_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_movie(int(payload)))


@route('anilist_upcoming_last_season_movie')
def ANILIST_UPCOMING_LAST_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_movie())


@route('anilist_upcoming_last_season_movie/*')
def ANILIST_UPCOMING_LAST_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_movie(int(payload)))


@route('anilist_trending_this_season_movie')
def ANILIST_TRENDING_THIS_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_movie())


@route('anilist_trending_this_season_movie/*')
def ANILIST_TRENDING_THIS_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_movie(int(payload)))


@route('anilist_popular_this_season_movie')
def ANILIST_POPULAR_THIS_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_movie())


@route('anilist_popular_this_season_movie/*')
def ANILIST_POPULAR_THIS_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_movie(int(payload)))


@route('anilist_voted_this_season_movie')
def ANILIST_VOTED_THIS_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_movie())


@route('anilist_voted_this_season_movie/*')
def ANILIST_VOTED_THIS_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_movie(int(payload)))


@route('anilist_completed_this_season_movie')
def ANILIST_COMPLETED_THIS_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_movie())


@route('anilist_completed_this_season_movie/*')
def ANILIST_COMPLETED_THIS_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_movie(int(payload)))


@route('anilist_upcoming_this_season_movie')
def ANILIST_UPCOMING_THIS_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_movie())


@route('anilist_upcoming_this_season_movie/*')
def ANILIST_UPCOMING_THIS_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_movie(int(payload)))


@route('anilist_upcoming_next_season_movie')
def ANILIST_UPCOMING_NEXT_SEASON_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_movie())


@route('anilist_upcoming_next_season_movie/*')
def ANILIST_UPCOMING_NEXT_SEASON_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_movie(int(payload)))


@route('anilist_all_time_trending_movie')
def ANILIST_ALL_TIME_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_movie())


@route('anilist_all_time_trending_movie/*')
def ANILIST_ALL_TIME_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_movie(int(payload)))


@route('anilist_all_time_popular_movie')
def ANILIST_ALL_TIME_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_movie())


@route('anilist_all_time_popular_movie/*')
def ANILIST_ALL_TIME_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_movie(int(payload)))


@route('anilist_all_time_voted_movie')
def ANILIST_ALL_TIME_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_movie())


@route('anilist_all_time_voted_movie/*')
def ANILIST_ALL_TIME_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_movie(int(payload)))


@route('anilist_top_100_anime_movie')
def ANILIST_TOP_100_ANIME_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_movie())


@route('anilist_top_100_anime_movie/*')
def ANILIST_TOP_100_ANIME_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_movie(int(payload)))


@route('anilist_airing_anime_tv')
def ANILIST_AIRING_ANIME_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_tv())


@route('anilist_airing_anime_tv/*')
def ANILIST_AIRING_ANIME_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_tv(int(payload)))


@route('anilist_trending_last_year_tv')
def ANILIST_TRENDING_LAST_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_tv())


@route('anilist_trending_last_year_tv/*')
def ANILIST_TRENDING_LAST_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_tv(int(payload)))


@route('anilist_popular_last_year_tv')
def ANILIST_POPULAR_LAST_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_tv())


@route('anilist_popular_last_year_tv/*')
def ANILIST_POPULAR_LAST_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_tv(int(payload)))


@route('anilist_voted_last_year_tv')
def ANILIST_VOTED_LAST_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_tv())


@route('anilist_voted_last_year_tv/*')
def ANILIST_VOTED_LAST_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_tv(int(payload)))


@route('anilist_completed_last_year_tv')
def ANILIST_COMPLETED_LAST_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_tv())


@route('anilist_completed_last_year_tv/*')
def ANILIST_COMPLETED_LAST_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_tv(int(payload)))


@route('anilist_upcoming_last_year_tv')
def ANILIST_UPCOMING_LAST_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_tv())


@route('anilist_upcoming_last_year_tv/*')
def ANILIST_UPCOMING_LAST_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_tv(int(payload)))


@route('anilist_trending_this_year_tv')
def ANILIST_TRENDING_THIS_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_tv())


@route('anilist_trending_this_year_tv/*')
def ANILIST_TRENDING_THIS_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_tv(int(payload)))


@route('anilist_popular_this_year_tv')
def ANILIST_POPULAR_THIS_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_tv())


@route('anilist_popular_this_year_tv/*')
def ANILIST_POPULAR_THIS_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_tv(int(payload)))


@route('anilist_voted_this_year_tv')
def ANILIST_VOTED_THIS_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_tv())


@route('anilist_voted_this_year_tv/*')
def ANILIST_VOTED_THIS_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_tv(int(payload)))


@route('anilist_completed_this_year_tv')
def ANILIST_COMPLETED_THIS_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_tv())


@route('anilist_completed_this_year_tv/*')
def ANILIST_COMPLETED_THIS_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_tv(int(payload)))


@route('anilist_upcoming_this_year_tv')
def ANILIST_UPCOMING_THIS_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_tv())


@route('anilist_upcoming_this_year_tv/*')
def ANILIST_UPCOMING_THIS_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_tv(int(payload)))


@route('anilist_upcoming_next_year_tv')
def ANILIST_UPCOMING_NEXT_YEAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_tv())


@route('anilist_upcoming_next_year_tv/*')
def ANILIST_UPCOMING_NEXT_YEAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_tv(int(payload)))


@route('anilist_trending_last_season_tv')
def ANILIST_TRENDING_LAST_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_tv())


@route('anilist_trending_last_season_tv/*')
def ANILIST_TRENDING_LAST_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_tv(int(payload)))


@route('anilist_popular_last_season_tv')
def ANILIST_POPULAR_LAST_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_tv())


@route('anilist_popular_last_season_tv/*')
def ANILIST_POPULAR_LAST_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_tv(int(payload)))


@route('anilist_voted_last_season_tv')
def ANILIST_VOTED_LAST_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_tv())


@route('anilist_voted_last_season_tv/*')
def ANILIST_VOTED_LAST_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_tv(int(payload)))


@route('anilist_completed_last_season_tv')
def ANILIST_COMPLETED_LAST_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_tv())


@route('anilist_completed_last_season_tv/*')
def ANILIST_COMPLETED_LAST_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_tv(int(payload)))


@route('anilist_upcoming_last_season_tv')
def ANILIST_UPCOMING_LAST_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_tv())


@route('anilist_upcoming_last_season_tv/*')
def ANILIST_UPCOMING_LAST_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_tv(int(payload)))


@route('anilist_trending_this_season_tv')
def ANILIST_TRENDING_THIS_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_tv())


@route('anilist_trending_this_season_tv/*')
def ANILIST_TRENDING_THIS_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_tv(int(payload)))


@route('anilist_popular_this_season_tv')
def ANILIST_POPULAR_THIS_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_tv())


@route('anilist_popular_this_season_tv/*')
def ANILIST_POPULAR_THIS_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_tv(int(payload)))


@route('anilist_voted_this_season_tv')
def ANILIST_VOTED_THIS_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_tv())


@route('anilist_voted_this_season_tv/*')
def ANILIST_VOTED_THIS_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_tv(int(payload)))


@route('anilist_completed_this_season_tv')
def ANILIST_COMPLETED_THIS_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_tv())


@route('anilist_completed_this_season_tv/*')
def ANILIST_COMPLETED_THIS_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_tv(int(payload)))


@route('anilist_upcoming_this_season_tv')
def ANILIST_UPCOMING_THIS_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_tv())


@route('anilist_upcoming_this_season_tv/*')
def ANILIST_UPCOMING_THIS_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_tv(int(payload)))


@route('anilist_upcoming_next_season_tv')
def ANILIST_UPCOMING_NEXT_SEASON_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_tv())


@route('anilist_upcoming_next_season_tv/*')
def ANILIST_UPCOMING_NEXT_SEASON_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_tv(int(payload)))


@route('anilist_all_time_trending_tv')
def ANILIST_ALL_TIME_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_tv())


@route('anilist_all_time_trending_tv/*')
def ANILIST_ALL_TIME_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_tv(int(payload)))


@route('anilist_all_time_popular_tv')
def ANILIST_ALL_TIME_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_tv())


@route('anilist_all_time_popular_tv/*')
def ANILIST_ALL_TIME_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_tv(int(payload)))


@route('anilist_all_time_voted_tv')
def ANILIST_ALL_TIME_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_tv())


@route('anilist_all_time_voted_tv/*')
def ANILIST_ALL_TIME_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_tv(int(payload)))


@route('anilist_top_100_anime_tv')
def ANILIST_TOP_100_ANIME_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_tv())


@route('anilist_top_100_anime_tv/*')
def ANILIST_TOP_100_ANIME_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_tv(int(payload)))


@route('anilist_trending_last_year_trending_trending')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_trending())


@route('anilist_trending_last_year_trending_trending/*')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_trending(int(payload)))


@route('anilist_trending_this_year_trending_trending')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_trending())


@route('anilist_trending_this_year_trending_trending/*')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_trending(int(payload)))


@route('anilist_trending_last_season_trending')
def ANILIST_TRENDING_LAST_SEASON_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending())


@route('anilist_trending_last_season_trending/*')
def ANILIST_TRENDING_LAST_SEASON_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending(int(payload)))


@route('anilist_trending_this_season_trending')
def ANILIST_TRENDING_THIS_SEASON_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending())


@route('anilist_trending_this_season_trending/*')
def ANILIST_TRENDING_THIS_SEASON_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending(int(payload)))


@route('anilist_all_time_trending_trending')
def ANILIST_ALL_TIME_TRENDING_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending())


@route('anilist_all_time_trending_trending/*')
def ANILIST_ALL_TIME_TRENDING_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending(int(payload)))


@route('anilist_popular_last_year_popular')
def ANILIST_POPULAR_LAST_YEAR_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular())


@route('anilist_popular_last_year_popular/*')
def ANILIST_POPULAR_LAST_YEAR_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular(int(payload)))


@route('anilist_popular_this_year_popular')
def ANILIST_POPULAR_THIS_YEAR_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular())


@route('anilist_popular_this_year_popular/*')
def ANILIST_POPULAR_THIS_YEAR_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular(int(payload)))


@route('anilist_popular_last_season_popular')
def ANILIST_POPULAR_LAST_SEASON_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular())


@route('anilist_popular_last_season_popular/*')
def ANILIST_POPULAR_LAST_SEASON_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular(int(payload)))


@route('anilist_popular_this_season_popular')
def ANILIST_POPULAR_THIS_SEASON_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular())


@route('anilist_popular_this_season_popular/*')
def ANILIST_POPULAR_THIS_SEASON_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular(int(payload)))


@route('anilist_all_time_popular_popular')
def ANILIST_ALL_TIME_POPULAR_POPULAR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular())


@route('anilist_all_time_popular_popular/*')
def ANILIST_ALL_TIME_POPULAR_POPULAR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular(int(payload)))


@route('anilist_voted_last_year_voted')
def ANILIST_VOTED_LAST_YEAR_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted())


@route('anilist_voted_last_year_voted/*')
def ANILIST_VOTED_LAST_YEAR_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted(int(payload)))


@route('anilist_voted_this_year_voted')
def ANILIST_VOTED_THIS_YEAR_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted())


@route('anilist_voted_this_year_voted/*')
def ANILIST_VOTED_THIS_YEAR_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted(int(payload)))


@route('anilist_voted_last_season_voted')
def ANILIST_VOTED_LAST_SEASON_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted())


@route('anilist_voted_last_season_voted/*')
def ANILIST_VOTED_LAST_SEASON_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted(int(payload)))


@route('anilist_voted_this_season_voted')
def ANILIST_VOTED_THIS_SEASON_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted())


@route('anilist_voted_this_season_voted/*')
def ANILIST_VOTED_THIS_SEASON_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted(int(payload)))


@route('anilist_all_time_voted_voted')
def ANILIST_ALL_TIME_VOTED_VOTED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted())


@route('anilist_all_time_voted_voted/*')
def ANILIST_ALL_TIME_VOTED_VOTED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted(int(payload)))


@route('anilist_completed_last_year_completed')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed())


@route('anilist_completed_last_year_completed/*')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed(int(payload)))


@route('anilist_completed_this_year_completed')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed())


@route('anilist_completed_this_year_completed/*')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed(int(payload)))


@route('anilist_completed_last_season_completed')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed())


@route('anilist_completed_last_season_completed/*')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed(int(payload)))


@route('anilist_completed_this_season_completed')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed())


@route('anilist_completed_this_season_completed/*')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed(int(payload)))


@route('anilist_upcoming_last_year_upcoming')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming())


@route('anilist_upcoming_last_year_upcoming/*')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming(int(payload)))


@route('anilist_upcoming_this_year_upcoming')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming())


@route('anilist_upcoming_this_year_upcoming/*')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming(int(payload)))


@route('anilist_upcoming_next_year_upcoming')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming())


@route('anilist_upcoming_next_year_upcoming/*')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming(int(payload)))


@route('anilist_upcoming_last_season_upcoming')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming())


@route('anilist_upcoming_last_season_upcoming/*')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming(int(payload)))


@route('anilist_upcoming_this_season_upcoming')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming())


@route('anilist_upcoming_this_season_upcoming/*')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming(int(payload)))


@route('anilist_upcoming_next_season_upcomin')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMIN(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming())


@route('anilist_upcoming_next_season_upcomin/*')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMIN_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming(int(payload)))


@route('anilist_genres')
def ANILIST_GENRES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genres(genre_dialog))


@route('anilist_genres/*')
def ANILIST_GENRES_PAGES(payload, params):
    genres, tags, page = payload.split("/")[-3:]
    return control.draw_items(_ANILIST_BROWSER.get_genres_page(genres, tags, int(page)))


@route('add_to_watchlist/*')
def ADD_TO_WATCHLIST(payload, params):
    anilist_id, mal_id = payload.split("/")[1:-1]
    return watchlist_append(anilist_id)


@route('add_to_completed_watchlist/*')
def ADD_TO_COMPLETED_WATCHLIST(payload, params):
    anilist_id = mal_id = kitsu_id = ''
    payload = payload.split("/")
    if params.get('anilist_id'):
        anilist_id = params.get('anilist_id')
    elif len(payload) == 4:
        id1, id2 = payload[1:-1]
        show = database.get_show(id1)
        if show:
            anilist_id = id1
            mal_id = id2
        else:
            mal_id = id1
            kitsu_id = id2
    elif len(payload) == 2:
        id1 = payload[1]
        show = database.get_show_mal(id1)
        if show:
            mal_id = id1
        else:
            kitsu_id = id1
    else:
        return
    return watchlist_completed(anilist_id, mal_id, kitsu_id)


@route('remove_from_watchlist/*')
def REMOVE_FROM_WATCHLIST(payload, params):
    anilist_id = params.get('anilist_id') if params.get('anilist_id') else payload.split("/")[1]
    watchlist_remove(anilist_id)
    control.refresh()
    return


@route('search_history')
def SEARCH_HISTORY(payload, params):
    history = database.getSearchHistory('show')
    if "Yes" in control.getSetting('searchhistory'):
        return control.draw_items(_BROWSER.search_history(history), contentType="addons", draw_cm=False)
    else:
        return SEARCH(payload, params)


@route('clear_history')
def CLEAR_HISTORY(payload, params):
    database.clearSearchHistory()
    return


@route('search')
def SEARCH(payload, params):
    action_args = params.get('action_args')
    if isinstance(action_args, dict):
        query = action_args.get('query')
    else:
        query = control.keyboard(control.lang(50011))
    if not query:
        return False

    # TODO: Better logic here, maybe move functionatly into router?
    if "Yes" in control.getSetting('searchhistory'):
        database.addSearchHistory(query, 'show')
        # history = database.getSearchHistory('show')

    if isinstance(action_args, dict):
        control.draw_items(_ANILIST_BROWSER.get_search(query, (int(action_args.get('page', '1')))))
    else:
        control.draw_items(_ANILIST_BROWSER.get_search(query))

    return


@route('search/*')
def SEARCH_PAGES(payload, params):
    query, page = payload.rsplit("/", 1)
    return control.draw_items(_ANILIST_BROWSER.get_search(query, int(page)))


@route('search_results/*')
def SEARCH_RESULTS(payload, params):
    query = params.get('query')
    items = _ANILIST_BROWSER.get_search(query, 1)
    return control.draw_items(items)


@route('play_latest/*')
def PLAY_LATEST(payload, params):
    debrid_provider, hash_ = payload.rsplit('/')
    link = _BROWSER.get_latest_sources(debrid_provider, hash_)
    player.play_source(link)


@route('play_movie/*')
def PLAY_MOVIE(payload, params):
    anilist_id, episode, filter_lang = payload.rsplit("/")
    sources = _BROWSER.get_sources(anilist_id, episode, filter_lang, 'movie')

    _mock_args = {'anilist_id': anilist_id}

    if control.getSetting('general.playstyle.movie') == '1' or params.get('source_select'):

        from resources.lib.windows.source_select import SourceSelect

        link = SourceSelect(*('source_select.xml', control.ADDON_PATH),
                            actionArgs=_mock_args, sources=sources).doModal()
    else:
        from resources.lib.windows.resolver import Resolver

        resolver = Resolver(*('resolver.xml', control.ADDON_PATH),
                            actionArgs=_mock_args)

        link = resolver.doModal(sources, {}, False)

    player.play_source(link,
                       anilist_id,
                       watchlist_update,
                       None,
                       int(episode))


@route('play_gogo/*')
def PLAY_GOGO(payload, params):
    slug, episode = payload.rsplit('/')
    from resources.lib.pages import gogoanime
    sources = gogoanime.sources()._process_gogo(slug, '', episode)

    _mock_args = {}
    from resources.lib.windows.source_select import SourceSelect

    link = SourceSelect(*('source_select.xml', control.ADDON_PATH),
                        actionArgs=_mock_args, sources=sources).doModal()

    player.play_source(link)


@route('play/*')
def PLAY(payload, params):
    anilist_id, episode, filter_lang = payload.rsplit("/")
    sources = _BROWSER.get_sources(anilist_id, episode, filter_lang, 'show')
    _mock_args = {"anilist_id": anilist_id, "episode": episode}

    if control.getSetting('general.playstyle.episode') == '1' or params.get('source_select'):

        from resources.lib.windows.source_select import SourceSelect

        link = SourceSelect(*('source_select.xml', control.ADDON_PATH),
                            actionArgs=_mock_args, sources=sources).doModal()
    else:
        from resources.lib.windows.resolver import Resolver

        resolver = Resolver(*('resolver.xml', control.ADDON_PATH),
                            actionArgs=_mock_args)

        link = resolver.doModal(sources, {}, False)

    player.play_source(link,
                       anilist_id,
                       watchlist_update,
                       _BROWSER.get_episodeList,
                       int(episode),
                       filter_lang,
                       source_select=params.get('source_select'))


@route('rescrape_play/*')
def RESCRAPE_PLAY(payload, params):
    anilist_id, episode, filter_lang = payload.rsplit("/")
    sources = _BROWSER.get_sources(anilist_id, episode, filter_lang, 'show', True)
    _mock_args = {"anilist_id": anilist_id}

    from resources.lib.windows.source_select import SourceSelect

    link = SourceSelect(*('source_select.xml', control.ADDON_PATH),
                        actionArgs=_mock_args, sources=sources, anilist_id=anilist_id, rescrape=True).doModal()

    player.play_source(link,
                       anilist_id,
                       watchlist_update,
                       _BROWSER.get_episodeList,
                       int(episode),
                       filter_lang,
                       rescrape=True)


# @route('tmdb_helper')
# def TMDB_HELPER(payload, params):
#    from resources.lib.indexers.anilist import AnilistAPI
#    from resources.lib.indexers.trakt import TRAKTAPI
#    trakt_show_name = params['title']
#    source_select = params['sourceselect']
#    action_args = ast.literal_eval(params.get('actionArgs'))
#    media_type = action_args['item_type']
#    trakt_id = action_args['trakt_id']
#    season = action_args.get('season', None)
#    episode = action_args.get('episode', 1)
#    if not trakt_show_name:
#        trakt_show = TRAKTAPI().get_trakt_show(trakt_id, media_type)
#        trakt_show_name = trakt_show['title']
#    if not media_type == 'movie':
#        if int(season) > 1 and not trakt_show_name.lower() == 'one piece' and not trakt_show_name.lower() == 'case closed':
#            trakt_show_name += " season " + str(season)
#    if 'attack on titan' == trakt_show_name.lower():
#        if int(season) == 4:
#            if int(episode) <= 16:
#                trakt_show_name = 'attack on titan final season'
#            elif int(episode) <= 28:
#                trakt_show_name = 'attack on titan final season part 2'
#            elif int(episode) > 28:
#                trakt_show_name = 'attack on titan final season part 3'
#    params = {}
#    params['dict_key'] = ('data', 'Page', 'media')
#    params['query_path'] = 'search/anime'
#    params['variables'] = {'page': 1,
#                           'search': trakt_show_name,
#                           'sort': 'SEARCH_MATCH',
#                           'type': 'ANIME'}
#    result, page = AnilistAPI().post_json(AnilistAPI._URL, **params)
#    top_result = result[0]
#    if not top_result['anilist_object']['info']['mediatype'] == media_type:
#        for x in result:
#            if x['anilist_object']['info']['mediatype'] == media_type:
#                top_result = x
#                break
#    if media_type == 'movie':
#        pars = {}
#        pars['action_args'] = {'anilist_id': top_result['anilist_id'], 'mediatype': media_type}
#        if source_select == 'true':
#            pars['source_select'] = 'true'
#        PLAY_MOVIE('', pars)
#    else:
#        if "part" in top_result['anilist_object']['info']['title'].lower() and not 'attack on titan' == trakt_show_name:
#            if xbmcgui.Dialog().yesno('Anime Season', "Is this season split into parts AND is this episode in the second part?"):
#                params['variables']['search'] = trakt_show_name + " part 2"
#                params['dict_key'] = ('data', 'Page', 'media')
#                params['query_path'] = 'search/anime'
#                refetched_anilist, op = AnilistAPI().post_json(AnilistAPI._URL, **params)
#                pars = {}
#                pars['action_args'] = {'anilist_id': refetched_anilist[0]['anilist_id'], 'episode': episode, 'mediatype': media_type}
#                if source_select == 'true':
#                    pars['source_select'] = 'true'
#                _BROWSER.get_sources('', pars)
#
#            else:
#                pars = {}
#                pars['action_args'] = {'anilist_id': top_result['anilist_id'], 'episode': episode, 'mediatype': media_type}
#                if source_select == 'true':
#                    pars['source_select'] = 'true'
#                _BROWSER.get_sources('', pars)
#        else:
#            pars = {}
#            if source_select == 'true':
#                pars['source_select'] = 'true'
#            pars['action_args'] = {'anilist_id': top_result['anilist_id'], 'episode': episode, 'mediatype': media_type}
#            _BROWSER.get_sources('', pars)


@route('tools')
def TOOLS_MENU(payload, params):
    TOOLS_ITEMS = [
        (control.lang(30027), "change_log", 'changelog.png'),
        (control.lang(30020), "settings", 'open_settings_menu.png'),
        (control.lang(30021), "clear_cache", 'clear_cache.png'),
        (control.lang(30022), "clear_torrent_cache", 'clear_local_torrent_cache.png'),
        (control.lang(30023), "clear_history", 'clear_search_history.png'),
        (control.lang(30026), "rebuild_database", 'rebuild_database.png'),
        (control.lang(30024), "wipe_addon_data", 'wipe_addon_data.png'),
    ]

    TOOLS_ITEMS_SETTINGS = TOOLS_ITEMS[:]
    for i in TOOLS_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TOOLS_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TOOLS_ITEMS],
        contentType="addons",
        draw_cm=False
    )


@route('')
def LIST_MENU(payload, params):
    ls = str(control.lang(30000))
    MENU_ITEMS_SETTINGS = MENU_ITEMS[:]
    for i in MENU_ITEMS_SETTINGS:
        if control.getSetting(i[1]) != 'true' and ls not in i[0] and 'watchlist' not in i[1]:
            MENU_ITEMS.remove(i)
    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in MENU_ITEMS],
        contentType="addons",
        draw_cm=False
    )


def Main():
    set_browser(_BROWSER)
    _add_last_watched()
    add_watchlist(MENU_ITEMS)
    router_process(control.get_plugin_url(), control.get_plugin_params())
