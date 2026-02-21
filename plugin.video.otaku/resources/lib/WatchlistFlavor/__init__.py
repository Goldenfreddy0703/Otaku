from resources.lib.ui import control
from resources.lib.WatchlistFlavor import AniList, Kitsu, MyAnimeList, Simkl  # noQA
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase


class WatchlistFlavor:
    # Unified status mapping: maps a unified status key to each flavor's native status string.
    _STATUS_MAP = {
        'watching':      {'anilist': 'CURRENT',   'mal': 'watching',      'kitsu': 'current',   'simkl': 'watching'},
        'completed':     {'anilist': 'COMPLETED', 'mal': 'completed',     'kitsu': 'completed', 'simkl': 'completed'},
        'on_hold':       {'anilist': 'PAUSED',    'mal': 'on_hold',       'kitsu': 'on_hold',   'simkl': 'hold'},
        'dropped':       {'anilist': 'DROPPED',   'mal': 'dropped',       'kitsu': 'dropped',   'simkl': 'dropped'},
        'plan_to_watch': {'anilist': 'PLANNING',  'mal': 'plan_to_watch', 'kitsu': 'planned',   'simkl': 'plantowatch'},
        'rewatching':    {'anilist': 'REPEATING',  'mal': 'watching',      'kitsu': 'current',   'simkl': 'watching'},
    }

    def __init__(self):
        raise Exception("Static Class should not be created")

    @staticmethod
    def get_enabled_watchlists():
        return [WatchlistFlavor.__instance_flavor(x) for x in control.enabled_watchlists()]

    @staticmethod
    def get_all_update_flavors():
        """Get all enabled and logged-in watchlist flavor instances for simultaneous updating."""
        if not control.getBool('watchlist.update.enabled'):
            return []
        enabled = control.enabled_watchlists()
        return [WatchlistFlavor.__instance_flavor(name) for name in enabled]

    @staticmethod
    def get_first_enabled_flavor():
        """Get the first enabled watchlist flavor (for data lookups like eps_watched)."""
        enabled = control.enabled_watchlists()
        if enabled:
            return WatchlistFlavor.__instance_flavor(enabled[0])
        return None

    @staticmethod
    def get_flavor_by_name(name):
        """Get a specific watchlist flavor instance by name."""
        if WatchlistFlavor.__is_flavor_valid(name) and name in control.enabled_watchlists():
            return WatchlistFlavor.__instance_flavor(name)
        return None

    @staticmethod
    def watchlist_request(name):
        return WatchlistFlavor.__instance_flavor(name).watchlist()

    @staticmethod
    def watchlist_status_request(name, status, next_up, offset=0, page=1, cache_only=False):
        return WatchlistFlavor.__instance_flavor(name).get_watchlist_status(status, next_up, offset, page, cache_only)

    @staticmethod
    def get_next_up(offset=0, page=1):
        """Get Next Up episodes from the configured watchlist flavor."""
        enabled = control.enabled_watchlists()
        if not enabled:
            return []

        # Determine which flavor to use based on setting
        # 0=Auto (first enabled), 1=AniList, 2=Kitsu, 3=MAL, 4=Simkl
        flavor_map = {1: 'anilist', 2: 'kitsu', 3: 'mal', 4: 'simkl'}
        nextup_pref = control.getInt('nextup.flavor')
        if nextup_pref and nextup_pref in flavor_map:
            preferred = flavor_map[nextup_pref]
            # Only use the preferred flavor if it's actually enabled
            if preferred in enabled:
                flavor_name = preferred
            else:
                flavor_name = enabled[0]
        else:
            flavor_name = enabled[0]

        watching_status = WatchlistFlavor._STATUS_MAP['watching'].get(flavor_name, 'watching')
        flavor = WatchlistFlavor.__instance_flavor(flavor_name)
        return flavor.get_watchlist_status(watching_status, next_up=True, offset=offset, page=page)

    @staticmethod
    def login_request(flavor):
        if not WatchlistFlavor.__is_flavor_valid(flavor):
            raise Exception("Invalid flavor %s" % flavor)
        flavor_class = WatchlistFlavor.__instance_flavor(flavor)
        return WatchlistFlavor.__set_login(flavor, flavor_class.login())

    @staticmethod
    def logout_request(flavor):
        control.setSetting('%s.userid' % flavor, '')
        control.setSetting('%s.authvar' % flavor, '')
        control.setSetting('%s.token' % flavor, '')
        control.setSetting('%s.refresh' % flavor, '')
        control.setSetting('%s.username' % flavor, '')
        control.setSetting('%s.password' % flavor, '')
        control.setInt('%s.sort' % flavor, 0)
        control.setInt('%s.order' % flavor, 0)
        control.setSetting('%s.titles' % flavor, '')
        return control.refresh()

    @staticmethod
    def __get_flavor_class(name):
        for flav in WatchlistFlavorBase.__subclasses__():
            if flav.name() == name:
                return flav

    @staticmethod
    def __is_flavor_valid(name):
        return WatchlistFlavor.__get_flavor_class(name) is not None

    @staticmethod
    def __instance_flavor(name):
        user_id = control.getSetting(f'{name}.userid')
        auth_var = control.getSetting(f'{name}.authvar')
        token = control.getSetting(f'{name}.token')
        refresh = control.getSetting(f'{name}.refresh')
        username = control.getSetting(f'{name}.username')
        password = control.getSetting(f'{name}.password')
        sort = control.getInt(f'{name}.sort')
        order = control.getInt(f'{name}.order')

        flavor_class = WatchlistFlavor.__get_flavor_class(name)
        return flavor_class(auth_var, username, password, user_id, token, refresh, sort, order)

    @staticmethod
    def __set_login(flavor, res):
        if not res:
            return control.ok_dialog('Login', 'Incorrect username or password')
        else:
            control.setBool('watchlist.update.enabled', True)
        for _id, value in list(res.items()):
            setting_name = '%s.%s' % (flavor, _id)
            if _id == 'expiry':
                control.setInt(setting_name, int(value))
            else:
                control.setSetting(setting_name, str(value))
        control.refresh()
        return control.ok_dialog('Login', 'Success')

    # ==================== All-Watchlist Update Methods ====================

    @staticmethod
    def watchlist_update_all_episodes(mal_id, episode):
        """Update episode progress on ALL enabled watchlists simultaneously.
        Handles per-flavor completion detection based on each service's total episode count.
        Returns True if any watchlist was marked as completed."""
        import pickle
        from resources.lib.ui import database

        # Get show info for completion detection fallback
        show = database.get_show(mal_id)
        kodi_episodes = None
        finished_airing = False
        if show:
            kodi_meta = pickle.loads(show['kodi_meta'])
            kodi_episodes = kodi_meta.get('episodes')
            status = kodi_meta.get('status')
            finished_airing = status in ['Finished Airing', 'FINISHED']

        # Update local eps_watched in kodi_meta so watch indicators refresh immediately
        if show:
            kodi_meta['eps_watched'] = episode
            database.update_kodi_meta(mal_id, kodi_meta)

        flavors = WatchlistFlavor.get_all_update_flavors()
        any_completed = False

        for flavor in flavors:
            try:
                flavor.update_num_episodes(mal_id, episode)
                control.log(f'Updated episode {episode} on {flavor.flavor_name}')

                # Per-flavor completion detection using each service's own total episode count
                entry = flavor.get_watchlist_anime_entry(mal_id)
                total = entry.get('total_episodes') if entry else None

                # DEBUG: Log what each API returns for total_episodes
                # control.print(f'[DEBUG] {flavor.flavor_name}: API total_episodes={total}, kodi_meta fallback={kodi_episodes}, entry={entry}')

                if total is None:
                    total = kodi_episodes  # Fallback to kodi_meta

                if total and int(episode) >= int(total) and finished_airing:
                    mapped = WatchlistFlavor._STATUS_MAP['completed'].get(flavor.flavor_name, 'completed')
                    flavor.update_list_status(mal_id, mapped)
                    any_completed = True
                    control.log(f'Auto-completed {flavor.flavor_name} (ep {episode}/{total})')
                else:
                    mapped = WatchlistFlavor._STATUS_MAP['watching'].get(flavor.flavor_name, 'watching')
                    flavor.update_list_status(mal_id, mapped)
                    control.log(f'Set watching on {flavor.flavor_name} (ep {episode}/{total})')

            except Exception as e:
                control.log(f'Failed to update on {flavor.flavor_name}: {e}', 'warning')

        return any_completed

    @staticmethod
    def watchlist_set_all_status(mal_id, status):
        """Set status on ALL enabled watchlists using unified status mapping."""
        flavors = WatchlistFlavor.get_all_update_flavors()
        results = {}
        for flavor in flavors:
            mapped_status = WatchlistFlavor._STATUS_MAP.get(status, {}).get(flavor.flavor_name, status)
            try:
                result = flavor.update_list_status(mal_id, mapped_status)
                results[flavor.flavor_name] = result
                control.log(f'Set status {mapped_status} on {flavor.flavor_name}: {result}')
            except Exception as e:
                control.log(f'Failed to set status on {flavor.flavor_name}: {e}', 'warning')
                results[flavor.flavor_name] = False
        return results

    @staticmethod
    def watchlist_set_all_score(mal_id, score):
        """Set score on ALL enabled watchlists."""
        flavors = WatchlistFlavor.get_all_update_flavors()
        results = {}
        for flavor in flavors:
            try:
                result = flavor.update_score(mal_id, score)
                results[flavor.flavor_name] = result
                control.log(f'Set score {score} on {flavor.flavor_name}: {result}')
            except Exception as e:
                control.log(f'Failed to set score on {flavor.flavor_name}: {e}', 'warning')
                results[flavor.flavor_name] = False
        return results

    @staticmethod
    def watchlist_delete_all_anime(mal_id):
        """Delete anime from ALL enabled watchlists."""
        flavors = WatchlistFlavor.get_all_update_flavors()
        results = {}
        for flavor in flavors:
            try:
                result = flavor.delete_anime(mal_id)
                results[flavor.flavor_name] = result
                control.log(f'Deleted from {flavor.flavor_name}: {result}')
            except Exception as e:
                control.log(f'Failed to delete from {flavor.flavor_name}: {e}', 'warning')
                results[flavor.flavor_name] = False
        return results

    @staticmethod
    def watchlist_sync_all():
        """Run save_completed on ALL enabled watchlists and merge results."""
        import json
        flavors = WatchlistFlavor.get_all_update_flavors()
        merged_completed = {}
        synced = []
        for flavor in flavors:
            try:
                completed = flavor.save_completed()
                if completed:
                    merged_completed.update(completed)
                synced.append(flavor.flavor_name)
                control.log(f'Synced completed for {flavor.flavor_name} ({len(completed) if completed else 0} entries)')
            except Exception as e:
                control.log(f'Failed to sync completed for {flavor.flavor_name}: {e}', 'warning')

        # Write merged completed data from all flavors once
        with open(control.completed_json, 'w') as file:
            json.dump(merged_completed, file)
        control.log(f'Wrote {len(merged_completed)} total completed entries to completed.json')
        return synced

    # ==================== Single-Flavor Methods (for Watchlist Manager) ====================

    @staticmethod
    def watchlist_anime_entry_request(mal_id):
        """Get watchlist anime entry from first available enabled flavor."""
        flavor = WatchlistFlavor.get_first_enabled_flavor()
        if flavor:
            return flavor.get_watchlist_anime_entry(mal_id)
        return {}

    @staticmethod
    def context_statuses_for_flavor(flavor_name):
        """Get action statuses for a specific flavor (used by Watchlist Manager)."""
        flavor = WatchlistFlavor.get_flavor_by_name(flavor_name)
        if flavor:
            return flavor.action_statuses()
        return []

    @staticmethod
    def watchlist_update_episode_for_flavor(flavor_name, mal_id, episode):
        """Update episode on a specific flavor only."""
        flavor = WatchlistFlavor.get_flavor_by_name(flavor_name)
        if flavor:
            return flavor.update_num_episodes(mal_id, episode)
        return False

    @staticmethod
    def watchlist_set_status_for_flavor(flavor_name, mal_id, status):
        """Set status on a specific flavor only."""
        flavor = WatchlistFlavor.get_flavor_by_name(flavor_name)
        if flavor:
            return flavor.update_list_status(mal_id, status)
        return False

    @staticmethod
    def watchlist_set_score_for_flavor(flavor_name, mal_id, score):
        """Set score on a specific flavor only."""
        flavor = WatchlistFlavor.get_flavor_by_name(flavor_name)
        if flavor:
            return flavor.update_score(mal_id, score)
        return False

    @staticmethod
    def watchlist_delete_anime_for_flavor(flavor_name, mal_id):
        """Delete anime from a specific flavor only."""
        flavor = WatchlistFlavor.get_flavor_by_name(flavor_name)
        if flavor:
            return flavor.delete_anime(mal_id)
        return False
