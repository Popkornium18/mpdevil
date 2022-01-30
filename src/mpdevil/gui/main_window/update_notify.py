from gettext import gettext as _
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class UpdateNotify(Gtk.Revealer):
    def __init__(self, client):
        super().__init__(valign=Gtk.Align.START, halign=Gtk.Align.CENTER)
        self._client = client

        # widgets
        self._spinner = Gtk.Spinner()
        label = Gtk.Label(label=_("Updating Database…"))

        # connect
        self._client.emitter.connect("updating_db", self._show)
        self._client.emitter.connect("updated_db", self._hide)
        self._client.emitter.connect("disconnected", self._hide)

        # packing
        box = Gtk.Box(spacing=12)
        box.get_style_context().add_class("app-notification")
        box.pack_start(self._spinner, False, False, 0)
        box.pack_end(label, True, True, 0)
        self.add(box)

    def _show(self, *args):
        self._spinner.start()
        self.set_reveal_child(True)

    def _hide(self, *args):
        self._spinner.stop()
        self.set_reveal_child(False)
