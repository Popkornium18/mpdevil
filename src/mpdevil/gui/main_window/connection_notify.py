from gettext import gettext as _
import gi
from mpdevil.constants import FALLBACK_SOCKET

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import Gtk


class ConnectionNotify(Gtk.Revealer):
    def __init__(self, client, settings):
        super().__init__(valign=Gtk.Align.START, halign=Gtk.Align.CENTER)
        self._client = client
        self._settings = settings

        # widgets
        self._label = Gtk.Label(wrap=True)
        connect_button = Gtk.Button(label=_("Connect"))
        settings_button = Gtk.Button(
            label=_("Preferences"), action_name="win.profile-settings"
        )

        # connect
        connect_button.connect("clicked", self._on_connect_button_clicked)
        self._client.emitter.connect("connection_error", self._on_connection_error)
        self._client.emitter.connect("reconnected", self._on_reconnected)

        # packing
        box = Gtk.Box(spacing=12)
        box.get_style_context().add_class("app-notification")
        box.pack_start(self._label, False, True, 6)
        box.pack_end(connect_button, False, True, 0)
        box.pack_end(settings_button, False, True, 0)
        self.add(box)

    def _on_connection_error(self, *args):
        profile = self._settings.get_active_profile()
        if profile.get_boolean("socket-connection"):
            socket = profile.get_string("socket")
            if not socket:
                socket = FALLBACK_SOCKET
            text = _("Connection to “{socket}” failed").format(socket=socket)
        else:
            text = _("Connection to “{host}:{port}” failed").format(
                host=profile.get_string("host"), port=profile.get_int("port")
            )
        self._label.set_text(text)
        self.set_reveal_child(True)

    def _on_reconnected(self, *args):
        self.set_reveal_child(False)

    def _on_connect_button_clicked(self, *args):
        self._client.reconnect()
