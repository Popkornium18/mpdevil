import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib
import functools
import threading


def main_thread_function(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        def glib_callback(event, result, *args, **kwargs):
            try:
                result.append(func(*args, **kwargs))
            except Exception as e:  # handle exceptions to avoid deadlocks
                result.append(e)
            event.set()
            return False

        event = threading.Event()
        result = []
        GLib.idle_add(glib_callback, event, result, *args, **kwargs)
        event.wait()
        if isinstance(result[0], Exception):
            raise result[0]
        else:
            return result[0]

    return wrapper_decorator
