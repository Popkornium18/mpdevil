import gi
from gettext import ngettext
from mpdevil.gui.main_window.auto_sized_icon import AutoSizedIcon

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class PlaybackControl(Gtk.ButtonBox):
    def __init__(self, client, settings):
        super().__init__(layout_style=Gtk.ButtonBoxStyle.EXPAND)
        self._client = client
        self._settings = settings

        # widgets
        self._play_button_icon = AutoSizedIcon(
            "media-playback-start-symbolic", "icon-size", self._settings
        )
        self._play_button = Gtk.Button(
            image=self._play_button_icon, action_name="mpd.toggle-play", can_focus=False
        )
        self._stop_button = Gtk.Button(
            image=AutoSizedIcon(
                "media-playback-stop-symbolic", "icon-size", self._settings
            ),
            action_name="mpd.stop",
            can_focus=False,
            no_show_all=True,
        )
        self._prev_button = Gtk.Button(
            image=AutoSizedIcon(
                "media-skip-backward-symbolic", "icon-size", self._settings
            ),
            action_name="mpd.prev",
            can_focus=False,
        )
        self._next_button = Gtk.Button(
            image=AutoSizedIcon(
                "media-skip-forward-symbolic", "icon-size", self._settings
            ),
            action_name="mpd.next",
            can_focus=False,
        )

        # connect
        self._settings.connect("changed::mini-player", self._mini_player)
        self._settings.connect("changed::show-stop", self._mini_player)
        self._client.emitter.connect("state", self._on_state)
        self._client.emitter.connect("playlist", self._refresh_tooltips)
        self._client.emitter.connect("current_song", self._refresh_tooltips)
        self._client.emitter.connect("disconnected", self._on_disconnected)

        # packing
        self.pack_start(self._prev_button, True, True, 0)
        self.pack_start(self._play_button, True, True, 0)
        self.pack_start(self._stop_button, True, True, 0)
        self.pack_start(self._next_button, True, True, 0)
        self._mini_player()

    def _refresh_tooltips(self, *args):
        status = self._client.status()
        song = status.get("song")
        length = status.get("playlistlength")
        if song is None or length is None:
            self._prev_button.set_tooltip_text("")
            self._next_button.set_tooltip_text("")
        else:
            elapsed = int(song)
            rest = int(length) - elapsed - 1
            elapsed_songs = ngettext("{number} song", "{number} songs", elapsed).format(
                number=elapsed
            )
            rest_songs = ngettext("{number} song", "{number} songs", rest).format(
                number=rest
            )
            self._prev_button.set_tooltip_text(elapsed_songs)
            self._next_button.set_tooltip_text(rest_songs)

    def _mini_player(self, *args):
        visibility = self._settings.get_boolean(
            "show-stop"
        ) and not self._settings.get_boolean("mini-player")
        self._stop_button.set_property("visible", visibility)

    def _on_state(self, emitter, state):
        if state == "play":
            self._play_button_icon.set_property(
                "icon-name", "media-playback-pause-symbolic"
            )
        else:
            self._play_button_icon.set_property(
                "icon-name", "media-playback-start-symbolic"
            )

    def _on_disconnected(self, *args):
        self._prev_button.set_tooltip_text("")
        self._next_button.set_tooltip_text("")
