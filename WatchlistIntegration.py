import pickle

from resources.lib.ui import control, database
from resources.lib.ui.router import Route
from resources.lib.WatchlistFlavor import WatchlistFlavor
from resources.lib import MetaBrowser

BROWSER = MetaBrowser.BROWSER


def get_auth_dialog(flavor):
    from resources.lib.windows import wlf_auth
    platform = control.sys.platform
    if 'linux' in platform:
        auth = wlf_auth.AltWatchlistFlavorAuth(flavor).set_settings()
    else:
        auth = wlf_auth.WatchlistFlavorAuth('wlf_auth_%s.xml' % flavor, control.ADDON_PATH, flavor=flavor).doModal()
    return WatchlistFlavor.login_request(flavor) if auth else None


@Route('watchlist_login/*')
def WL_LOGIN(payload, params):
    auth_dialog = bool(params.get('auth_dialog'))
    get_auth_dialog(payload) if auth_dialog else WatchlistFlavor.login_request(payload)
    control.exit_code()


@Route('watchlist_logout/*')
def WL_LOGOUT(payload, params):
    WatchlistFlavor.logout_request(payload)
    control.refresh()
    control.exit_code()


@Route('watchlist/*')
def WATCHLIST(payload, params):
    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(WatchlistFlavor.watchlist_request(payload), view_type)


@Route('watchlist_status_type/*')
def WATCHLIST_STATUS_TYPE(payload, params):
    flavor, status = payload.rsplit("/")
    next_up = bool(params.get('next_up'))
    content_type = 'videos' if next_up else 'tvshows'
    control.draw_items(WatchlistFlavor.watchlist_status_request(flavor, status, next_up), content_type)


@Route('watchlist_status_type_pages/*')
def WATCHLIST_STATUS_TYPE_PAGES(payload, params):
    flavor, status, offset = payload.rsplit("/")
    page = int(params.get('page', 1))
    next_up = bool(params.get('next_up'))
    content_type = 'videos' if next_up else 'tvshows'
    control.draw_items(WatchlistFlavor.watchlist_status_request(flavor, status, next_up, offset, page), content_type)


@Route('watchlist_to_ep/*')
def WATCHLIST_TO_EP(payload, params):
    payload_list = payload.rsplit("/")
    # todo needs to be fixed
    if len(payload_list) == 2:
        mal_id, eps_watched = payload_list
    else:
        mal_id, eps_watched, extra = payload_list
    show_meta = database.get_show(mal_id)
    if not show_meta:
        show_meta = BROWSER.get_anime(mal_id)
    kodi_meta = pickle.loads(show_meta['kodi_meta'])
    kodi_meta['eps_watched'] = eps_watched
    database.update_kodi_meta(mal_id, kodi_meta)

    anime_general, content_type = MetaBrowser.get_anime_init(mal_id)
    control.draw_items(anime_general, content_type)


@Route('watchlist_manager/*')
def CONTEXT_MENU(payload, params):
    if not control.getBool('watchlist.update.enabled'):
        control.ok_dialog(control.ADDON_NAME, control.lang(30461))
        return control.exit_code()
    payload_list = payload.rsplit('/')
    path, mal_id, eps_watched = payload_list

    if not (show := database.get_show(mal_id)):
        show = BROWSER.get_anime(mal_id)

    if not (flavor := WatchlistFlavor.get_update_flavor()):
        control.ok_dialog(control.ADDON_NAME, control.lang(30462))
        return control.exit_code()
    actions = WatchlistFlavor.context_statuses()

    kodi_meta = pickle.loads(show['kodi_meta'])
    title = kodi_meta['title_userPreferred']

    context = control.select_dialog(f"{title}  {control.colorstr(f'({str(flavor.flavor_name).capitalize()})', 'blue')}", list(map(lambda x: x[0], actions)))
    if context != -1:
        heading = f'{control.ADDON_NAME} - ({str(flavor.flavor_name).capitalize()})'
        status = actions[context][1]
        if status == 'DELETE':
            yesno = control.yesno_dialog(heading, control.lang(30463).format(title, flavor.flavor_name))
            if yesno:
                delete = delete_watchlist_anime(mal_id)
                if delete:
                    control.ok_dialog(heading, control.lang(30464).format(title, flavor.flavor_name))
                else:
                    control.ok_dialog(heading, control.lang(30465))
        elif status == 'set_score':
            score_list = [
                control.lang(30466),
                control.lang(30467),
                control.lang(30468),
                control.lang(30469),
                control.lang(30470),
                control.lang(30471),
                control.lang(30472),
                control.lang(30473),
                control.lang(30474),
                control.lang(30475),
                control.lang(30476)
            ]
            score = control.select_dialog(f'{title}: ({str(flavor.flavor_name).capitalize()})', score_list)
            if score != -1:
                score = 10 - score
                set_score = set_watchlist_score(mal_id, score)
                if set_score:
                    control.ok_dialog(heading, control.lang(30477).format(title, score))
                else:
                    control.ok_dialog(heading, control.lang(30478))
        else:
            set_status = set_watchlist_status(mal_id, status)
            if set_status in ['watching', 'current', 'CURRENT']:
                control.ok_dialog(heading, control.lang(30479))
            elif set_status:
                control.ok_dialog(heading, control.lang(30480).format(title, status))
            else:
                control.ok_dialog(heading, control.lang(30481))
    return control.exit_code()


def add_watchlist(items):
    flavors = WatchlistFlavor.get_enabled_watchlists()
    if flavors:
        for flavor in flavors:
            items.append((f"{flavor.username}'s {flavor.title}", f"watchlist/{flavor.flavor_name}", flavor.image, {}))
    return items


def watchlist_update_episode(mal_id, episode):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_update_episode(mal_id, episode)


def set_watchlist_status(mal_id, status):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_set_status(mal_id, status)


def set_watchlist_score(mal_id, score):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_set_score(mal_id, score)


def delete_watchlist_anime(mal_id):
    flavor = WatchlistFlavor.get_update_flavor()
    if flavor:
        return WatchlistFlavor.watchlist_delete_anime(mal_id)
