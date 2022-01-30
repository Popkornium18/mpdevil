import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio


class AutoSizedIcon(Gtk.Image):
    def __init__(self, icon_name, settings_key, settings):
        super().__init__(icon_name=icon_name)
        settings.bind(settings_key, self, "pixel-size", Gio.SettingsBindFlags.GET)
