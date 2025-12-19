import json

from resources.lib.ui import control


def div_flavor(f):
    def wrapper(*args, **kwargs):
        if control.getBool('divflavors.dubonly') or control.getBool('divflavors.showdub'):
            with open(control.maldubFile) as file:
                mal_dub = json.load(file)
            return f(*args, **kwargs, mal_dub=mal_dub)
        return f(*args, **kwargs)
    return wrapper
