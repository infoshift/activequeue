from gevent import monkey
monkey.patch_all()

from server import app
import config


if config.DEBUG:
    from werkzeug.debug import DebuggedApplication
    app = DebuggedApplication(app, evalex=True)


if config.PROFILE:
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app = ProfilerMiddleware(
        app,
        sort_by=("cumtime", ),
        restrictions=("/app/server.py", 30),
    )
