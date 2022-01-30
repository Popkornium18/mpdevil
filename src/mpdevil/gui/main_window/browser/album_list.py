import gi
import threading
from gettext import gettext as _

from mpdevil.constants import FALLBACK_COVER
from mpdevil.decorators import main_thread_function
from mpdevil.gui.main_window.browser.popover import AlbumPopover

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib


class AlbumLoadingThread(threading.Thread):
    def __init__(self, client, settings, progress_bar, iconview, store, artist, genre):
        super().__init__(daemon=True)
        self._client = client
        self._settings = settings
        self._progress_bar = progress_bar
        self._iconview = iconview
        self._store = store
        self._artist = artist
        self._genre = genre

    def _get_albums(self):
        for albumartist, albumartistsort in self._artists:
            albums = main_thread_function(self._client.list)(
                "album",
                "albumartist",
                albumartist,
                "albumartistsort",
                albumartistsort,
                *self._genre_filter,
                "group",
                "date",
                "group",
                "albumsort",
            )
            for album in albums:
                album["albumartist"] = albumartist
                album["albumartistsort"] = albumartistsort
                yield album

    def set_callback(self, callback):
        self._callback = callback

    def stop(self):
        self._stop_flag = True

    def start(self):
        self._settings.set_property("cursor-watch", True)
        self._progress_bar.show()
        self._callback = None
        self._stop_flag = False
        self._iconview.set_model(None)
        self._store.clear()
        self._cover_size = self._settings.get_int("album-cover")
        if self._artist is None:
            self._iconview.set_markup_column(2)  # show artist names
        else:
            self._iconview.set_markup_column(1)  # hide artist names
        if self._genre is None:
            self._genre_filter = ()
        else:
            self._genre_filter = ("genre", self._genre)
        if self._artist is None:
            self._artists = self._client.get_artists(self._genre)
        else:
            self._artists = [self._artist]
        super().start()

    def run(self):
        # temporarily display all albums with fallback cover
        fallback_cover = GdkPixbuf.Pixbuf.new_from_file_at_size(
            FALLBACK_COVER, self._cover_size, self._cover_size
        )
        add = main_thread_function(self._store.append)
        for i, album in enumerate(self._get_albums()):
            # album label
            if album["date"]:
                display_label = f"<b>{GLib.markup_escape_text(album['album'])}</b> ({GLib.markup_escape_text(album['date'])})"
            else:
                display_label = f"<b>{GLib.markup_escape_text(album['album'])}</b>"
            display_label_artist = (
                f"{display_label}\n{GLib.markup_escape_text(album['albumartist'])}"
            )
            # add album
            add(
                [
                    fallback_cover,
                    display_label,
                    display_label_artist,
                    album["albumartist"],
                    album["albumartistsort"],
                    album["album"],
                    album["albumsort"],
                    album["date"],
                ]
            )
            if i % 10 == 0:
                if self._stop_flag:
                    self._exit()
                    return
                GLib.idle_add(self._progress_bar.pulse)
        # sort model
        if main_thread_function(self._settings.get_boolean)("sort-albums-by-year"):
            main_thread_function(self._store.set_sort_column_id)(
                7, Gtk.SortType.ASCENDING
            )
        else:
            main_thread_function(self._store.set_sort_column_id)(
                6, Gtk.SortType.ASCENDING
            )
        GLib.idle_add(self._iconview.set_model, self._store)
        # load covers
        total = 2 * len(self._store)

        @main_thread_function
        def get_cover(row):
            if self._stop_flag:
                return None
            else:
                self._client.restrict_tagtypes("albumartist", "album")
                song = self._client.find(
                    "albumartist",
                    row[3],
                    "albumartistsort",
                    row[4],
                    "album",
                    row[5],
                    "albumsort",
                    row[6],
                    "date",
                    row[7],
                    "window",
                    "0:1",
                )[0]
                self._client.tagtypes("all")
                return self._client.get_cover(song)

        covers = []
        for i, row in enumerate(self._store):
            cover = get_cover(row)
            if cover is None:
                self._exit()
                return
            covers.append(cover)
            GLib.idle_add(self._progress_bar.set_fraction, (i + 1) / total)
        treeiter = self._store.get_iter_first()
        i = 0

        def set_cover(treeiter, cover):
            if self._store.iter_is_valid(treeiter):
                self._store.set_value(treeiter, 0, cover)

        while treeiter is not None:
            if self._stop_flag:
                self._exit()
                return
            cover = covers[i].get_pixbuf(self._cover_size)
            GLib.idle_add(set_cover, treeiter, cover)
            GLib.idle_add(self._progress_bar.set_fraction, 0.5 + (i + 1) / total)
            i += 1
            treeiter = self._store.iter_next(treeiter)
        self._exit()

    def _exit(self):
        def callback():
            self._settings.set_property("cursor-watch", False)
            self._progress_bar.hide()
            self._progress_bar.set_fraction(0)
            if self._callback is not None:
                self._callback()
            return False

        GLib.idle_add(callback)


class AlbumList(Gtk.IconView):
    def __init__(self, client, settings, artist_list):
        super().__init__(
            item_width=0,
            pixbuf_column=0,
            markup_column=1,
            activate_on_single_click=True,
        )
        self._settings = settings
        self._client = client
        self._artist_list = artist_list

        # cover, display_label, display_label_artist, albumartist, albumartistsort, album, albumsort, date
        self._store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, str, str, str, str)
        self._store.set_default_sort_func(lambda *args: 0)
        self.set_model(self._store)

        # progress bar
        self.progress_bar = Gtk.ProgressBar(no_show_all=True)

        # popover
        self._album_popover = AlbumPopover(self._client, self._settings)

        # cover thread
        self._cover_thread = AlbumLoadingThread(
            self._client,
            self._settings,
            self.progress_bar,
            self,
            self._store,
            None,
            None,
        )

        # connect
        self.connect("item-activated", self._on_item_activated)
        self.connect("button-press-event", self._on_button_press_event)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self._settings.connect("changed::sort-albums-by-year", self._sort_settings)
        self._settings.connect("changed::album-cover", self._on_cover_size_changed)
        self._artist_list.connect("item-selected", self._refresh)
        self._artist_list.connect("clear", self._clear)

    def _workaround_clear(self):
        self._store.clear()
        # workaround (scrollbar still visible after clear)
        self.set_model(None)
        self.set_model(self._store)

    def _clear(self, *args):
        def callback():
            self._album_popover.popdown()
            self._workaround_clear()

        if self._cover_thread.is_alive():
            self._cover_thread.set_callback(callback)
            self._cover_thread.stop()
        else:
            callback()

    def scroll_to_current_album(self):
        def callback():
            song = self._client.currentsong()
            album = song["album"][0]
            self.unselect_all()
            row_num = len(self._store)
            for i in range(0, row_num):
                path = Gtk.TreePath(i)
                if self._store[path][5] == album:
                    self.set_cursor(path, None, False)
                    self.select_path(path)
                    self.scroll_to_path(path, True, 0, 0)
                    break

        if self._cover_thread.is_alive():
            self._cover_thread.set_callback(callback)
        else:
            callback()

    def _sort_settings(self, *args):
        if not self._cover_thread.is_alive():
            if self._settings.get_boolean("sort-albums-by-year"):
                self._store.set_sort_column_id(7, Gtk.SortType.ASCENDING)
            else:
                self._store.set_sort_column_id(6, Gtk.SortType.ASCENDING)

    def _refresh(self, *args):
        def callback():
            if self._cover_thread.is_alive():  # already started?
                return False
            artist, genre = self._artist_list.get_artist_selected()
            self._cover_thread = AlbumLoadingThread(
                self._client,
                self._settings,
                self.progress_bar,
                self,
                self._store,
                artist,
                genre,
            )
            self._cover_thread.start()

        if self._cover_thread.is_alive():
            self._cover_thread.set_callback(callback)
            self._cover_thread.stop()
        else:
            callback()

    def _path_to_playlist(self, path, mode="default"):
        tags = self._store[path][3:8]
        self._client.album_to_playlist(*tags, mode)

    def _on_button_press_event(self, widget, event):
        path = widget.get_path_at_pos(int(event.x), int(event.y))
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            if path is not None:
                self._path_to_playlist(path, "play")
        elif event.button == 2 and event.type == Gdk.EventType.BUTTON_PRESS:
            if path is not None:
                self._path_to_playlist(path, "append")
        elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            v = self.get_vadjustment().get_value()
            h = self.get_hadjustment().get_value()
            if path is not None:
                tags = self._store[path][3:8]
                # when using "button-press-event" in iconview popovers only show up in combination with idle_add (bug in GTK?)
                GLib.idle_add(
                    self._album_popover.open, *tags, widget, event.x - h, event.y - v
                )

    def _on_item_activated(self, widget, path):
        self._path_to_playlist(path)

    def _on_disconnected(self, *args):
        self.set_sensitive(False)

    def _on_reconnected(self, *args):
        self.set_sensitive(True)

    def show_info(self):
        paths = self.get_selected_items()
        if len(paths) > 0:
            path = paths[0]
            cell = self.get_cell_rect(path, None)[1]
            rect = self.get_allocation()
            x = max(min(rect.x + cell.width // 2, rect.x + rect.width), rect.x)
            y = max(min(cell.y + cell.height // 2, rect.y + rect.height), rect.y)
            tags = self._store[path][3:8]
            self._album_popover.open(*tags, self, x, y)

    def add_to_playlist(self, mode):
        paths = self.get_selected_items()
        if len(paths) != 0:
            self._path_to_playlist(paths[0], mode)

    def _on_cover_size_changed(self, *args):
        if self._client.connected():
            self._refresh()
