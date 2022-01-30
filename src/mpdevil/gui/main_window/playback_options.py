from gettext import gettext as _
import gi
from mpdevil.gui.main_window.auto_sized_icon import AutoSizedIcon

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk


class PlaybackOptions(Gtk.ButtonBox):
    def __init__(self, client, settings):
        super().__init__(layout_style=Gtk.ButtonBoxStyle.EXPAND)
        self._client = client
        self._settings = settings

        # buttons
        self._buttons = {}
        data = (
            ("repeat", "media-playlist-repeat-symbolic", _("Repeat mode")),
            ("random", "media-playlist-shuffle-symbolic", _("Random mode")),
            ("single", "org.mpdevil.mpdevil-single-symbolic", _("Single mode")),
            ("consume", "org.mpdevil.mpdevil-consume-symbolic", _("Consume mode")),
        )
        for name, icon, tooltip in data:
            button = Gtk.ToggleButton(
                image=AutoSizedIcon(icon, "icon-size", self._settings),
                tooltip_text=tooltip,
                can_focus=False,
            )
            handler = button.connect("toggled", self._set_option, name)
            self.pack_start(button, True, True, 0)
            self._buttons[name] = (button, handler)

        # css
        self._provider = Gtk.CssProvider()
        self._provider.load_from_data(b"""image {color: @error_color;}""")  # red icon

        # connect
        for name in ("repeat", "random", "consume"):
            self._client.emitter.connect(name, self._button_refresh, name)
        self._client.emitter.connect("single", self._single_refresh)
        self._buttons["single"][0].connect(
            "button-press-event", self._on_single_button_press_event
        )
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self._settings.bind(
            "mini-player", self, "no-show-all", Gio.SettingsBindFlags.GET
        )
        self._settings.bind(
            "mini-player",
            self,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )

    def _set_option(self, widget, option):
        func = getattr(self._client, option)
        if widget.get_active():
            func("1")
        else:
            func("0")

    def _button_refresh(self, emitter, val, name):
        self._buttons[name][0].handler_block(self._buttons[name][1])
        self._buttons[name][0].set_active(val)
        self._buttons[name][0].handler_unblock(self._buttons[name][1])

    def _single_refresh(self, emitter, val):
        self._buttons["single"][0].handler_block(self._buttons["single"][1])
        self._buttons["single"][0].set_active((val in ("1", "oneshot")))
        if val == "oneshot":
            self._buttons["single"][0].get_image().get_style_context().add_provider(
                self._provider, 600
            )
        else:
            self._buttons["single"][0].get_image().get_style_context().remove_provider(
                self._provider
            )
        self._buttons["single"][0].handler_unblock(self._buttons["single"][1])

    def _on_single_button_press_event(self, widget, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            state = self._client.status()["single"]
            if state == "oneshot":
                self._client.single("0")
            else:
                self._client.single("oneshot")

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        for name in ("repeat", "random", "consume"):
            self._button_refresh(None, False, name)
        self._single_refresh(None, "0")

    def _on_reconnected(self, *args):
        self.set_sensitive(True)
