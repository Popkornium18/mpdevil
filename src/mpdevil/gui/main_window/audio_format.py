import gi

from mpdevil.mpd_client_wrapper import Format

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango


class AudioFormat(Gtk.Box):
    def __init__(self, client, settings):
        super().__init__(spacing=6)
        self._client = client
        self._settings = settings
        self._file_type_label = Gtk.Label(xalign=1, visible=True)
        self._separator_label = Gtk.Label(xalign=1, visible=True)
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontFeatures.new("tnum 1"))
        self._brate_label = Gtk.Label(
            xalign=1, width_chars=5, visible=True, attributes=attrs
        )
        self._format_label = Gtk.Label(visible=True)

        # connect
        self._settings.connect("changed::mini-player", self._mini_player)
        self._settings.connect("changed::show-audio-format", self._mini_player)
        self._client.emitter.connect("audio", self._on_audio)
        self._client.emitter.connect("bitrate", self._on_bitrate)
        self._client.emitter.connect("current_song", self._on_song_changed)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)

        # packing
        hbox = Gtk.Box(halign=Gtk.Align.END, visible=True)
        hbox.pack_start(self._brate_label, False, False, 0)
        hbox.pack_start(self._separator_label, False, False, 0)
        hbox.pack_start(self._file_type_label, False, False, 0)
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, visible=True
        )
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self._format_label, False, False, 0)
        self.pack_start(Gtk.Separator(visible=True), False, False, 0)
        self.pack_start(vbox, False, False, 0)
        self.pack_start(Gtk.Separator(visible=True), False, False, 0)
        self._mini_player()

    def _mini_player(self, *args):
        visibility = self._settings.get_boolean(
            "show-audio-format"
        ) and not self._settings.get_boolean("mini-player")
        self.set_property("no-show-all", not (visibility))
        self.set_property("visible", visibility)

    def _on_audio(self, emitter, audio_format):
        if audio_format is None:
            self._format_label.set_markup("<small> </small>")
        else:
            self._format_label.set_markup(f"<small>{Format(audio_format)}</small>")

    def _on_bitrate(self, emitter, brate):
        # handle unknown bitrates: https://github.com/MusicPlayerDaemon/MPD/issues/428#issuecomment-442430365
        if brate is None:
            self._brate_label.set_text("—")
        else:
            self._brate_label.set_text(brate)

    def _on_song_changed(self, *args):
        current_song = self._client.currentsong()
        if current_song:
            file_type = current_song["file"].split(".")[-1].split("/")[0].upper()
            self._separator_label.set_text(" kb∕s • ")
            self._file_type_label.set_text(file_type)
        else:
            self._file_type_label.set_text("")
            self._separator_label.set_text(" kb∕s")
            self._format_label.set_markup("<small> </small>")

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self._brate_label.set_text("—")
        self._separator_label.set_text(" kb/s")
        self._file_type_label.set_text("")
        self._format_label.set_markup("<small> </small>")

    def _on_reconnected(self, *args):
        self.set_sensitive(True)
