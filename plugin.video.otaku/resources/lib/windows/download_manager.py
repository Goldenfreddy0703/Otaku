import xbmcgui, xbmcvfs
import json
import os
import math
import requests
import time

from resources.lib.windows.base_window import BaseWindow
from resources.lib.ui import database, control
from urllib import parse


CLOCK = time.time


class DownloadManager(BaseWindow):
    def __init__(self, xml_file, location):
        super().__init__(xml_file, location)
        self.abort = False
        self.downloads = []
        self.display_list = None

    def onInit(self):
        self.display_list = self.getControl(1000)
        self.background_info_updater()
        super().onInit()

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.abort = True
            self.close()

        if actionID == 7:
            self.handle_action(7)

        elif actionID == 117:
            context_response = control.context_menu(['Cancel Download'])
            if context_response == 0:
                pass

    def onClick(self, controlID):
        self.handle_action(controlID)

    def handle_action(self, controlID):
        if controlID == 3100:
            self.abort = True
            manager.clear_complete()
            self.close()
            DownloadManager(*('download_manager.xml', control.ADDON_PATH)).doModal()

        if controlID == 3101:   # close
            self.abort = True
            self.close()

    def background_info_updater(self):
        while not control.abort_requested() and not self.abort:
            self.downloads = manager.get_all_tasks_info()
            self.populate_menu_items()
            control.sleep(1000)

    def populate_menu_items(self):
        def create_menu_item(download_item):
            new_item = xbmcgui.ListItem(label=f"{download_item['filename']}")
            self.set_menu_item_properties(new_item, download_item)
            return new_item

        # while len(self.downloads) < self.display_list.size():
        #     self.display_list.removeItem(self.display_list.size() - 1)

        for idx, download in enumerate(self.downloads):
            if idx < self.display_list.size():
                menu_item = self.display_list.getListItem(idx)
                self.set_menu_item_properties(menu_item, download)
            else:
                menu_item = create_menu_item(download)
                self.display_list.addItem(menu_item)

    @staticmethod
    def set_menu_item_properties(menu_item, download_info):
        menu_item.setProperty('item.info.speed', download_info['speed'])
        menu_item.setProperty('item.info.progress', str(download_info['progress']))
        menu_item.setProperty('item.info.filename', download_info['filename'])
        menu_item.setProperty('item.info.eta', download_info['eta'])
        menu_item.setProperty('item.info.filesize', download_info['filesize'])
        menu_item.setProperty('item.info.downloaded', download_info['downloaded'])
        menu_item.setProperty('item.info.status', download_info['status'])
        menu_item.setProperty('item.info.hash', download_info.get('hash', ''))


class Manager:
    download_init = {
        "speed": "0 B/s",
        "progress": 0,
        "filename": "",
        "eta": "99:99:99",
        "filesize": "0 B",
        "downloaded": "0 B",
        "status": '',
        'hash': ''
    }

    def __init__(self):
        self.url_hash = None
        self.storage_location = control.getSetting('download.location')
        self.file_size = -1
        self.file_size_display = None
        self.progress = -1
        self.speed = -1
        self.remaining_seconds = -1
        self.output_path = None
        self.canceled = False
        self.bytes_consumed = 0
        self.output_filename = None
        self._start_time = CLOCK()
        self.status = "Starting"
        self.download_ids = []
        self.download = {}
        if not xbmcvfs.exists(control.downloads_json):
            with open(control.downloads_json, 'w') as file:
                json.dump({}, file)

    def create_download_task(self, url_hash):
        self.get_download_index()
        if url_hash in self.download_ids:
            control.notify(control.ADDON_NAME, "Skipped creating duplicate download task")
            return False
        self.download_ids.append(url_hash)
        self.insert_into_index()
        self.url_hash = url_hash
        self.download[url_hash] = self.download_init
        self.download[url_hash]['hash'] = url_hash
        self.update_task_info(url_hash, self.download[url_hash])
        return True

    def cancel_task(self, url_hash):
        self.get_download_index()
        # info = self.get_task_info(url_hash)
        # info["canceled"] = True
        # self.update_task_info(url_hash, info)

    def insert_into_index(self):
        control.setSetting("DMIndex", ",".join(self.download_ids))

    @staticmethod
    def update_task_info(url_hash, download_dict):
        with open(control.downloads_json) as file:
            downloads = json.load(file)
        with open(control.downloads_json, 'w') as file:
            downloads[url_hash] = download_dict
            json.dump(downloads, file)

    def get_all_tasks_info(self):
        self.get_download_index()
        with open(control.downloads_json) as file:
            downloads = json.load(file)
        return downloads.values()

    def get_download_index(self):
        index = control.getSetting("DMIndex")
        self.download_ids = [i for i in index.split(",") if i] if index is not None else []

    def clear_complete(self):
        for download_ in self.get_all_tasks_info():
            if download_["progress"] >= 100:
                self.remove_download_task(download_["hash"])

    def remove_download_task(self, url_hash):
        self.get_download_index()
        with open(control.downloads_json) as file:
            downloads = json.load(file)
        with open(control.downloads_json, 'w') as file:
            if downloads.get(url_hash):
                downloads.pop(url_hash)
                json.dump(downloads, file)
        if url_hash in self.download_ids:
            self.remove_from_index(url_hash)

    def remove_from_index(self, url_hash):
        self.download_ids.remove(url_hash)
        control.setSetting("DMIndex", ",".join(self.download_ids))

    def download_file(self, url, filename=None):
        self.output_filename = filename
        if self.output_filename is None:
            self.output_filename = url.split("/")[-1]
            self.output_filename = parse.unquote(self.output_filename)
        self.output_path = os.path.join(self.storage_location, self.output_filename)

        yesno = control.yesno_dialog(control.ADDON_NAME, f'''
        Do you want to download "[I]{self.output_filename}[/I]" to:
            {self.output_path[:50]}
            {self.output_path[50:100]}
        ''')
        if not yesno:
            return False

        self.url_hash = database._generate_md5(url)
        if not self.create_download_task(self.url_hash):
            return False

        self.progress = 0
        self.speed = 0
        self.status = "downloading"

        head = requests.head(url, allow_redirects=True)
        self.file_size = int(head.headers.get("content-length", None))
        self.file_size_display = self.get_display_size(self.file_size)

        r = requests.get(url, stream=True)
        chunks = r.iter_content(chunk_size=1024 * 1024 * 8)

        control.notify(control.ADDON_NAME, 'Download Started')

        with open(self.output_path, 'wb') as f:
            for chunk in chunks:
                if chunk:
                    f.write(chunk)
                    self.update_status(len(chunk))
                    self.update_task_info(self.url_hash, self.download)
        self.download['status'] = 'DONE'
        self.update_task_info(self.url_hash, self.download)
        if self.canceled:
            os.remove(self.output_path)
            control.notify(control.ADDON_NAME, "Download Canceled")

    def update_status(self, chunk_size):
        """
        :param chunk_size: int
        :return: None
        """
        self.bytes_consumed += chunk_size
        self.progress = int((float(self.bytes_consumed) / self.file_size) * 100)
        self.speed = self.bytes_consumed / (CLOCK() - self._start_time)
        self.remaining_seconds = float(self.file_size - self.bytes_consumed) / self.speed
        self.update_download()

    @staticmethod
    def safe_round(x, y=0):
        """
        equal rounding, it's up to 15 digits behind the comma.
        """
        place = 10**y
        rounded = (int(x * place + 0.5 if x >= 0 else -0.5)) / place
        if rounded == int(rounded):
            rounded = int(rounded)
        return rounded

    def get_remaining_time_display(self):
        """
        Returns a display friendly version of the remaining time
        :return: String
        """

        seconds = self.remaining_seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    @staticmethod
    def get_display_size(size_bytes):
        size_names = ("B", "KB", "MB", "GB", "TB")
        size = 0.0
        name_idx = 0

        if size_bytes is not None and size_bytes > 0:
            name_idx = int(math.floor(math.log(size_bytes, 1024)))
            if name_idx > (last_size_value := len(size_names) - 1):
                name_idx = last_size_value
            chunk = math.pow(1024, name_idx)
            size = round(size_bytes / chunk, 2)

        return f"{size} {size_names[name_idx]}"

    def get_display_speed(self):

        """
        Returns a display friendly version of the current speed
        :return: String
        """

        speed = self.speed
        speed_categories = ["B/s", "KB/s", "MB/s"]
        if self.progress >= 100:
            return "-"
        for i in speed_categories:
            if speed < 1024:
                return f"{self.safe_round(speed, 2)} {i}"
            else:
                speed = speed / 1024

    def update_download(self):
        self.download = {
            "speed": self.get_display_speed(),
            "progress": self.progress,
            "filename": self.output_filename,
            "eta": self.get_remaining_time_display(),
            "filesize": self.file_size_display,
            "downloaded": self.get_display_size(self.bytes_consumed),
            "status": self.status,
            'hash': self.url_hash
        }


manager = Manager()
