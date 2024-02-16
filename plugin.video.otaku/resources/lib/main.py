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
import time
from resources.lib.AniListBrowser import AniListBrowser
from resources.lib.OtakuBrowser import OtakuBrowser
from resources.lib.ui import control, database, player, utils
from resources.lib.ui.router import route, router_process
from resources.lib.WatchlistIntegration import add_watchlist, watchlist_update_episode

MENU_ITEMS = [
    (control.lang(50000), "anilist_airing_calendar", 'airing_anime_calendar.png'),
    (control.lang(50001), "anilist_airing_anime", 'airing_anime.png'),
    (control.lang(50002), "movies", 'movies.png'),
    (control.lang(50003), "tv_shows", 'tv_shows.png'),
    (control.lang(50004), "trending", 'trending.png'),
    (control.lang(50005), "popular", 'popular.png'),
    (control.lang(50006), "voted", 'voted.png'),
    (control.lang(50007), "completed", 'completed_01.png'),
    (control.lang(50008), "upcoming", 'upcoming.png'),
    (control.lang(50009), "anilist_top_100_anime", 'top_100_anime.png'),
    (control.lang(50010), "genres", 'genres_&_tags.png'),
    (control.lang(50011), "anilist_search", 'search.png'),
    (control.lang(50012), "tools", 'tools.png'),
]
_TITLE_LANG = control.getSetting("general.titlelanguage")
_BROWSER = OtakuBrowser()
_ANILIST_BROWSER = AniListBrowser(_TITLE_LANG)

if control.ADDON_VERSION != control.getSetting('version'):
    showchangelog = control.getSetting("general.showchangelog")
    cache = control.getSetting("changelog.clean_cache")
    if showchangelog == "Yes":
        control.getChangeLog()
    if cache == "true":
        database.cache_clear()
        database.torrent_cache_clear()
    control.setSetting('version', control.ADDON_VERSION)


@route('movies')
def MOVIES_MENU(payload, params):
    MOVIES_ITEMS = [
        (control.lang(50000), "anilist_airing_calendar_movie", 'airing_anime_calendar.png'),
        (control.lang(50001), "anilist_airing_anime_movie", 'airing_anime.png'),
        (control.lang(50004), "trending_movie", 'trending.png'),
        (control.lang(50005), "popular_movie", 'popular.png'),
        (control.lang(50006), "voted_movie", 'voted.png'),
        (control.lang(50007), "completed_movie", 'completed_01.png'),
        (control.lang(50008), "upcoming_movie", 'upcoming.png'),
        (control.lang(50009), "anilist_top_100_anime_movie", 'top_100_anime.png'),
        (control.lang(50010), "genres_movie", 'genres_&_tags.png'),
        (control.lang(50011), "search_history/movie", 'search.png'),
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
        (control.lang(50000), "anilist_airing_calendar_tv", 'airing_anime_calendar.png'),
        (control.lang(50001), "anilist_airing_anime_tv", 'airing_anime.png'),
        (control.lang(50004), "trending_tv", 'trending.png'),
        (control.lang(50005), "popular_tv", 'popular.png'),
        (control.lang(50006), "voted_tv", 'voted.png'),
        (control.lang(50007), "completed_tv", 'completed_01.png'),
        (control.lang(50008), "upcoming_tv", 'upcoming.png'),
        (control.lang(50009), "anilist_top_100_anime_tv", 'top_100_anime.png'),
        (control.lang(50010), "genres_tv", 'genres_&_tags.png'),
        (control.lang(50011), "search_history/show", 'search.png'),
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
        (control.lang(50013), "anilist_trending_last_year_trending", 'trending.png'),
        (control.lang(50018), "anilist_trending_this_year_trending", 'trending.png'),
        (control.lang(50024), "anilist_trending_last_season_trending", 'trending.png'),
        (control.lang(50029), "anilist_trending_this_season_trending", 'trending.png'),
        (control.lang(50035), "anilist_all_time_trending_trending", 'trending.png'),
    ]

    TRENDING_ITEMS_SETTINGS = TRENDING_ITEMS[:]
    for i in TRENDING_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TRENDING_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TRENDING_ITEMS_SETTINGS],
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
        [utils.allocate_item(name, url, True, image) for name, url, image in POPULAR_ITEMS_SETTINGS],
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
        [utils.allocate_item(name, url, True, image) for name, url, image in VOTED_ITEMS_SETTINGS],
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
        [utils.allocate_item(name, url, True, image) for name, url, image in COMPLETED_ITEMS_SETTINGS],
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
        [utils.allocate_item(name, url, True, image) for name, url, image in UPCOMING_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('genres')
def GENRES_MENU(payload, params):
    GENRES_ITEMS = [
        (control.lang(50073), "anilist_genres", 'completed_01.png'),
        (control.lang(50074), "anilist_genre_action", 'genre_action.png'),
        (control.lang(50075), "anilist_genre_adventure", 'genre_adventure.png'),
        (control.lang(50076), "anilist_genre_comedy", 'genre_comedy.png'),
        (control.lang(50077), "anilist_genre_drama", 'genre_drama.png'),
        (control.lang(50078), "anilist_genre_ecchi", 'genre_ecchi.png'),
        (control.lang(50079), "anilist_genre_fantasy", 'genre_fantasy.png'),
        (control.lang(50080), "anilist_genre_hentai", 'genre_hentai.png'),
        (control.lang(50081), "anilist_genre_horror", 'genre_horror.png'),
        (control.lang(50082), "anilist_genre_shoujo", 'genre_shoujo.png'),
        (control.lang(50083), "anilist_genre_mecha", 'genre_mecha.png'),
        (control.lang(50084), "anilist_genre_music", 'genre_music.png'),
        (control.lang(50085), "anilist_genre_mystery", 'genre_mystery.png'),
        (control.lang(50086), "anilist_genre_psychological", 'genre_psychological.png'),
        (control.lang(50087), "anilist_genre_romance", 'genre_romance.png'),
        (control.lang(50088), "anilist_genre_sci_fi", 'genre_sci-fi.png'),
        (control.lang(50089), "anilist_genre_slice_of_life", 'genre_slice_of_life.png'),
        (control.lang(50090), "anilist_genre_sports", 'genre_sports.png'),
        (control.lang(50091), "anilist_genre_supernatural", 'genre_supernatural.png'),
        (control.lang(50092), "anilist_genre_thriller", 'genre_thriller.png'),
    ]

    GENRES_ITEMS_SETTINGS = GENRES_ITEMS[:]
    for i in GENRES_ITEMS:
        if control.getSetting(i[1]) != 'true':
            GENRES_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in GENRES_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('trending_movie')
def TRENDING_MOVIE_MENU(payload, params):
    TRENDING_MOVIE_ITEMS = [
        (control.lang(50013), "anilist_trending_last_year_trending_movie", 'trending.png'),
        (control.lang(50018), "anilist_trending_this_year_trending_movie", 'trending.png'),
        (control.lang(50024), "anilist_trending_last_season_trending_movie", 'trending.png'),
        (control.lang(50029), "anilist_trending_this_season_trending_movie", 'trending.png'),
        (control.lang(50035), "anilist_all_time_trending_trending_movie", 'trending.png'),
    ]

    TRENDING_MOVIE_ITEMS_SETTINGS = TRENDING_MOVIE_ITEMS[:]
    for i in TRENDING_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TRENDING_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TRENDING_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('popular_movie')
def POPULAR_MOVIE_MENU(payload, params):
    POPULAR_MOVIE_ITEMS = [
        (control.lang(50014), "anilist_popular_last_year_popular_movie", 'popular.png'),
        (control.lang(50019), "anilist_popular_this_year_popular_movie", 'popular.png'),
        (control.lang(50025), "anilist_popular_last_season_popular_movie", 'popular.png'),
        (control.lang(50030), "anilist_popular_this_season_popular_movie", 'popular.png'),
        (control.lang(50036), "anilist_all_time_popular_popular_movie", 'popular.png'),
    ]

    POPULAR_MOVIE_ITEMS_SETTINGS = POPULAR_MOVIE_ITEMS[:]
    for i in POPULAR_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            POPULAR_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in POPULAR_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('voted_movie')
def VOTED_MOVIE_MENU(payload, params):
    VOTED_MOVIE_ITEMS = [
        (control.lang(50015), "anilist_voted_last_year_voted_movie", 'voted.png'),
        (control.lang(50020), "anilist_voted_this_year_voted_movie", 'voted.png'),
        (control.lang(50026), "anilist_voted_last_season_voted_movie", 'voted.png'),
        (control.lang(50031), "anilist_voted_this_season_voted_movie", 'voted.png'),
        (control.lang(50037), "anilist_all_time_voted_voted_movie", 'voted.png'),
    ]

    VOTED_MOVIE_ITEMS_SETTINGS = VOTED_MOVIE_ITEMS[:]
    for i in VOTED_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            VOTED_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in VOTED_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('completed_movie')
def COMPLETED_MOVIE_MENU(payload, params):
    COMPLETED_MOVIE_ITEMS = [
        (control.lang(50016), "anilist_completed_last_year_completed_movie", 'completed_01.png'),
        (control.lang(50021), "anilist_completed_this_year_completed_movie", 'completed_01.png'),
        (control.lang(50027), "anilist_completed_last_season_completed_movie", 'completed_01.png'),
        (control.lang(50032), "anilist_completed_this_season_completed_movie", 'completed_01.png'),
    ]

    COMPLETED_MOVIE_ITEMS_SETTINGS = COMPLETED_MOVIE_ITEMS[:]
    for i in COMPLETED_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            COMPLETED_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in COMPLETED_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('upcoming_movie')
def UPCOMING_MOVIE_MENU(payload, params):
    UPCOMING_MOVIE_ITEMS = [
        (control.lang(50017), "anilist_upcoming_last_year_upcoming_movie", 'upcoming.png'),
        (control.lang(50022), "anilist_upcoming_this_year_upcoming_movie", 'upcoming.png'),
        (control.lang(50023), "anilist_upcoming_next_year_upcoming_movie", 'upcoming.png'),
        (control.lang(50028), "anilist_upcoming_last_season_upcoming_movie", 'upcoming.png'),
        (control.lang(50033), "anilist_upcoming_this_season_upcoming_movie", 'upcoming.png'),
        (control.lang(50034), "anilist_upcoming_next_season_upcoming_movie", 'upcoming.png'),
    ]

    UPCOMING_MOVIE_ITEMS_SETTINGS = UPCOMING_MOVIE_ITEMS[:]
    for i in UPCOMING_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            UPCOMING_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in UPCOMING_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('genres_movie')
def GENRES_MOVIE_MENU(payload, params):
    GENRES_MOVIE_ITEMS = [
        (control.lang(50073), "anilist_genres_movie", 'completed_01.png'),
        (control.lang(50074), "anilist_genre_action_movie", 'genre_action.png'),
        (control.lang(50075), "anilist_genre_adventure_movie", 'genre_adventure.png'),
        (control.lang(50076), "anilist_genre_comedy_movie", 'genre_comedy.png'),
        (control.lang(50077), "anilist_genre_drama_movie", 'genre_drama.png'),
        (control.lang(50078), "anilist_genre_ecchi_movie", 'genre_ecchi.png'),
        (control.lang(50079), "anilist_genre_fantasy_movie", 'genre_fantasy.png'),
        (control.lang(50080), "anilist_genre_hentai_movie", 'genre_hentai.png'),
        (control.lang(50081), "anilist_genre_horror_movie", 'genre_horror.png'),
        (control.lang(50082), "anilist_genre_shoujo_movie", 'genre_shoujo.png'),
        (control.lang(50083), "anilist_genre_mecha_movie", 'genre_mecha.png'),
        (control.lang(50084), "anilist_genre_music_movie", 'genre_music.png'),
        (control.lang(50085), "anilist_genre_mystery_movie", 'genre_mystery.png'),
        (control.lang(50086), "anilist_genre_psychological_movie", 'genre_psychological.png'),
        (control.lang(50087), "anilist_genre_romance_movie", 'genre_romance.png'),
        (control.lang(50088), "anilist_genre_sci_fi_movie", 'genre_sci-fi.png'),
        (control.lang(50089), "anilist_genre_slice_of_life_movie", 'genre_slice_of_life.png'),
        (control.lang(50090), "anilist_genre_sports_movie", 'genre_sports.png'),
        (control.lang(50091), "anilist_genre_supernatural_movie", 'genre_supernatural.png'),
        (control.lang(50092), "anilist_genre_thrille_movie", 'genre_thriller.png'),
    ]

    GENRES_MOVIE_ITEMS_SETTINGS = GENRES_MOVIE_ITEMS[:]
    for i in GENRES_MOVIE_ITEMS:
        if control.getSetting(i[1]) != 'true':
            GENRES_MOVIE_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in GENRES_MOVIE_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('trending_tv')
def TRENDING_TV_MENU(payload, params):
    TRENDING_TV_ITEMS = [
        (control.lang(50013), "anilist_trending_last_year_trending_tv", 'trending.png'),
        (control.lang(50018), "anilist_trending_this_year_trending_tv", 'trending.png'),
        (control.lang(50024), "anilist_trending_last_season_trending_tv", 'trending.png'),
        (control.lang(50029), "anilist_trending_this_season_trending_tv", 'trending.png'),
        (control.lang(50035), "anilist_all_time_trending_trending_tv", 'trending.png'),
    ]

    TRENDING_TV_ITEMS_SETTINGS = TRENDING_TV_ITEMS[:]
    for i in TRENDING_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            TRENDING_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in TRENDING_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('popular_tv')
def POPULAR_TV_MENU(payload, params):
    POPULAR_TV_ITEMS = [
        (control.lang(50014), "anilist_popular_last_year_popular_tv", 'popular.png'),
        (control.lang(50019), "anilist_popular_this_year_popular_tv", 'popular.png'),
        (control.lang(50025), "anilist_popular_last_season_popular_tv", 'popular.png'),
        (control.lang(50030), "anilist_popular_this_season_popular_tv", 'popular.png'),
        (control.lang(50036), "anilist_all_time_popular_popular_tv", 'popular.png'),
    ]

    POPULAR_TV_ITEMS_SETTINGS = POPULAR_TV_ITEMS[:]
    for i in POPULAR_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            POPULAR_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in POPULAR_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('voted_tv')
def VOTED_TV_MENU(payload, params):
    VOTED_TV_ITEMS = [
        (control.lang(50015), "anilist_voted_last_year_voted_tv", 'voted.png'),
        (control.lang(50020), "anilist_voted_this_year_voted_tv", 'voted.png'),
        (control.lang(50026), "anilist_voted_last_season_voted_tv", 'voted.png'),
        (control.lang(50031), "anilist_voted_this_season_voted_tv", 'voted.png'),
        (control.lang(50037), "anilist_all_time_voted_voted_tv", 'voted.png'),
    ]

    VOTED_TV_ITEMS_SETTINGS = VOTED_TV_ITEMS[:]
    for i in VOTED_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            VOTED_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in VOTED_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('completed_tv')
def COMPLETED_TV_MENU(payload, params):
    COMPLETED_TV_ITEMS = [
        (control.lang(50016), "anilist_completed_last_year_completed_tv", 'completed_01.png'),
        (control.lang(50021), "anilist_completed_this_year_completed_tv", 'completed_01.png'),
        (control.lang(50027), "anilist_completed_last_season_completed_tv", 'completed_01.png'),
        (control.lang(50032), "anilist_completed_this_season_completed_tv", 'completed_01.png'),
    ]

    COMPLETED_TV_ITEMS_SETTINGS = COMPLETED_TV_ITEMS[:]
    for i in COMPLETED_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            COMPLETED_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in COMPLETED_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('upcoming_tv')
def UPCOMING_TV_MENU(payload, params):
    UPCOMING_TV_ITEMS = [
        (control.lang(50017), "anilist_upcoming_last_year_upcoming_tv", 'upcoming.png'),
        (control.lang(50022), "anilist_upcoming_this_year_upcoming_tv", 'upcoming.png'),
        (control.lang(50023), "anilist_upcoming_next_year_upcoming_tv", 'upcoming.png'),
        (control.lang(50028), "anilist_upcoming_last_season_upcoming_tv", 'upcoming.png'),
        (control.lang(50033), "anilist_upcoming_this_season_upcoming_tv", 'upcoming.png'),
        (control.lang(50034), "anilist_upcoming_next_season_upcoming_tv", 'upcoming.png'),
    ]

    UPCOMING_TV_ITEMS_SETTINGS = UPCOMING_TV_ITEMS[:]
    for i in UPCOMING_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            UPCOMING_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in UPCOMING_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('genres_tv')
def GENRES_TV_MENU(payload, params):
    GENRES_TV_ITEMS = [
        (control.lang(50073), "anilist_genres_tv", 'completed_01.png'),
        (control.lang(50074), "anilist_genre_action_tv", 'genre_action.png'),
        (control.lang(50075), "anilist_genre_adventure_tv", 'genre_adventure.png'),
        (control.lang(50076), "anilist_genre_comedy_tv", 'genre_comedy.png'),
        (control.lang(50077), "anilist_genre_drama_tv", 'genre_drama.png'),
        (control.lang(50078), "anilist_genre_ecchi_tv", 'genre_ecchi.png'),
        (control.lang(50079), "anilist_genre_fantasy_tv", 'genre_fantasy.png'),
        (control.lang(50080), "anilist_genre_hentai_tv", 'genre_hentai.png'),
        (control.lang(50081), "anilist_genre_horror_tv", 'genre_horror.png'),
        (control.lang(50082), "anilist_genre_shoujo_tv", 'genre_shoujo.png'),
        (control.lang(50083), "anilist_genre_mecha_tv", 'genre_mecha.png'),
        (control.lang(50084), "anilist_genre_music_tv", 'genre_music.png'),
        (control.lang(50085), "anilist_genre_mystery_tv", 'genre_mystery.png'),
        (control.lang(50086), "anilist_genre_psychological_tv", 'genre_psychological.png'),
        (control.lang(50087), "anilist_genre_romance_tv", 'genre_romance.png'),
        (control.lang(50088), "anilist_genre_sci_fi_tv", 'genre_sci-fi.png'),
        (control.lang(50089), "anilist_genre_slice_of_life_tv", 'genre_slice_of_life.png'),
        (control.lang(50090), "anilist_genre_sports_tv", 'genre_sports.png'),
        (control.lang(50091), "anilist_genre_supernatural_tv", 'genre_supernatural.png'),
        (control.lang(50092), "anilist_genre_thrille_tv", 'genre_thriller.png'),
    ]

    GENRES_TV_ITEMS_SETTINGS = GENRES_TV_ITEMS[:]
    for i in GENRES_TV_ITEMS:
        if control.getSetting(i[1]) != 'true':
            GENRES_TV_ITEMS_SETTINGS.remove(i)

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in GENRES_TV_ITEMS_SETTINGS],
        contentType="addons",
        draw_cm=False
    )


@route('anilist_search')
def SEARCH_MENU(payload, params):
    SEARCH_ITEMS = [
        (control.lang(50070), "search_history/both", 'search.png'),
        (control.lang(50071), "search_history/movie", 'search.png'),
        (control.lang(50072), "search_history/show", 'search.png'),
    ]

    return control.draw_items(
        [utils.allocate_item(name, url, True, image) for name, url, image in SEARCH_ITEMS],
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
            "animes/%s///" % anilist_id,
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


@route('find_recommendations/*')
def FIND_RECOMMENDATIONS(payload, params):
    payload_list = payload.rsplit("/")[1:]
    if len(payload_list) == 4:
        path, anilist_id, mal_id, kitsu_id = payload_list
    else:
        path, anilist_id, mal_id, kitsu_id, eps_watched = payload_list

    if not anilist_id:
        try:
            anilist_id = database.get_show_mal(mal_id)['anilist_id']
        except TypeError:
            show_meta = _ANILIST_BROWSER.get_mal_to_anilist(mal_id)
            anilist_id = show_meta['anilist_id']
    return control.draw_items(_ANILIST_BROWSER.get_recommendations(anilist_id))


@route('recommendations_next/*')
def RECOMMENDATIONS_NEXT(payload, params):
    anilist_id, page = payload.split("/")
    return control.draw_items(_ANILIST_BROWSER.get_recommendations(anilist_id, int(page)))


@route('find_relations/*')
def FIND_RELATIONS(payload, params):
    payload_list = payload.rsplit("/")[1:]
    if len(payload_list) == 4:
        path, anilist_id, mal_id, kitsu_id = payload_list
    else:
        path, anilist_id, mal_id, kitsu_id, eps_watched = payload_list
    if not anilist_id:
        try:
            anilist_id = database.get_show_mal(mal_id)['anilist_id']
        except TypeError:
            show_meta = _ANILIST_BROWSER.get_mal_to_anilist(mal_id)
            anilist_id = show_meta['anilist_id']
    return control.draw_items(_ANILIST_BROWSER.get_relations(anilist_id))


@route('watch_order/*')
def GET_WATCH_ORDER(payload, params):
    payload_list = payload.rsplit("/")[1:]
    if len(payload_list) == 4:
        path, anilist_id, mal_id, kitsu_id = payload_list
    else:
        path, anilist_id, mal_id, kitsu_id, eps_watched = payload_list
    if not mal_id:
        mal_id = database.get_show(anilist_id)['mal_id']
    return control.draw_items(_ANILIST_BROWSER.get_watch_order(mal_id))


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
    return control.getChangeLog()


# @route('consumet_inst')
# def CONSUMET_INST(payload, params):
#     from resources.lib.ui import control
#     return control.getInstructions()


@route('fs_inst')
def FS_INST(payload, params):
    from resources.lib.ui import control
    return control.getInstructions()


@route('animes/*')
def ANIMES_PAGE(payload, params):
    payload_list = payload.rsplit("/")
    if len(payload_list) == 3:
        anilist_id, mal_id, kitsu_id = payload_list
        filter_lang = ''
    else:
        anilist_id, mal_id, kitsu_id, filter_lang = payload.rsplit("/")
    anime_general, content = _BROWSER.get_anime_init(anilist_id, filter_lang)
    if control.hide_unaired(content) and anime_general[0].get('info').get('aired'):
        anime_general = [x for x in anime_general
                         if x.get('info').get('aired')
                         and time.strptime(x.get('info').get('aired'), '%Y-%m-%d') < time.localtime()]
    return control.draw_items(anime_general, content)


@route('run_player_dialogs')
def RUN_PLAYER_DIALOGS(payload, params):
    from resources.lib.ui.player import PlayerDialogs
    try:
        PlayerDialogs().display_dialog()
    except:
        import traceback
        traceback.print_exc()


@route('anilist_trending_last_year_trending')
def ANILIST_TRENDING_LAST_YEAR_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending())


@route('anilist_trending_last_year_trending/*')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending(int(payload)))


@route('anilist_trending_this_year_trending')
def ANILIST_TRENDING_THIS_YEAR_TRENDING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending())


@route('anilist_trending_this_year_trending/*')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending(int(payload)))


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


@route('anilist_upcoming_next_season_upcoming')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming())


@route('anilist_upcoming_next_season_upcoming/*')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming(int(payload)))


@route('anilist_top_100_anime')
def ANILIST_TOP_100_ANIME(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime())


@route('anilist_top_100_anime/*')
def ANILIST_TOP_100_ANIME_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime(int(payload)))


@route('anilist_trending_last_year_trending_movie')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_movie())


@route('anilist_trending_last_year_trending_movie/*')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_movie(int(payload)))


@route('anilist_trending_this_year_trending_movie')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_movie())


@route('anilist_trending_this_year_trending_movie/*')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_movie(int(payload)))


@route('anilist_trending_last_season_trending_movie')
def ANILIST_TRENDING_LAST_SEASON_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending_movie())


@route('anilist_trending_last_season_trending_movie/*')
def ANILIST_TRENDING_LAST_SEASON_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending_movie(int(payload)))


@route('anilist_trending_this_season_trending_movie')
def ANILIST_TRENDING_THIS_SEASON_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending_movie())


@route('anilist_trending_this_season_trending_movie/*')
def ANILIST_TRENDING_THIS_SEASON_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending_movie(int(payload)))


@route('anilist_all_time_trending_trending_movie')
def ANILIST_ALL_TIME_TRENDING_TRENDING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending_movie())


@route('anilist_all_time_trending_trending_movie/*')
def ANILIST_ALL_TIME_TRENDING_TRENDING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending_movie(int(payload)))


@route('anilist_popular_last_year_popular_movie')
def ANILIST_POPULAR_LAST_YEAR_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular_movie())


@route('anilist_popular_last_year_popular_movie/*')
def ANILIST_POPULAR_LAST_YEAR_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular_movie(int(payload)))


@route('anilist_popular_this_year_popular_movie')
def ANILIST_POPULAR_THIS_YEAR_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular_movie())


@route('anilist_popular_this_year_popular_movie/*')
def ANILIST_POPULAR_THIS_YEAR_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular_movie(int(payload)))


@route('anilist_popular_last_season_popular_movie')
def ANILIST_POPULAR_LAST_SEASON_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular_movie())


@route('anilist_popular_last_season_popular_movie/*')
def ANILIST_POPULAR_LAST_SEASON_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular_movie(int(payload)))


@route('anilist_popular_this_season_popular_movie')
def ANILIST_POPULAR_THIS_SEASON_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular_movie())


@route('anilist_popular_this_season_popular_movie/*')
def ANILIST_POPULAR_THIS_SEASON_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular_movie(int(payload)))


@route('anilist_all_time_popular_popular_movie')
def ANILIST_ALL_TIME_POPULAR_POPULAR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular_movie())


@route('anilist_all_time_popular_popular_movie/*')
def ANILIST_ALL_TIME_POPULAR_POPULAR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular_movie(int(payload)))


@route('anilist_voted_last_year_voted_movie')
def ANILIST_VOTED_LAST_YEAR_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted_movie())


@route('anilist_voted_last_year_voted_movie/*')
def ANILIST_VOTED_LAST_YEAR_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted_movie(int(payload)))


@route('anilist_voted_this_year_voted_movie')
def ANILIST_VOTED_THIS_YEAR_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted_movie())


@route('anilist_voted_this_year_voted_movie/*')
def ANILIST_VOTED_THIS_YEAR_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted_movie(int(payload)))


@route('anilist_voted_last_season_voted_movie')
def ANILIST_VOTED_LAST_SEASON_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted_movie())


@route('anilist_voted_last_season_voted_movie/*')
def ANILIST_VOTED_LAST_SEASON_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted_movie(int(payload)))


@route('anilist_voted_this_season_voted_movie')
def ANILIST_VOTED_THIS_SEASON_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted_movie())


@route('anilist_voted_this_season_voted_movie/*')
def ANILIST_VOTED_THIS_SEASON_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted_movie(int(payload)))


@route('anilist_all_time_voted_voted_movie')
def ANILIST_ALL_TIME_VOTED_VOTED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted_movie())


@route('anilist_all_time_voted_voted_movie/*')
def ANILIST_ALL_TIME_VOTED_VOTED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted_movie(int(payload)))


@route('anilist_completed_last_year_completed_movie')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed_movie())


@route('anilist_completed_last_year_completed_movie/*')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed_movie(int(payload)))


@route('anilist_completed_this_year_completed_movie')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed_movie())


@route('anilist_completed_this_year_completed_movie/*')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed_movie(int(payload)))


@route('anilist_completed_last_season_completed_movie')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed_movie())


@route('anilist_completed_last_season_completed_movie/*')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed_movie(int(payload)))


@route('anilist_completed_this_season_completed_movie')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed_movie())


@route('anilist_completed_this_season_completed_movie/*')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed_movie(int(payload)))


@route('anilist_upcoming_last_year_upcoming_movie')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming_movie())


@route('anilist_upcoming_last_year_upcoming_movie/*')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming_movie(int(payload)))


@route('anilist_upcoming_this_year_upcoming_movie')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming_movie())


@route('anilist_upcoming_this_year_upcoming_movie/*')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming_movie(int(payload)))


@route('anilist_upcoming_next_year_upcoming_movie')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming_movie())


@route('anilist_upcoming_next_year_upcoming_movie/*')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming_movie(int(payload)))


@route('anilist_upcoming_last_season_upcoming_movie')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming_movie())


@route('anilist_upcoming_last_season_upcoming_movie/*')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming_movie(int(payload)))


@route('anilist_upcoming_this_season_upcoming_movie')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming_movie())


@route('anilist_upcoming_this_season_upcoming_movie/*')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming_movie(int(payload)))


@route('anilist_upcoming_next_season_upcoming_movie')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming_movie())


@route('anilist_upcoming_next_season_upcoming_movie/*')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming_movie(int(payload)))


@route('anilist_top_100_anime_movie')
def ANILIST_TOP_100_ANIME_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_movie())


@route('anilist_top_100_anime_movie/*')
def ANILIST_TOP_100_ANIME_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_movie(int(payload)))


@route('anilist_trending_last_year_trending_tv')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_tv())


@route('anilist_trending_last_year_trending_tv/*')
def ANILIST_TRENDING_LAST_YEAR_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_year_trending_tv(int(payload)))


@route('anilist_trending_this_year_trending_tv')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_tv())


@route('anilist_trending_this_year_trending_tv/*')
def ANILIST_TRENDING_THIS_YEAR_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_year_trending_tv(int(payload)))


@route('anilist_trending_last_season_trending_tv')
def ANILIST_TRENDING_LAST_SEASON_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending_tv())


@route('anilist_trending_last_season_trending_tv/*')
def ANILIST_TRENDING_LAST_SEASON_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_last_season_trending_tv(int(payload)))


@route('anilist_trending_this_season_trending_tv')
def ANILIST_TRENDING_THIS_SEASON_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending_tv())


@route('anilist_trending_this_season_trending_tv/*')
def ANILIST_TRENDING_THIS_SEASON_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_trending_this_season_trending_tv(int(payload)))


@route('anilist_all_time_trending_trending_tv')
def ANILIST_ALL_TIME_TRENDING_TRENDING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending_tv())


@route('anilist_all_time_trending_trending_tv/*')
def ANILIST_ALL_TIME_TRENDING_TRENDING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_trending_trending_tv(int(payload)))


@route('anilist_popular_last_year_popular_tv')
def ANILIST_POPULAR_LAST_YEAR_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular_tv())


@route('anilist_popular_last_year_popular_tv/*')
def ANILIST_POPULAR_LAST_YEAR_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_year_popular_tv(int(payload)))


@route('anilist_popular_this_year_popular_tv')
def ANILIST_POPULAR_THIS_YEAR_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular_tv())


@route('anilist_popular_this_year_popular_tv/*')
def ANILIST_POPULAR_THIS_YEAR_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_year_popular_tv(int(payload)))


@route('anilist_popular_last_season_popular_tv')
def ANILIST_POPULAR_LAST_SEASON_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular_tv())


@route('anilist_popular_last_season_popular_tv/*')
def ANILIST_POPULAR_LAST_SEASON_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_last_season_popular_tv(int(payload)))


@route('anilist_popular_this_season_popular_tv')
def ANILIST_POPULAR_THIS_SEASON_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular_tv())


@route('anilist_popular_this_season_popular_tv/*')
def ANILIST_POPULAR_THIS_SEASON_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_popular_this_season_popular_tv(int(payload)))


@route('anilist_all_time_popular_popular_tv')
def ANILIST_ALL_TIME_POPULAR_POPULAR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular_tv())


@route('anilist_all_time_popular_popular_tv/*')
def ANILIST_ALL_TIME_POPULAR_POPULAR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_popular_popular_tv(int(payload)))


@route('anilist_voted_last_year_voted_tv')
def ANILIST_VOTED_LAST_YEAR_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted_tv())


@route('anilist_voted_last_year_voted_tv/*')
def ANILIST_VOTED_LAST_YEAR_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_year_voted_tv(int(payload)))


@route('anilist_voted_this_year_voted_tv')
def ANILIST_VOTED_THIS_YEAR_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted_tv())


@route('anilist_voted_this_year_voted_tv/*')
def ANILIST_VOTED_THIS_YEAR_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_year_voted_tv(int(payload)))


@route('anilist_voted_last_season_voted_tv')
def ANILIST_VOTED_LAST_SEASON_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted_tv())


@route('anilist_voted_last_season_voted_tv/*')
def ANILIST_VOTED_LAST_SEASON_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_last_season_voted_tv(int(payload)))


@route('anilist_voted_this_season_voted_tv')
def ANILIST_VOTED_THIS_SEASON_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted_tv())


@route('anilist_voted_this_season_voted_tv/*')
def ANILIST_VOTED_THIS_SEASON_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_voted_this_season_voted_tv(int(payload)))


@route('anilist_all_time_voted_voted_tv')
def ANILIST_ALL_TIME_VOTED_VOTED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted_tv())


@route('anilist_all_time_voted_voted_tv/*')
def ANILIST_ALL_TIME_VOTED_VOTED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_all_time_voted_voted_tv(int(payload)))


@route('anilist_completed_last_year_completed_tv')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed_tv())


@route('anilist_completed_last_year_completed_tv/*')
def ANILIST_COMPLETED_LAST_YEAR_COMPLETED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_year_completed_tv(int(payload)))


@route('anilist_completed_this_year_completed_tv')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed_tv())


@route('anilist_completed_this_year_completed_tv/*')
def ANILIST_COMPLETED_THIS_YEAR_COMPLETED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_year_completed_tv(int(payload)))


@route('anilist_completed_last_season_completed_tv')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed_tv())


@route('anilist_completed_last_season_completed_tv/*')
def ANILIST_COMPLETED_LAST_SEASON_COMPLETED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_last_season_completed_tv(int(payload)))


@route('anilist_completed_this_season_completed_tv')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed_tv())


@route('anilist_completed_this_season_completed_tv/*')
def ANILIST_COMPLETED_THIS_SEASON_COMPLETED_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_completed_this_season_completed_tv(int(payload)))


@route('anilist_upcoming_last_year_upcoming_tv')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming_tv())


@route('anilist_upcoming_last_year_upcoming_tv/*')
def ANILIST_UPCOMING_LAST_YEAR_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_year_upcoming_tv(int(payload)))


@route('anilist_upcoming_this_year_upcoming_tv')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming_tv())


@route('anilist_upcoming_this_year_upcoming_tv/*')
def ANILIST_UPCOMING_THIS_YEAR_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_year_upcoming_tv(int(payload)))


@route('anilist_upcoming_next_year_upcoming_tv')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming_tv())


@route('anilist_upcoming_next_year_upcoming_tv/*')
def ANILIST_UPCOMING_NEXT_YEAR_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_year_upcoming_tv(int(payload)))


@route('anilist_upcoming_last_season_upcoming_tv')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming_tv())


@route('anilist_upcoming_last_season_upcoming_tv/*')
def ANILIST_UPCOMING_LAST_SEASON_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_last_season_upcoming_tv(int(payload)))


@route('anilist_upcoming_this_season_upcoming_tv')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming_tv())


@route('anilist_upcoming_this_season_upcoming_tv/*')
def ANILIST_UPCOMING_THIS_SEASON_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_this_season_upcoming_tv(int(payload)))


@route('anilist_upcoming_next_season_upcoming_tv')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming_tv())


@route('anilist_upcoming_next_season_upcoming_tv/*')
def ANILIST_UPCOMING_NEXT_SEASON_UPCOMING_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_upcoming_next_season_upcoming_tv(int(payload)))


@route('anilist_top_100_anime_tv')
def ANILIST_TOP_100_ANIME_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_tv())


@route('anilist_top_100_anime_tv/*')
def ANILIST_TOP_100_ANIME_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_top_100_anime_tv(int(payload)))


@route('clear_all_history')
def CLEAR_ALL_HISTORY(payload, params):
    database.clearAllSearchHistory()


# <!-- Main Menu Items -->
@route('anilist_airing_calendar')
def ANILIST_AIRING_CALENDAR(payload, params):
    airing = _ANILIST_BROWSER.get_airing_calendar()
    from resources.lib.windows.anichart import Anichart

    anime = Anichart(*('anichart.xml', control.ADDON_PATH), get_anime=_BROWSER.get_anime_init, anime_items=airing).doModal()

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


@route('anilist_genres')
def ANILIST_GENRES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genres(genre_dialog))


@route('anilist_genres/*')
def ANILIST_GENRES_PAGES(payload, params):
    genres, tags, page = payload.split("/")[-3:]
    return control.draw_items(_ANILIST_BROWSER.get_genres_page(genres, tags, int(page)))


@route('anilist_genre_action')
def ANILIST_GENRE_ACTION(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action())


@route('anilist_genre_action/*')
def ANILIST_GENRE_ACTION_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action(int(payload)))


@route('anilist_genre_adventure')
def ANILIST_GENRE_ADVENTURE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure())


@route('anilist_genre_adventure/*')
def ANILIST_GENRE_ADVENTURE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure(int(payload)))


@route('anilist_genre_comedy')
def ANILIST_GENRE_COMEDY(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy())


@route('anilist_genre_comedy/*')
def ANILIST_GENRE_COMEDY_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy(int(payload)))


@route('anilist_genre_drama')
def ANILIST_GENRE_DRAMA(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama())


@route('anilist_genre_drama/*')
def ANILIST_GENRE_DRAMA_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama(int(payload)))


@route('anilist_genre_ecchi')
def ANILIST_GENRE_ECCHI(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi())


@route('anilist_genre_ecchi/*')
def ANILIST_GENRE_ECCHI_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi(int(payload)))


@route('anilist_genre_fantasy')
def ANILIST_GENRE_FANTASY(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy())


@route('anilist_genre_fantasy/*')
def ANILIST_GENRE_FANTASY_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy(int(payload)))


@route('anilist_genre_hentai')
def ANILIST_GENRE_HENTAI(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai())


@route('anilist_genre_hentai/*')
def ANILIST_GENRE_HENTAI_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai(int(payload)))


@route('anilist_genre_horror')
def ANILIST_GENRE_HORROR(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror())


@route('anilist_genre_horror/*')
def ANILIST_GENRE_HORROR_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror(int(payload)))


@route('anilist_genre_shoujo')
def ANILIST_GENRE_SHOUJO(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo())


@route('anilist_genre_shoujo/*')
def ANILIST_GENRE_SHOUJO_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo(int(payload)))


@route('anilist_genre_mecha')
def ANILIST_GENRE_MECHA(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha())


@route('anilist_genre_mecha/*')
def ANILIST_GENRE_MECHA_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha(int(payload)))


@route('anilist_genre_music')
def ANILIST_GENRE_MUSIC(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music())


@route('anilist_genre_music/*')
def ANILIST_GENRE_MUSIC_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music(int(payload)))


@route('anilist_genre_mystery')
def ANILIST_GENRE_MYSTERY(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery())


@route('anilist_genre_mystery/*')
def ANILIST_GENRE_MYSTERY_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery(int(payload)))


@route('anilist_genre_psychological')
def ANILIST_GENRE_PSYCHOLOGICAL(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological())


@route('anilist_genre_psychological/*')
def ANILIST_GENRE_PSYCHOLOGICAL_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological(int(payload)))


@route('anilist_genre_romance')
def ANILIST_GENRE_ROMANCE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance())


@route('anilist_genre_romance/*')
def ANILIST_GENRE_ROMANCE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance(int(payload)))


@route('anilist_genre_sci_fi')
def ANILIST_GENRE_SCI_FI(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi())


@route('anilist_genre_sci_fi/*')
def ANILIST_GENRE_SCI_FI_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi(int(payload)))


@route('anilist_genre_slice_of_life')
def ANILIST_GENRE_SLICE_OF_LIFE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life())


@route('anilist_genre_slice_of_life/*')
def ANILIST_GENRE_SLICE_OF_LIFE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life(int(payload)))


@route('anilist_genre_sports')
def ANILIST_GENRE_SPORTS(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports())


@route('anilist_genre_sports/*')
def ANILIST_GENRE_SPORTS_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports(int(payload)))


@route('anilist_genre_supernatural')
def ANILIST_GENRE_SUPERNATURAL(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural())


@route('anilist_genre_supernatural/*')
def ANILIST_GENRE_SUPERNATURAL_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural(int(payload)))


@route('anilist_genre_thriller')
def ANILIST_GENRE_THRILLER(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller())


@route('anilist_genre_thriller/*')
def ANILIST_GENRE_THRILLER_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller(int(payload)))


@route('remove_search_item/*')
def REMOVE_SEARCH_ITEM(payload, params):
    payload = payload.split('/')
    database.remove_search(table=payload[1], value=payload[2])


@route('clear_history')
def CLEAR_HISTORY(payload, params):
    stype = 'both'
    action_args = params.get('action_args')
    if action_args:
        if isinstance(action_args, six.string_types):
            import ast
            action_args = ast.literal_eval(action_args)
        stype = action_args.get('stype', stype)

    database.clearSearchHistory(stype)


@route('search_history/*')
def SEARCH_HISTORY(payload, params):
    stype = payload.split('/')[-1]
    if "Yes" in control.getSetting('general.searchhistory'):
        history = database.getSearchHistory(stype)
        return control.draw_items(
            _BROWSER.search_history(stype, history),
            contentType="addons",
            draw_cm=[('Remove from History', 'remove_search_item')]
        )
    else:
        return SEARCH(payload, {'action_args': {'stype': stype}})


@route('search')
def SEARCH(payload, params):
    action_args = params.get('action_args')
    stype = 'both'
    query = None
    if action_args:
        if isinstance(action_args, six.string_types):
            import ast
            action_args = ast.literal_eval(action_args)
        query = action_args.get('query')
        stype = action_args.get('stype', stype)
    if query is None:
        query = control.keyboard(control.lang(50011))
    if not query:
        return False

    if "Yes" in control.getSetting('general.searchhistory'):
        database.addSearchHistory(stype, query)

    if isinstance(action_args, dict):
        control.draw_items(_ANILIST_BROWSER.get_search(stype, query, (int(action_args.get('page', '1')))))
    else:
        control.draw_items(_ANILIST_BROWSER.get_search(stype, query))


@route('search/*')
def SEARCH_PAGES(payload, params):
    page = 1
    if len(payload.split("/")) == 3:
        stype, query, page = payload.split("/")
    else:
        stype, query = payload.split("/")
    return control.draw_items(_ANILIST_BROWSER.get_search(stype, query, int(page)))


# <!-- Movie Menu Items -->
@route('anilist_airing_calendar_movie')
def ANILIST_AIRING_CALENDAR_MOVIE(payload, params):
    airing = _ANILIST_BROWSER.get_airing_calendar_movie()
    from resources.lib.windows.anichart import Anichart

    anime = Anichart(*('anichart.xml', control.ADDON_PATH), get_anime=_BROWSER.get_anime_init, anime_items=airing).doModal()

    if not anime:
        return

    anime, content_type = anime
    return control.draw_items(anime, content_type)


@route('anilist_airing_anime_movie')
def ANILIST_AIRING_ANIME_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_movie())


@route('anilist_airing_anime_movie/*')
def ANILIST_AIRING_ANIME_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_movie(int(payload)))


@route('anilist_genres_movie')
def ANILIST_GENRES_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genres_movie(genre_dialog))


@route('anilist_genres_movie/*')
def ANILIST_GENRES_MOVIE_PAGES(payload, params):
    genres, tags, page = payload.split("/")[-3:]
    return control.draw_items(_ANILIST_BROWSER.get_genres_movie_page(genres, tags, int(page)))


@route('anilist_genre_action_movie')
def ANILIST_GENRE_ACTION_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action_movie())


@route('anilist_genre_action_movie/*')
def ANILIST_GENRE_ACTION_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action_movie(int(payload)))


@route('anilist_genre_adventure_movie')
def ANILIST_GENRE_ADVENTURE_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure_movie())


@route('anilist_genre_adventure_movie/*')
def ANILIST_GENRE_ADVENTURE_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure_movie(int(payload)))


@route('anilist_genre_comedy_movie')
def ANILIST_GENRE_COMEDY_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy_movie())


@route('anilist_genre_comedy_movie/*')
def ANILIST_GENRE_COMEDY_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy_movie(int(payload)))


@route('anilist_genre_drama_movie')
def ANILIST_GENRE_DRAMA_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama_movie())


@route('anilist_genre_drama_movie/*')
def ANILIST_GENRE_DRAMA_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama_movie(int(payload)))


@route('anilist_genre_ecchi_movie')
def ANILIST_GENRE_ECCHI_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi_movie())


@route('anilist_genre_ecchi_movie/*')
def ANILIST_GENRE_ECCHI_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi_movie(int(payload)))


@route('anilist_genre_fantasy_movie')
def ANILIST_GENRE_FANTASY_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy_movie())


@route('anilist_genre_fantasy_movie/*')
def ANILIST_GENRE_FANTASY_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy_movie(int(payload)))


@route('anilist_genre_hentai_movie')
def ANILIST_GENRE_HENTAI_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai_movie())


@route('anilist_genre_hentai_movie/*')
def ANILIST_GENRE_HENTAI_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai_movie(int(payload)))


@route('anilist_genre_horror_movie')
def ANILIST_GENRE_HORROR_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror_movie())


@route('anilist_genre_horror_movie/*')
def ANILIST_GENRE_HORROR_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror_movie(int(payload)))


@route('anilist_genre_shoujo_movie')
def ANILIST_GENRE_SHOUJO_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo_movie())


@route('anilist_genre_shoujo_movie/*')
def ANILIST_GENRE_SHOUJO_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo_movie(int(payload)))


@route('anilist_genre_mecha_movie')
def ANILIST_GENRE_MECHA_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha_movie())


@route('anilist_genre_mecha_movie/*')
def ANILIST_GENRE_MECHA_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha_movie(int(payload)))


@route('anilist_genre_music_movie')
def ANILIST_GENRE_MUSIC_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music_movie())


@route('anilist_genre_music_movie/*')
def ANILIST_GENRE_MUSIC_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music_movie(int(payload)))


@route('anilist_genre_mystery_movie')
def ANILIST_GENRE_MYSTERY_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery_movie())


@route('anilist_genre_mystery_movie/*')
def ANILIST_GENRE_MYSTERY_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery_movie(int(payload)))


@route('anilist_genre_psychological_movie')
def ANILIST_GENRE_PSYCHOLOGICAL_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological_movie())


@route('anilist_genre_psychological_movie/*')
def ANILIST_GENRE_PSYCHOLOGICAL_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological_movie(int(payload)))


@route('anilist_genre_romance_movie')
def ANILIST_GENRE_ROMANCE_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance_movie())


@route('anilist_genre_romance_movie/*')
def ANILIST_GENRE_ROMANCE_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance_movie(int(payload)))


@route('anilist_genre_sci_fi_movie')
def ANILIST_GENRE_SCI_FI_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi_movie())


@route('anilist_genre_sci_fi_movie/*')
def ANILIST_GENRE_SCI_FI_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi_movie(int(payload)))


@route('anilist_genre_slice_of_life_movie')
def ANILIST_GENRE_SLICE_OF_LIFE_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life_movie())


@route('anilist_genre_slice_of_life_movie/*')
def ANILIST_GENRE_SLICE_OF_LIFE_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life_movie(int(payload)))


@route('anilist_genre_sports_movie')
def ANILIST_GENRE_SPORTS_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports_movie())


@route('anilist_genre_sports_movie/*')
def ANILIST_GENRE_SPORTS_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports_movie(int(payload)))


@route('anilist_genre_supernatural_movie')
def ANILIST_GENRE_SUPERNATURAL_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural_movie())


@route('anilist_genre_supernatural_movie/*')
def ANILIST_GENRE_SUPERNATURAL_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural_movie(int(payload)))


@route('anilist_genre_thriller_movie')
def ANILIST_GENRE_THRILLER_MOVIE(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller_movie())


@route('anilist_genre_thriller_movie/*')
def ANILIST_GENRE_THRILLER_MOVIE_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller_movie(int(payload)))


# <!-- TV Show Menu Items -->
@route('anilist_airing_calendar_tv')
def ANILIST_AIRING_CALENDAR_TV(payload, params):
    airing = _ANILIST_BROWSER.get_airing_calendar_tv()
    from resources.lib.windows.anichart import Anichart

    anime = Anichart(*('anichart.xml', control.ADDON_PATH),
                     get_anime=_BROWSER.get_anime_init, anime_items=airing).doModal()

    if not anime:
        return

    anime, content_type = anime
    return control.draw_items(anime, content_type)


@route('anilist_airing_anime_tv')
def ANILIST_AIRING_ANIME_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_tv())


@route('anilist_airing_anime_tv/*')
def ANILIST_AIRING_ANIME_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_airing_anime_tv(int(payload)))


@route('anilist_genres_tv')
def ANILIST_GENRES_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genres_tv(genre_dialog))


@route('anilist_genres_tv/*')
def ANILIST_GENRES_TV_PAGES(payload, params):
    genres, tags, page = payload.split("/")[-3:]
    return control.draw_items(_ANILIST_BROWSER.get_genres_tv_page(genres, tags, int(page)))


@route('anilist_genre_action_tv')
def ANILIST_GENRE_ACTION_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action_tv())


@route('anilist_genre_action_tv/*')
def ANILIST_GENRE_ACTION_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_action_tv(int(payload)))


@route('anilist_genre_adventure_tv')
def ANILIST_GENRE_ADVENTURE_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure_tv())


@route('anilist_genre_adventure_tv/*')
def ANILIST_GENRE_ADVENTURE_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_adventure_tv(int(payload)))


@route('anilist_genre_comedy_tv')
def ANILIST_GENRE_COMEDY_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy_tv())


@route('anilist_genre_comedy_tv/*')
def ANILIST_GENRE_COMEDY_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_comedy_tv(int(payload)))


@route('anilist_genre_drama_tv')
def ANILIST_GENRE_DRAMA_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama_tv())


@route('anilist_genre_drama_tv/*')
def ANILIST_GENRE_DRAMA_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_drama_tv(int(payload)))


@route('anilist_genre_ecchi_tv')
def ANILIST_GENRE_ECCHI_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi_tv())


@route('anilist_genre_ecchi_tv/*')
def ANILIST_GENRE_ECCHI_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_ecchi_tv(int(payload)))


@route('anilist_genre_fantasy_tv')
def ANILIST_GENRE_FANTASY_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy_tv())


@route('anilist_genre_fantasy_tv/*')
def ANILIST_GENRE_FANTASY_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_fantasy_tv(int(payload)))


@route('anilist_genre_hentai_tv')
def ANILIST_GENRE_HENTAI_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai_tv())


@route('anilist_genre_hentai_tv/*')
def ANILIST_GENRE_HENTAI_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_hentai_tv(int(payload)))


@route('anilist_genre_horror_tv')
def ANILIST_GENRE_HORROR_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror_tv())


@route('anilist_genre_horror_tv/*')
def ANILIST_GENRE_HORROR_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_horror_tv(int(payload)))


@route('anilist_genre_shoujo_tv')
def ANILIST_GENRE_SHOUJO_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo_tv())


@route('anilist_genre_shoujo_tv/*')
def ANILIST_GENRE_SHOUJO_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_shoujo_tv(int(payload)))


@route('anilist_genre_mecha_tv')
def ANILIST_GENRE_MECHA_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha_tv())


@route('anilist_genre_mecha_tv/*')
def ANILIST_GENRE_MECHA_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mecha_tv(int(payload)))


@route('anilist_genre_music_tv')
def ANILIST_GENRE_MUSIC_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music_tv())


@route('anilist_genre_music_tv/*')
def ANILIST_GENRE_MUSIC_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_music_tv(int(payload)))


@route('anilist_genre_mystery_tv')
def ANILIST_GENRE_MYSTERY_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery_tv())


@route('anilist_genre_mystery_tv/*')
def ANILIST_GENRE_MYSTERY_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_mystery_tv(int(payload)))


@route('anilist_genre_psychological_tv')
def ANILIST_GENRE_PSYCHOLOGICAL_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological_tv())


@route('anilist_genre_psychological_tv/*')
def ANILIST_GENRE_PSYCHOLOGICAL_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_psychological_tv(int(payload)))


@route('anilist_genre_romance_tv')
def ANILIST_GENRE_ROMANCE_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance_tv())


@route('anilist_genre_romance_tv/*')
def ANILIST_GENRE_ROMANCE_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_romance_tv(int(payload)))


@route('anilist_genre_sci_fi_tv')
def ANILIST_GENRE_SCI_FI_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi_tv())


@route('anilist_genre_sci_fi_tv/*')
def ANILIST_GENRE_SCI_FI_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sci_fi_tv(int(payload)))


@route('anilist_genre_slice_of_life_tv')
def ANILIST_GENRE_SLICE_OF_LIFE_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life_tv())


@route('anilist_genre_slice_of_life_tv/*')
def ANILIST_GENRE_SLICE_OF_LIFE_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_slice_of_life_tv(int(payload)))


@route('anilist_genre_sports_tv')
def ANILIST_GENRE_SPORTS_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports_tv())


@route('anilist_genre_sports_tv/*')
def ANILIST_GENRE_SPORTS_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_sports_tv(int(payload)))


@route('anilist_genre_supernatural_tv')
def ANILIST_GENRE_SUPERNATURAL_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural_tv())


@route('anilist_genre_supernatural_tv/*')
def ANILIST_GENRE_SUPERNATURAL_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_supernatural_tv(int(payload)))


@route('anilist_genre_thriller_tv')
def ANILIST_GENRE_THRILLER_TV(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller_tv())


@route('anilist_genre_thriller_tv/*')
def ANILIST_GENRE_THRILLER_TV_PAGES(payload, params):
    return control.draw_items(_ANILIST_BROWSER.get_genre_thriller_tv(int(payload)))


@route('play/*')
def PLAY(payload, params):
    anilist_id, episode, filter_lang = payload.rsplit("/")
    source_select = bool(params.get('source_select'))
    rescrape = bool(params.get('rescrape'))
    sources = _BROWSER.get_sources(anilist_id, episode, filter_lang, 'show', rescrape, source_select)
    _mock_args = {"anilist_id": anilist_id, "episode": episode}

    if control.getSetting('general.playstyle.episode') == '1' or source_select or rescrape:
        from resources.lib.windows.source_select import SourceSelect
        link = SourceSelect(*('source_select.xml', control.ADDON_PATH), actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()

    else:
        from resources.lib.windows.resolver import Resolver
        resolver = Resolver(*('resolver.xml', control.ADDON_PATH), actionArgs=_mock_args)
        link = resolver.doModal(sources, {}, False)
    player.play_source(link, anilist_id, watchlist_update_episode, _BROWSER.get_episodeList, int(episode),
                       source_select=source_select, rescrape=rescrape)


@route('play_movie/*')
def PLAY_MOVIE(payload, params):
    payload_list = payload.rsplit("/")
    anilist_id, mal_id, kitsu_id = payload_list
    source_select = bool(params.get('source_select'))
    rescrape = bool(params.get('rescrape'))
    if not anilist_id:
        try:
            anilist_id = database.get_show_mal(mal_id)['anilist_id']
        except TypeError:
            show_meta = _ANILIST_BROWSER.get_mal_to_anilist(mal_id)
            anilist_id = show_meta['anilist_id']
    sources = _BROWSER.get_sources(anilist_id, 1, None, 'movie', rescrape, source_select)
    _mock_args = {'anilist_id': anilist_id}

    if control.getSetting('general.playstyle.movie') == '1' or source_select or rescrape:
        from resources.lib.windows.source_select import SourceSelect
        link = SourceSelect(*('source_select.xml', control.ADDON_PATH), actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()

    else:
        from resources.lib.windows.resolver import Resolver
        resolver = Resolver(*('resolver.xml', control.ADDON_PATH), actionArgs=_mock_args)
        link = resolver.doModal(sources, {}, False)
    player.play_source(link, anilist_id, watchlist_update_episode, _BROWSER.get_episodeList, 1, source_select=source_select, rescrape=rescrape)


@route('toggleLanguageInvoker')
def TOGGLE_LANGUAGE_INVOKER(payload, params):
    return control.toggle_reuselanguageinvoker()


@route('marked_as_watched/*')
def MARKED_AS_WATCHED(payload, params):
    from resources.lib.WatchlistFlavor import WatchlistFlavor

    play, anilist_id, episode, filter_lang = payload.rsplit("/")
    flavor = WatchlistFlavor.get_update_flavor()
    watchlist_update_episode(anilist_id, episode)
    control.notify('Episode #{0} was Marked as Watched in {1}'.format(episode, flavor.flavor_name))
    plugin = 'plugin://plugin.video.otaku'
    show_meta = database.get_show(anilist_id)
    kitsu_id = show_meta['kitsu_id']  # todo kitsu_id is None right now needs to be fixed
    mal_id = show_meta['mal_id']
    control.execute('ActivateWindow(Videos,{0}/watchlist_to_ep/{1}/{2}/{3}/{4})'.format(plugin, anilist_id, mal_id, kitsu_id, episode))


@route('delete_anime_from_database/*')
def DELETE_ANIME_DATABASE(payload, params):
    payload_list = payload.rsplit("/")
    if len(payload_list) == 4:
        path, anilist_id, mal_id, kitsu_id = payload_list
    else:
        path, anilist_id, mal_id, kitsu_id, eps_watched = payload_list
    if not anilist_id:
        try:
            show_meta = database.get_show_mal(mal_id)
            anilist_id = show_meta['anilist_id']
            title_user = pickle.loads(show_meta['kodi_meta'])['title_userPreferred']
        except TypeError:
            show_meta = _ANILIST_BROWSER.get_mal_to_anilist(mal_id)
            anilist_id = show_meta['anilist_id']
            title_user = pickle.loads(show_meta['kodi_meta'])['title_userPreferred']
    else:
        show_meta = database.get_show(anilist_id)
        try:
            title_user = pickle.loads(show_meta['kodi_meta'])['title_userPreferred']
        except TypeError:
            control.notify("Not in Database")
            return

    database.remove_episodes(anilist_id)
    database.remove_season(anilist_id)
    control.notify('Removed "%s" from database' % title_user)


@route('tmdb_helper')
def TMDB_HELPER(payload, params):
    from resources.lib.indexers.tmdb2anime import TMDB2ANIME
    import ast
    action_args = params.pop('actionArgs')

    if isinstance(action_args, six.string_types):
        action_args = ast.literal_eval(action_args)

    media_type = action_args['item_type']
    source_select = params.pop('source_select') == 'true'
    params.update({'source_select': source_select})
    if media_type == 'movie':
        anime_ids = database.get_mapping(tmdb_id=action_args['tmdb_id'])
        if not anime_ids.get('anilist_id'):
            anime_ids = TMDB2ANIME().get_ids(action_args['tmdb_id'])
        if anime_ids.get('anilist_id'):
            playload = '{0}/{1}/'.format(anime_ids.get('anilist_id'), anime_ids.get('mal_id'))
            PLAY_MOVIE(playload, params)
        else:
            control.notify('No Anilist ID Found, Might be a special or not in database')
    else:
        anime_ids = TMDB2ANIME().get_ids(action_args['tmdb_id'], action_args['season'])
        if anime_ids.get('anilist_id'):
            playload = '{0}/{1}/'.format(anime_ids.get('anilist_id'), action_args['episode'])
            PLAY(playload, params)
        else:
            control.notify('No Anilist ID Found, Might be a special or not in database')


@route('tools')
def TOOLS_MENU(payload, params):
    TOOLS_ITEMS = [
        (control.lang(30027), "change_log", 'changelog.png'),
        (control.lang(30020), "settings", 'open_settings_menu.png'),
        (control.lang(30021), "clear_cache", 'clear_cache.png'),
        (control.lang(30022), "clear_torrent_cache", 'clear_local_torrent_cache.png'),
        (control.lang(30023), "clear_all_history", 'clear_search_history.png'),
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
    _add_last_watched()
    add_watchlist(MENU_ITEMS)
    router_process(control.get_plugin_url(), control.get_plugin_params())
