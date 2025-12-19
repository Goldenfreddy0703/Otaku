import time
import os
import json
import urllib.request
import urllib.error
import threading

from resources.lib.ui import control, client, database_sync


def refresh_apis():
    control.log("### Refreshing API's")
    rd_token = control.getSetting('realdebrid.token')
    dl_token = control.getSetting('debridlink.token')

    kitsu_token = control.getSetting('kitsu.token')
    mal_token = control.getSetting('mal.token')

    if rd_token != '':
        rd_expiry = control.getInt('realdebrid.expiry')
        if time.time() > (rd_expiry - 600):
            from resources.lib.debrid import real_debrid
            real_debrid.RealDebrid().refreshToken()

    if dl_token != '':
        dl_expiry = control.getInt('debridlink.expiry')
        if time.time() > (dl_expiry - 600):
            from resources.lib.debrid import debrid_link
            debrid_link.DebridLink().refreshToken()

    if kitsu_token != '':
        kitsu_expiry = control.getInt('kitsu.expiry')
        if time.time() > (kitsu_expiry - 600):
            from resources.lib.WatchlistFlavor import Kitsu
            Kitsu.KitsuWLF().refresh_token()

    if mal_token != '':
        mal_expiry = control.getInt('mal.expiry')
        if time.time() > (mal_expiry - 600):
            from resources.lib.WatchlistFlavor import MyAnimeList
            MyAnimeList.MyAnimeListWLF().refresh_token()


def update_calendars():
    control.log("### Updating Calendars")
    # from resources.lib.endpoints import anilist, mal, simkl
    # simkl.Simkl().update_calendar()
    # anilist.Anilist().update_calendar()
    # mal.Mal().update_calendar()
    control.log("### Calendars updated successfully")


def update_mappings_db():
    control.log("### Updating Mappings")
    url = 'https://github.com/Goldenfreddy0703/Otaku-Mappings/raw/refs/heads/main/anime_mappings.db'
    try:
        response = urllib.request.urlopen(url)
        with open(os.path.join(control.dataPath, 'mappings.db'), 'wb') as file:
            file.write(response.read())
        control.log("### Mappings updated successfully")
    except urllib.error.URLError as e:
        control.log(f"### Failed to update mappings: {e}")


def sync_watchlist(silent=False):
    if control.getBool('watchlist.sync.enabled'):
        control.log('### Updating Completed Sync')
        from resources.lib.WatchlistFlavor import WatchlistFlavor

        flavor = WatchlistFlavor.get_update_flavor()
        if flavor:
            if flavor.flavor_name in control.enabled_watchlists():
                flavor.save_completed()
                if not silent:
                    notify_string = f'Completed Sync [B]{flavor.flavor_name.capitalize()}[/B]'
                    return control.notify(control.ADDON_NAME, notify_string)
            else:
                if not silent:
                    control.ok_dialog(control.ADDON_NAME, "No Watchlist Enabled or Not Logged In")
        else:
            if not silent:
                control.ok_dialog(control.ADDON_NAME, "No Watchlist Enabled or Not Logged In")
    else:
        if not silent:
            control.ok_dialog(control.ADDON_NAME, "Watchilst Sync is Disabled")


def prefetch_watchlist():
    """Prefetch all watchlist statuses in background for faster loading."""
    if not control.getBool('watchlist.prefetch.enabled'):
        return
    if not control.getBool('watchlist.update.enabled'):
        return

    from resources.lib.ui.database import is_watchlist_cache_valid

    flavor_name = control.getSetting('watchlist.update.flavor').lower()
    if flavor_name not in control.enabled_watchlists():
        return

    # Map flavor to all its status names
    status_map = {
        'mal': ['watching', 'completed', 'on_hold', 'dropped', 'plan_to_watch'],
        'anilist': ['CURRENT', 'COMPLETED', 'PAUSED', 'DROPPED', 'PLANNING', 'REWATCHING'],
        'kitsu': ['current', 'completed', 'on_hold', 'dropped', 'planned'],
        'simkl': ['watching', 'completed', 'on_hold', 'dropped', 'plantowatch']
    }
    statuses = status_map.get(flavor_name)
    if not statuses:
        return

    try:
        from resources.lib.WatchlistFlavor import WatchlistFlavor
        flavor = WatchlistFlavor.get_update_flavor()
        if not flavor:
            return

        for status in statuses:
            # Check if cache is still valid - skip this status
            if is_watchlist_cache_valid(flavor_name, status):
                control.log(f'### Watchlist cache valid for {flavor_name}/{status}, skipping')
                continue

            control.log(f'### Prefetching {flavor_name} watchlist ({status})')
            try:
                # Call get_watchlist_status which will fetch and cache the data
                flavor.get_watchlist_status(status, next_up=False, offset=0, page=1)
                control.log(f'### Prefetch complete for {flavor_name}/{status}')
            except Exception as e:
                control.log(f'### Prefetch failed for {status}: {e}', 'warning')

        control.log(f'### Watchlist prefetch finished for {flavor_name}')
    except Exception as e:
        control.log(f'### Watchlist prefetch failed: {e}', 'warning')


def update_dub_json():
    control.log("### Updating Dub json")
    with open(control.maldubFile, 'w') as file:
        response = client.get('https://raw.githubusercontent.com/MAL-Dubs/MAL-Dubs/main/data/dubInfo.json')
        if response:
            mal_dub_list = response.json()["dubbed"]
            mal_dub = {str(item): {'dub': True} for item in mal_dub_list}
            json.dump(mal_dub, file)
            control.log("### Dubs updated successfully")
        else:
            control.log("### Failed to update Dubs")


def getChangeLog():
    changelog_path = os.path.join(control.ADDON_PATH, 'changelog.txt')
    news_path = os.path.join(control.ADDON_PATH, 'news.txt')

    with open(changelog_path, encoding='utf-8') as changelog_file, open(news_path, encoding='utf-8') as news_file:
        changelog_text = changelog_file.read()
        news_text = news_file.read()

    heading = '[B]%s -  v%s - ChangeLog & News[/B]' % (control.ADDON_NAME, control.ADDON_VERSION)
    from resources.lib.windows.textviewer import TextViewerXML
    windows = TextViewerXML('textviewer.xml', control.ADDON_PATH, heading=heading, changelog_text=changelog_text, news_text=news_text)
    windows.run()
    del windows


def getInstructions():
    instructions_path = os.path.join(control.ADDON_PATH, 'instructions.txt')

    with open(instructions_path, encoding='utf-8') as instructions_file:
        instructions_text = instructions_file.read()

    heading = '[B]%s -  v%s - Instructions[/B]' % (control.ADDON_NAME, control.ADDON_VERSION)
    from resources.lib.windows.textviewer import TextViewerXML
    windows = TextViewerXML('textviewer_1.xml', control.ADDON_PATH, heading=heading, instructions_text=instructions_text)
    windows.run()
    del windows


def getMigration():
    migration_path = os.path.join(control.ADDON_PATH, 'migration.txt')

    with open(migration_path, encoding='utf-8') as migration_file:
        migration_text = migration_file.read()

    heading = '[B]%s -  v%s - Migration[/B]' % (control.ADDON_NAME, control.ADDON_VERSION)
    from resources.lib.windows.textviewer import TextViewerXML
    windows = TextViewerXML('textviewer_1.xml', control.ADDON_PATH, heading=heading, migration_text=migration_text)
    windows.run()
    del windows


def toggle_reuselanguageinvoker(forced_state=None):
    def _store_and_reload(output):
        with open(file_path, "w+") as addon_xml_:
            addon_xml_.writelines(output)
        if not forced_state:
            control.ok_dialog(control.ADDON_NAME, 'Language Invoker option has been changed, reloading kodi profile')
            control.execute('LoadProfile({})'.format(control.xbmc.getInfoLabel("system.profilename")))
    file_path = os.path.join(control.ADDON_PATH, "addon.xml")
    with open(file_path) as addon_xml:
        file_lines = addon_xml.readlines()
    for i in range(len(file_lines)):
        line_string = file_lines[i]
        if "reuselanguageinvoker" in file_lines[i]:
            if forced_state == 'Disabled' or ("true" in line_string and forced_state is None):
                file_lines[i] = file_lines[i].replace("true", "false")
                control.setSetting("reuselanguageinvoker.status", "Disabled")
                _store_and_reload(file_lines)
            elif forced_state == 'Enabled' or ("false" in line_string and forced_state is None):
                file_lines[i] = file_lines[i].replace("false", "true")
                control.setSetting("reuselanguageinvoker.status", "Enabled")
                _store_and_reload(file_lines)
            break


def version_check():
    control.log(f'### {control.ADDON_ID} {control.ADDON_VERSION}')
    control.log(f'### Platform: {control.sys.platform}')
    control.log(f'### Python: {control.sys.version}')
    control.log(f'### SQLite: {database_sync.sqlite_version}')
    control.log(f'### Kodi Version: {control.kodi_version}')

    if control.getSetting('otaku.version') != control.ADDON_VERSION:
        reuselang = control.getSetting('reuselanguageinvoker.status')
        toggle_reuselanguageinvoker(reuselang)
        control.setSetting('otaku.version', control.ADDON_VERSION)
        control.log(f"### {reuselang} Re-uselanguageinvoker")


def apply_migration_settings():
    if os.path.exists(control.migrationSettings):
        try:
            with open(control.migrationSettings, 'r', encoding='utf-8') as f:
                migration_data = json.load(f)
            # Restore each setting from the migration file
            for key, value in migration_data.items():
                try:
                    # Try bool
                    if isinstance(value, bool):
                        control.setBool(key, value)
                    # Try int (but not bool, since bool is a subclass of int)
                    elif isinstance(value, int) and not isinstance(value, bool):
                        control.setInt(key, value)
                    # Fallback to string
                    else:
                        control.setSetting(key, str(value))
                except Exception as e:
                    control.log(f"Error setting {key}: {e}")
                    control.setSetting(key, str(value))
            os.remove(control.migrationSettings)
            control.ok_dialog(control.ADDON_NAME, "Migration complete. Watchlist Settings have been restored.")
            getMigration()
            # Ask the user if they would like to go throught the setup wizard
            # Here the button labels are:
            # Button 0: "Yes"   | Button 1: "No"
            choice = control.yesno_dialog(
                control.ADDON_NAME + ' - ' + control.lang(30415),
                "Welcome back to Otaku!!!\nSense most of your settings have been deleted, would you like to go through the setup wizard?",
                "No", "Yes",
            )

            # Yes selected
            if choice == 1:
                control.setBool('first_time', False)
                control.execute('RunPlugin(plugin://plugin.video.otaku/setup_wizard)')

            # No selected
            elif choice == 0:
                control.setBool('first_time', False)

            control.log("Migration settings successfully applied and file removed.")
        except Exception as e:
            control.log(f"Error applying migration settings: {e}")


if __name__ == "__main__":
    apply_migration_settings()  # Apply migration settings if available
    control.log('##################  RUNNING MAINTENANCE  ######################')
    version_check()
    database_sync.SyncDatabase()
    refresh_apis()
    if control.getInt('update.time.30') == 0 or control.getInt('update.time.7') == 0:
        update_mappings_db()
        update_dub_json()
        sync_watchlist(True)
        control.setInt('update.time.30', int(time.time()))
        control.setInt('update.time.7', int(time.time()))
        control.setInt('update.time.1', int(time.time()))
    else:
        if time.time() > control.getInt('update.time.30') + 2_592_000:   # 30 days
            update_mappings_db()
            control.setInt('update.time.30', int(time.time()))
        if time.time() > control.getInt('update.time.7') + 604_800:   # 7 days
            update_dub_json()
            sync_watchlist(True)
            control.setInt('update.time.7', int(time.time()))
        if time.time() > control.getInt('update.time.1') + 86_400:   # 1 day
            # update_calendars()
            sync_watchlist(True)
            control.setInt('update.time.1', int(time.time()))
    # Prefetch watchlist in background thread (non-blocking)
    threading.Thread(target=prefetch_watchlist, daemon=True).start()
    control.log('##################  MAINTENANCE COMPLETE ######################')
