import gi
from mpdevil.gui.main_window.browser.album_list import AlbumList
from mpdevil.gui.main_window.browser.genre_list import GenreList
from mpdevil.gui.main_window.browser.artist_list import ArtistList

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio


class Browser(Gtk.Paned):
    def __init__(self, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings

        # widgets
        self._genre_list = GenreList(self._client)
        self._artist_list = ArtistList(self._client, self._settings, self._genre_list)
        self._album_list = AlbumList(self._client, self._settings, self._artist_list)
        genre_window = Gtk.ScrolledWindow(child=self._genre_list)
        artist_window = Gtk.ScrolledWindow(child=self._artist_list)
        album_window = Gtk.ScrolledWindow(child=self._album_list)

        # hide/show genre filter
        self._genre_list.set_property("visible", True)
        self._settings.bind(
            "genre-filter",
            genre_window,
            "no-show-all",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        self._settings.bind(
            "genre-filter", genre_window, "visible", Gio.SettingsBindFlags.GET
        )
        self._settings.connect("changed::genre-filter", self._on_genre_filter_changed)

        # packing
        album_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        album_box.pack_start(album_window, True, True, 0)
        album_box.pack_start(self._album_list.progress_bar, False, False, 0)
        self.paned1 = Gtk.Paned()
        self.paned1.pack1(artist_window, False, False)
        self.paned1.pack2(album_box, True, False)
        self.pack1(genre_window, False, False)
        self.pack2(self.paned1, True, False)

    def back_to_current_album(self, force=False):
        song = self._client.currentsong()
        if song:
            artist, genre = self._artist_list.get_artist_selected()
            # deactivate genre filter to show all artists (if needed)
            if song["genre"][0] != genre or force:
                self._genre_list.deactivate()
            # select artist
            if artist is None and not force:  # all artists selected
                self._artist_list.highlight_selected()
            else:  # one artist selected
                self._artist_list.select(
                    (song["albumartist"][0], song["albumartistsort"][0])
                )
            self._album_list.scroll_to_current_album()
        else:
            self._genre_list.deactivate()

    def _on_genre_filter_changed(self, settings, key):
        if self._client.connected():
            if not settings.get_boolean(key):
                self._genre_list.deactivate()
