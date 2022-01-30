import threading
from gettext import gettext as _
import gi
import bs4
import requests
from mpdevil.constants import FALLBACK_COVER
from mpdevil.gui.main_window.popover import AlbumPopover


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, GdkPixbuf, GLib


class MainCover(Gtk.Image):
    def __init__(self, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings
        # set default size
        size = self._settings.get_int("track-cover")
        self.set_size_request(size, size)

        # connect
        self._client.emitter.connect("current_song", self._refresh)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self._settings.connect("changed::track-cover", self._on_settings_changed)

    def _clear(self):
        size = self._settings.get_int("track-cover")
        self.set_from_pixbuf(
            GdkPixbuf.Pixbuf.new_from_file_at_size(FALLBACK_COVER, size, size)
        )

    def _refresh(self, *args):
        song = self._client.currentsong()
        if song:
            self.set_from_pixbuf(
                self._client.get_cover(song).get_pixbuf(
                    self._settings.get_int("track-cover")
                )
            )
        else:
            self._clear()

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self._clear()

    def _on_reconnected(self, *args):
        self.set_sensitive(True)

    def _on_settings_changed(self, *args):
        size = self._settings.get_int("track-cover")
        self.set_size_request(size, size)
        self._refresh()


class CoverEventBox(Gtk.EventBox):
    def __init__(self, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings

        # album popover
        self._album_popover = AlbumPopover(self._client, self._settings)

        # connect
        self._button_press_event = self.connect(
            "button-press-event", self._on_button_press_event
        )
        self._client.emitter.connect("disconnected", self._on_disconnected)

    def _on_button_press_event(self, widget, event):
        if self._settings.get_boolean("mini-player"):
            if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
                window = self.get_toplevel()
                window.begin_move_drag(1, event.x_root, event.y_root, Gdk.CURRENT_TIME)
        else:
            if self._client.connected():
                song = self._client.currentsong()
                if song:
                    tags = (
                        song["albumartist"][0],
                        song["albumartistsort"][0],
                        song["album"][0],
                        song["albumsort"][0],
                        song["date"][0],
                    )
                    if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
                        self._client.album_to_playlist(*tags)
                    elif (
                        event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS
                    ):
                        self._client.album_to_playlist(*tags, "play")
                    elif event.button == 2 and event.type == Gdk.EventType.BUTTON_PRESS:
                        self._client.album_to_playlist(*tags, "append")
                    elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                        self._album_popover.open(*tags, widget, event.x, event.y)

    def _on_disconnected(self, *args):
        self._album_popover.popdown()


class LyricsWindow(Gtk.ScrolledWindow):
    def __init__(self, client, settings):
        super().__init__()
        self._settings = settings
        self._client = client
        self._displayed_song_file = None

        # text view
        self._text_view = Gtk.TextView(
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.WORD,
            justification=Gtk.Justification.CENTER,
            opacity=0.9,
            left_margin=5,
            right_margin=5,
            bottom_margin=5,
            top_margin=3,
        )

        # text buffer
        self._text_buffer = self._text_view.get_buffer()

        # connect
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._song_changed = self._client.emitter.connect("current_song", self._refresh)
        self._client.emitter.handler_block(self._song_changed)

        # packing
        self.add(self._text_view)

    def enable(self, *args):
        current_song = self._client.currentsong()
        if current_song:
            if current_song["file"] != self._displayed_song_file:
                self._refresh()
        else:
            if self._displayed_song_file is not None:
                self._refresh()
        self._client.emitter.handler_unblock(self._song_changed)
        GLib.idle_add(self._text_view.grab_focus)  # focus textview

    def disable(self, *args):
        self._client.emitter.handler_block(self._song_changed)

    def _get_lyrics(self, title, artist):
        replaces = (
            (" ", "+"),
            (".", "_"),
            ("@", "_"),
            (",", "_"),
            (";", "_"),
            ("&", "_"),
            ("\\", "_"),
            ("/", "_"),
            ('"', "_"),
            ("(", "_"),
            (")", "_"),
        )
        for char1, char2 in replaces:
            title = title.replace(char1, char2)
            artist = artist.replace(char1, char2)
        req = requests.get(
            f"https://www.letras.mus.br/winamp.php?musica={title}&artista={artist}"
        )
        soup = bs4.BeautifulSoup(req.text, "html.parser")
        soup = soup.find(id="letra-cnt")
        if soup is None:
            raise ValueError("Not found")
        paragraphs = [i for i in soup.children][
            1
        ]  # remove unneded paragraphs (NavigableString)
        lyrics = ""
        for paragraph in paragraphs:
            for line in paragraph.stripped_strings:
                lyrics += line + "\n"
            lyrics += "\n"
        output = lyrics[:-2]  # omit last two newlines
        if output:
            return output
        else:  # assume song is instrumental when lyrics are empty
            return "Instrumental"

    def _display_lyrics(self, current_song):
        GLib.idle_add(self._text_buffer.set_text, _("searching…"), -1)
        try:
            text = self._get_lyrics(current_song["title"][0], current_song["artist"][0])
        except requests.exceptions.ConnectionError:
            self._displayed_song_file = None
            text = _("connection error")
        except ValueError:
            text = _("lyrics not found")
        GLib.idle_add(self._text_buffer.set_text, text, -1)

    def _refresh(self, *args):
        current_song = self._client.currentsong()
        if current_song:
            self._displayed_song_file = current_song["file"]
            update_thread = threading.Thread(
                target=self._display_lyrics,
                kwargs={"current_song": current_song},
                daemon=True,
            )
            update_thread.start()
        else:
            self._displayed_song_file = None
            self._text_buffer.set_text("", -1)

    def _on_disconnected(self, *args):
        self._displayed_song_file = None
        self._text_buffer.set_text("", -1)


class CoverLyricsWindow(Gtk.Overlay):
    def __init__(self, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings

        # cover
        main_cover = MainCover(self._client, self._settings)
        self._cover_event_box = CoverEventBox(self._client, self._settings)

        # lyrics button
        self.lyrics_button = Gtk.ToggleButton(
            image=Gtk.Image.new_from_icon_name(
                "org.mpdevil.mpdevil-lyrics-symbolic", Gtk.IconSize.BUTTON
            ),
            tooltip_text=_("Lyrics"),
            can_focus=False,
        )
        self.lyrics_button.get_style_context().add_class("osd")

        # lyrics window
        self._lyrics_window = LyricsWindow(self._client, self._settings)

        # revealer
        self._lyrics_button_revealer = Gtk.Revealer(
            child=self.lyrics_button,
            transition_duration=0,
            margin_top=6,
            margin_end=6,
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
        )
        self._settings.bind(
            "show-lyrics-button",
            self._lyrics_button_revealer,
            "reveal-child",
            Gio.SettingsBindFlags.DEFAULT,
        )

        # stack
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.OVER_DOWN_UP)
        self._stack.add_named(self._cover_event_box, "cover")
        self._stack.add_named(self._lyrics_window, "lyrics")
        self._stack.set_visible_child(self._cover_event_box)

        # connect
        self.lyrics_button.connect("toggled", self._on_lyrics_toggled)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)

        # packing
        self.add(main_cover)
        self.add_overlay(self._stack)
        self.add_overlay(self._lyrics_button_revealer)

    def _on_reconnected(self, *args):
        self.lyrics_button.set_sensitive(True)

    def _on_disconnected(self, *args):
        self.lyrics_button.set_active(False)
        self.lyrics_button.set_sensitive(False)

    def _on_lyrics_toggled(self, widget):
        if widget.get_active():
            self._stack.set_visible_child(self._lyrics_window)
            self._lyrics_window.enable()
        else:
            self._stack.set_visible_child(self._cover_event_box)
            self._lyrics_window.disable()
