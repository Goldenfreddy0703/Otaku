import json

from resources.lib.ui import control

# Cache the mal_dub JSON in memory so it's only read from disk once
_mal_dub_cache = None


def _get_mal_dub():
    global _mal_dub_cache
    if _mal_dub_cache is None:
        with open(control.maldubFile) as file:
            _mal_dub_cache = json.load(file)
    return _mal_dub_cache


def div_flavor(f):
    def wrapper(*args, **kwargs):
        if control.getBool('divflavors.dubonly') or control.getBool('divflavors.showdub'):
            return f(*args, **kwargs, mal_dub=_get_mal_dub())
        return f(*args, **kwargs)
    return wrapper
