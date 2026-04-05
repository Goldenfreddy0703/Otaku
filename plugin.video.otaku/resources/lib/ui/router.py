"""router.py - URL Route Dispatcher
====================================
Simple decorator-based router: @Route('/path') registers a handler,
router_process() dispatches incoming plugin URLs to the matching handler.
"""

ROUTES = []


class Route:
    def __init__(self, route_path):
        self.path = route_path
        self.wildcard = False
        if route_path.endswith("*"):
            self.wildcard = True
            self.path = route_path[:-1]

    def __call__(self, func):
        self.func = func
        ROUTES.append(self)
        return func


def router_process(url, params=None):
    if not params:
        params = {}
    payload = "/".join(url.split("/")[1:])
    for route_obj in ROUTES:
        if url == route_obj.path or (route_obj.wildcard and url.startswith(route_obj.path)):
            return route_obj.func(payload, params)
