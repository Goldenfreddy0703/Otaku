import pickle
import time

from resources.lib.ui import control, database
from resources.lib.ui.router import route
from resources.lib.WatchlistFlavor import WatchlistFlavor
from resources.lib.OtakuBrowser import OtakuBrowser
from resources.lib.AniListBrowser import AniListBrowser


def get_auth_dialog(flavor):
    from resources.lib.windows import wlf_auth
    platform = control.sys.platform
    if 'linux' in platform:
        auth = wlf_auth.AltWatchlistFlavorAuth(flavor).set_settings()
    else:
        auth = wlf_auth.WatchlistFlavorAuth(*('wlf_auth_%s.xml' % flavor, control.ADDON_PATH), flavor=flavor).doModal()
    return WatchlistFlavor.login_request(flavor) if auth else None


@route('watchlist_login/*')
def WL_LOGIN(payload, params):
    auth_dialog = bool(params.get('auth_dialog'))
    return get_auth_dialog(payload) if auth_dialog else WatchlistFlavor.login_request(payload)


@route('watchlist_logout/*')
def WL_LOGOUT(payload, params):
    return WatchlistFlavor.logout_request(payload)


@route('watchlist/*')
def WATCHLIST(payload, params):
    return control.draw_items(WatchlistFlavor.watchlist_request(payload), contentType="addons")


@route('watchlist_status_type/*')
def WATCHLIST_STATUS_TYPE(payload, params):
    flavor, status = payload.rsplit("/")
    next_up = bool(params.get('next_up'))
    return control.draw_items(WatchlistFlavor.watchlist_status_request(flavor, status, next_up))


@route('watchlist_status_type_pages/*')
def WATCHLIST_STATUS_TYPE_PAGES(payload, params):
    flavor, status, offset, page = payload.rsplit("/")
    next_up = bool(params.get('next_up'))
    return control.draw_items(WatchlistFlavor.watchlist_status_request_pages(flavor, status, next_up, offset, int(page)))


@route('watchlist_to_ep/*')
def WATCHLIST_TO_EP(payload, params):
    payload_list = payload.rsplit("/")
    anilist_id, mal_id, kitsu_id, eps_watched = payload_list
    if mal_id:
        show = database.get_show_mal(mal_id)
        if not show:
            show = AniListBrowser().get_mal_to_anilist(mal_id)
    else:
        show = database.get_show(anilist_id)

    anilist_id = show['anilist_id']
    kodi_meta = pickle.loads(show['kodi_meta'])
    kodi_meta['eps_watched'] = eps_watched
    database.update_kodi_meta(anilist_id, kodi_meta)

    anime_general, content_type = OtakuBrowser().get_anime_init(anilist_id)

    if control.hide_unaired(content_type) and anime_general[0].get('info').get('aired'):
        anime_general = [x for x in anime_general
                         if x.get('info').get('aired')
                         and time.strptime(x.get('info').get('aired'), '%Y-%m-%d') < time.localtime()]
    return control.draw_items(anime_general, content_type)


@route('watchlist_context/*')
def CONTEXT_MENU(payload, params):
    flavor_settings = {
        'AniList': ('anilist.enabled', 'anilist.username'),
        'Kitsu': ('kitsu.enabled', 'kitsu.username'),
        'MAL': ('mal.enabled', 'mal.username'),
        'Simkl': ('simkl.enabled', 'simkl.username')
    }

    update_enabled = control.getSetting('watchlist.update.enabled')
    if update_enabled == 'false':
        heading = "Watchlist: Setting Not Enabled"
        control.ok_dialog(heading, 'Please toggle the "Update Watchlist" setting before using the Watchlist Manager')
        return

    flavor = control.getSetting('watchlist.update.flavor')
    if flavor not in flavor_settings:
        heading = "%s Watchlist: Not Supported" % flavor
        control.ok_dialog(heading, 'Your "Watchlist to Update" is set to %s but this watchlist is not supported by the Watchlist Manager' % flavor)
        return

    enabled_setting, username_setting = flavor_settings[flavor]
    if control.getSetting(enabled_setting) == "true":
        if control.getSetting(username_setting) == "":
            heading = "%s Watchlist: Not Logged in" % flavor
            control.ok_dialog(heading, 'Your "Watchlist to Update" is set to %s but your %s Watchlist is not logged in, please log into your %s Watchlist before using the Watchlist Manager' % (flavor, flavor, flavor))
            return
    else:
        heading = "%s Watchlist: Not Enabled" % flavor
        control.ok_dialog(heading, 'Your "Watchlist to Update" is set to %s but your %s Watchlist is not enabled, please enable your %s Watchlist before using the Watchlist Manager' % (flavor, flavor, flavor))
        return

    payload_list = payload.rsplit('/')[1:]
    if len(payload_list) == 5:
        path, anilist_id, mal_id, kitsu_id, eps_watched = payload_list
    else:
        path, anilist_id, mal_id, kitsu_id = payload_list

    if not anilist_id:
        show = database.get_show_mal(mal_id)
        if not show:
            show = AniListBrowser().get_mal_to_anilist(mal_id)
        anilist_id = show['anilist_id']
    else:
        show = database.get_show(anilist_id)
        if not show:
            show = AniListBrowser().get_anilist(anilist_id)
    flavor = WatchlistFlavor.get_update_flavor()
    actions = WatchlistFlavor.context_statuses()

    kodi_meta = pickle.loads(show['kodi_meta'])
    title = kodi_meta['title_userPreferred'] or kodi_meta['name']

    context = control.select_dialog('{0} {1}'.format(title, control.colorString("(" + str(flavor.flavor_name).capitalize() + ")", "blue")), list(map(lambda x: x[0], actions)))
    if context != -1:
        heading = '{0} - ({1})'.format(control.ADDON_NAME, str(flavor.flavor_name).capitalize())
        status = actions[context][1]
        if status == 'DELETE':
            yn_title = control.format_string(title, "I")
            yn_flavor = control.format_string(flavor.flavor_name, "B")
            yesno = control.yesno_dialog(
                heading,
                'Are you sure you want to delete {0} from {1}[CR][CR]Press YES to Continue:'.format(yn_title, yn_flavor)
            )
            if yesno:
                delete = delete_watchlist_anime(anilist_id)
                if delete:
                    control.ok_dialog(heading, '{0}  was deleted from {1}'.format(yn_title, yn_flavor))
                else:
                    control.ok_dialog(heading, 'Unable to delete from Watchlist')
        elif status == 'set_score':
            score_list = [
                "(10) Masterpiece",
                "(9) Great",
                "(8) Very Good",
                "(7) Good",
                "(6) Fine",
                "(5) Average",
                "(4) Bad",
                "(3) Very Bad",
                "(2) Horrible",
                "(1) Appalling",
                "(0) No Score"
            ]
            score = control.select_dialog('{0} ({1})'.format(title, str(flavor.flavor_name).capitalize()), score_list)
            if score != -1:
                score = 10 - score
                set_score = set_watchlist_score(anilist_id, score)
                if set_score:
                    control.ok_dialog(heading, '{0} was set to {1}'.format(control.format_string(title, "I"), control.format_string(score, "B")))
                else:
                    control.ok_dialog(heading, 'Unable to Set Score')
        else:
            set_status = set_watchlist_status(anilist_id, status)
            if set_status == 'watching':
                control.ok_dialog(
                    heading,
                    'This show is still airing, so we are keeping it in your "Watching" list and marked all aired episodes as watched.'
                )
            elif set_status:
                control.ok_dialog(heading, '{0}  was added to {1}'.format(control.format_string(title, "I"), control.format_string(status, "B")))
            else:
                control.ok_dialog(heading, 'Unable to Set Watchlist')


def add_watchlist(items):
    flavors = WatchlistFlavor.get_enabled_watchlists()
    if flavors:
        for flavor in flavors:
            items.insert(0, (
                "%s's %s" % (flavor.username, flavor.title),
                "watchlist/%s" % flavor.flavor_name,
                flavor.image,
            ))
    return items


def watchlist_update_episode(anilist_id, episode):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        if int(episode) < 3:
            current = WatchlistFlavor.context_statuses()[0][1]
            status = WatchlistFlavor.watchlist_anime_entry_request(anilist_id).get('status', '')
            if status != current:
                WatchlistFlavor.watchlist_set_status(anilist_id, current)
        return WatchlistFlavor.watchlist_update_episdoe(anilist_id, episode)


def set_watchlist_status(anilist_id, status):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_set_status(anilist_id, status)


def set_watchlist_score(anilist_id, score):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_set_score(anilist_id, score)


def delete_watchlist_anime(anilist_id):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_delete_anime(anilist_id)
