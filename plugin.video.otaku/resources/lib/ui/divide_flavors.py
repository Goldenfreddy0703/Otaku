import json
from resources.lib.ui import control, database

def div_flavor(f):
    def wrapper(*args, **kwargs):
        if control.getSetting("divflavors.bool") == "true":
            dubsub_filter = control.getSetting("divflavors.menu")
            mal_dub = _get_mal_dub()

            return f(dub=mal_dub, dubsub_filter=dubsub_filter, *args, **kwargs)

        return f(*args, **kwargs)

    return wrapper


def _get_mal_dub():
    mal_dub_list = database.get_mal_dub_ids()  # Call the function that returns all mal_dub_ids
    mal_dub = {str(item): {'dub': True} for item in mal_dub_list}
    return mal_dub