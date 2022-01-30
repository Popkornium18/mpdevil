import gi
from gettext import gettext as _
from mpdevil.gui.main_window.browser.selection_list import SelectionList

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


class ArtistPopover(Gtk.Popover):
    def __init__(self, client):
        super().__init__()
        self._client = client
        self._rect = Gdk.Rectangle()
        self._artist = None
        self._genre = None

        # buttons
        vbox = Gtk.ButtonBox(orientation=Gtk.Orientation.VERTICAL, border_width=9)
        data = (
            (_("Append"), "list-add-symbolic", "append"),
            (_("Play"), "media-playback-start-symbolic", "play"),
            (_("Enqueue"), "insert-object-symbolic", "enqueue"),
        )
        for label, icon, mode in data:
            button = Gtk.ModelButton(
                label=label,
                image=Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON),
            )
            button.get_child().set_property("xalign", 0)
            button.connect("clicked", self._on_button_clicked, mode)
            vbox.pack_start(button, True, True, 0)

        self.add(vbox)
        vbox.show_all()

    def open(self, artist, genre, widget, x, y):
        self._rect.x = x
        self._rect.y = y
        self.set_pointing_to(self._rect)
        self.set_relative_to(widget)
        self._artist = artist
        self._genre = genre
        self.popup()

    def _on_button_clicked(self, widget, mode):
        self._client.artist_to_playlist(self._artist, self._genre, mode)
        self.popdown()


class ArtistList(SelectionList):
    def __init__(self, client, settings, genre_list):
        super().__init__(_("all artists"))
        self._client = client
        self._settings = settings
        self.genre_list = genre_list

        # selection
        self._selection = self.get_selection()

        # artist popover
        self._artist_popover = ArtistPopover(self._client)

        # connect
        self.connect("clear", lambda *args: self._artist_popover.popdown())
        self.connect("button-press-event", self._on_button_press_event)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        self.genre_list.connect_after("item-selected", self._refresh)

    def _refresh(self, *args):
        genre = self.genre_list.get_item_selected()
        if genre is not None:
            genre = genre[0]
        artists = self._client.get_artists(genre)
        self.set_items(artists)
        if genre is not None:
            self.select_all()
        else:
            song = self._client.currentsong()
            if song:
                artist = (song["albumartist"][0], song["albumartistsort"][0])
                self.select(artist)
            else:
                if self.length() > 0:
                    self.select_path(Gtk.TreePath(1))
                else:
                    self.select_path(Gtk.TreePath(0))

    def _on_button_press_event(self, widget, event):
        if (event.button in (2, 3) and event.type == Gdk.EventType.BUTTON_PRESS) or (
            event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS
        ):
            path_re = widget.get_path_at_pos(int(event.x), int(event.y))
            if path_re is not None:
                path = path_re[0]
                artist, genre = self.get_artist_at_path(path)
                if event.button == 1:
                    self._client.artist_to_playlist(artist, genre, "play")
                elif event.button == 2:
                    self._client.artist_to_playlist(artist, genre, "append")
                elif event.button == 3:
                    self._artist_popover.open(artist, genre, self, event.x, event.y)

    def get_artist_at_path(self, path):
        genre = self.genre_list.get_item_selected()
        artist = self.get_item_at_path(path)
        if genre is not None:
            genre = genre[0]
        return (artist, genre)

    def get_artist_selected(self):
        return self.get_artist_at_path(self.get_path_selected())

    def add_to_playlist(self, mode):
        selected_rows = self._selection.get_selected_rows()
        if selected_rows is not None:
            path = selected_rows[1][0]
            artist, genre = self.get_artist_at_path(path)
            self._client.artist_to_playlist(artist, genre, mode)

    def show_info(self):
        treeview, treeiter = self._selection.get_selected()
        if treeiter is not None:
            path = self._store.get_path(treeiter)
            artist, genre = self.get_artist_at_path(path)
            self._artist_popover.open(
                artist, genre, self, *self.get_popover_point(path)
            )

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self.clear()

    def _on_reconnected(self, *args):
        self.set_sensitive(True)
