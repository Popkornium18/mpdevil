from gettext import gettext as _, ngettext
import gi
import threading
from mpdevil.decorators import main_thread_function
from mpdevil.gui.main_window.songs_window import SongsWindow

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GObject, GLib


class SearchThread(threading.Thread):
    def __init__(self, client, search_entry, songs_window, hits_label, search_tag):
        super().__init__(daemon=True)
        self._client = client
        self._search_entry = search_entry
        self._songs_view = songs_window.get_treeview()
        self._store = self._songs_view.get_model()
        self._action_bar = songs_window.get_action_bar()
        self._hits_label = hits_label
        self._search_tag = search_tag
        self._stop_flag = False
        self._callback = None

    def set_callback(self, callback):
        self._callback = callback

    def stop(self):
        self._stop_flag = True

    def start(self):
        self._songs_view.clear()
        self._hits_label.set_text("")
        self._action_bar.set_sensitive(False)
        self._search_text = self._search_entry.get_text()
        if self._search_text:
            super().start()
        else:
            self._exit()

    def run(self):
        hits = 0
        stripe_size = 1000
        songs = self._get_songs(0, stripe_size)
        stripe_start = stripe_size
        while songs:
            hits += len(songs)
            if not self._append_songs(songs):
                self._exit()
                return
            GLib.idle_add(self._search_entry.progress_pulse)
            GLib.idle_add(
                self._hits_label.set_text,
                ngettext("{hits} hit", "{hits} hits", hits).format(hits=hits),
            )
            stripe_end = stripe_start + stripe_size
            songs = self._get_songs(stripe_start, stripe_end)
            stripe_start = stripe_end
        if hits > 0:
            GLib.idle_add(self._action_bar.set_sensitive, True)
        self._exit()

    def _exit(self):
        def callback():
            self._search_entry.set_progress_fraction(0.0)
            if self._callback is not None:
                self._callback()
            return False

        GLib.idle_add(callback)

    @main_thread_function
    def _get_songs(self, start, end):
        if self._stop_flag:
            return []
        else:
            self._client.restrict_tagtypes("track", "title", "artist", "album")
            songs = self._client.search(
                self._search_tag, self._search_text, "window", f"{start}:{end}"
            )
            self._client.tagtypes("all")
            return songs

    @main_thread_function
    def _append_songs(self, songs):
        for song in songs:
            if self._stop_flag:
                return False
            try:
                int_track = int(song["track"][0])
            except ValueError:
                int_track = 0
            self._store.insert_with_valuesv(
                -1,
                range(7),
                [
                    song["track"][0],
                    song["title"][0],
                    str(song["artist"]),
                    song["album"][0],
                    str(song["duration"]),
                    song["file"],
                    int_track,
                ],
            )
        return True


class SearchWindow(Gtk.Box):
    __gsignals__ = {"close": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._client = client

        # widgets
        self._tag_combo_box = Gtk.ComboBoxText()
        self.search_entry = Gtk.SearchEntry()
        self._hits_label = Gtk.Label(xalign=1)
        close_button = Gtk.Button(
            image=Gtk.Image.new_from_icon_name(
                "window-close-symbolic", Gtk.IconSize.BUTTON
            ),
            relief=Gtk.ReliefStyle.NONE,
        )

        # songs window
        # (track, title, artist, album, duration, file, sort track)
        self._store = Gtk.ListStore(str, str, str, str, str, str, int)
        self._store.set_default_sort_func(lambda *args: 0)
        self._songs_window = SongsWindow(self._client, self._store, 5)
        self._action_bar = self._songs_window.get_action_bar()
        self._songs_view = self._songs_window.get_treeview()

        # columns
        renderer_text = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True
        )
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontFeatures.new("tnum 1"))
        renderer_text_tnum = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True, attributes=attrs
        )
        renderer_text_ralign_tnum = Gtk.CellRendererText(xalign=1.0, attributes=attrs)
        column_data = (
            (_("No"), renderer_text_ralign_tnum, False, 0, 6),
            (_("Title"), renderer_text, True, 1, 1),
            (_("Artist"), renderer_text, True, 2, 2),
            (_("Album"), renderer_text, True, 3, 3),
            (_("Length"), renderer_text_tnum, False, 4, 4),
        )
        for title, renderer, expand, text, sort in column_data:
            column = Gtk.TreeViewColumn(title, renderer, text=text)
            column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
            column.set_property("resizable", False)
            column.set_property("expand", expand)
            column.set_sort_column_id(sort)
            self._songs_view.append_column(column)

        # search thread
        self._search_thread = SearchThread(
            self._client, self.search_entry, self._songs_window, self._hits_label, "any"
        )

        # connect
        self.search_entry.connect("activate", self._search)
        self._search_entry_changed = self.search_entry.connect(
            "search-changed", self._search
        )
        self.search_entry.connect(
            "focus_in_event", self._on_search_entry_focus_event, True
        )
        self.search_entry.connect(
            "focus_out_event", self._on_search_entry_focus_event, False
        )
        self._tag_combo_box_changed = self._tag_combo_box.connect(
            "changed", self._search
        )
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("updated_db", self._search)
        close_button.connect("clicked", lambda *args: self.emit("close"))

        # packing
        hbox = Gtk.Box(spacing=6, border_width=6)
        hbox.pack_start(close_button, False, False, 0)
        hbox.pack_start(self.search_entry, True, True, 0)
        hbox.pack_end(self._tag_combo_box, False, False, 0)
        self._hits_label.set_margin_end(6)
        self._action_bar.pack_end(self._hits_label)
        self.pack_start(hbox, False, False, 0)
        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )
        self.pack_start(self._songs_window, True, True, 0)

    def _on_disconnected(self, *args):
        self._search_thread.stop()

    def _on_reconnected(self, *args):
        def callback():
            self._action_bar.set_sensitive(False)
            self._songs_view.clear()
            self._hits_label.set_text("")
            self.search_entry.handler_block(self._search_entry_changed)
            self.search_entry.set_text("")
            self.search_entry.handler_unblock(self._search_entry_changed)
            self._tag_combo_box.handler_block(self._tag_combo_box_changed)
            self._tag_combo_box.remove_all()
            self._tag_combo_box.append_text(_("all tags"))
            for tag in self._client.tagtypes():
                if not tag.startswith("MUSICBRAINZ"):
                    self._tag_combo_box.append_text(tag)
            self._tag_combo_box.set_active(0)
            self._tag_combo_box.handler_unblock(self._tag_combo_box_changed)

        if self._search_thread.is_alive():
            self._search_thread.set_callback(callback)
            self._search_thread.stop()
        else:
            callback()

    def _search(self, *args):
        def callback():
            if self._tag_combo_box.get_active() == 0:
                search_tag = "any"
            else:
                search_tag = self._tag_combo_box.get_active_text()
            self._search_thread = SearchThread(
                self._client,
                self.search_entry,
                self._songs_window,
                self._hits_label,
                search_tag,
            )
            self._search_thread.start()

        if self._search_thread.is_alive():
            self._search_thread.set_callback(callback)
            self._search_thread.stop()
        else:
            callback()

    def _on_search_entry_focus_event(self, widget, event, focus):
        app = self.get_toplevel().get_application()
        if focus:
            app.set_accels_for_action("mpd.toggle-play", [])
        else:
            app.set_accels_for_action("mpd.toggle-play", ["space"])
