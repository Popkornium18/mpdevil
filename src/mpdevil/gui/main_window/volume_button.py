import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk


class OutputPopover(Gtk.Popover):
    def __init__(self, client, relative):
        super().__init__()
        self.set_relative_to(relative)
        self._client = client

        # widgets
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, border_width=9)
        for output in self._client.outputs():
            button = Gtk.ModelButton(
                label=f"{output['outputname']} ({output['plugin']})",
                role=Gtk.ButtonRole.CHECK,
            )
            button.get_child().set_property("xalign", 0)
            if output["outputenabled"] == "1":
                button.set_property("active", True)
            button.connect("clicked", self._on_button_clicked, output["outputid"])
            box.pack_start(button, False, False, 0)

        # connect
        self.connect("closed", lambda *args: self.destroy())

        # packing
        self.add(box)
        box.show_all()

    def _on_button_clicked(self, button, out_id):
        if button.get_property("active"):
            self._client.disableoutput(out_id)
            button.set_property("active", False)
        else:
            self._client.enableoutput(out_id)
            button.set_property("active", True)


class VolumeButton(Gtk.VolumeButton):
    def __init__(self, client, settings):
        super().__init__(use_symbolic=True, can_focus=False)
        self._client = client
        self._popover = None
        self._adj = self.get_adjustment()
        self._adj.set_step_increment(5)
        self._adj.set_page_increment(10)
        self._adj.set_upper(
            0
        )  # do not allow volume change by user when MPD has not yet reported volume (no output enabled/avail)
        settings.bind(
            "icon-size", self.get_child(), "pixel-size", Gio.SettingsBindFlags.GET
        )

        # connect
        self._changed = self.connect("value-changed", self._set_volume)
        self._client.emitter.connect("volume", self._refresh)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self.connect("button-press-event", self._on_button_press_event)

    def _set_volume(self, widget, value):
        self._client.setvol(str(int(value)))

    def _refresh(self, emitter, volume):
        self.handler_block(self._changed)
        if volume < 0:
            self.set_value(0)
            self._adj.set_upper(0)
        else:
            self._adj.set_upper(100)
            self.set_value(volume)
        self.handler_unblock(self._changed)

    def _on_button_press_event(self, widget, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            self._popover = OutputPopover(self._client, self)
            self._popover.popup()

    def _on_reconnected(self, *args):
        self.set_sensitive(True)

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self._refresh(None, -1)
        if self._popover is not None:
            self._popover.popdown()
            self._popover = None
