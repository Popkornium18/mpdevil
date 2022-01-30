from gettext import gettext as _, ngettext
import gi
from mpdevil.gui.main_window.popover import SongPopover
from mpdevil.gui.main_window.tree_view import TreeView
from mpdevil.mpd_client_wrapper import Duration


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, Pango, GObject


class PlaylistView(TreeView):
    selected_path = GObject.Property(
        type=Gtk.TreePath, default=None
    )  # currently marked song (bold text)

    def __init__(self, client, settings):
        super().__init__(
            activate_on_single_click=True,
            reorderable=True,
            search_column=2,
            fixed_height_mode=True,
        )
        self._client = client
        self._settings = settings
        self._playlist_version = None
        self._inserted_path = None  # needed for drag and drop
        self._selection = self.get_selection()

        # store
        # (track, disc, title, artist, album, human duration, date, genre, file, weight, duration)
        self._store = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str, Pango.Weight, float
        )
        self.set_model(self._store)

        # columns
        renderer_text = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True
        )
        renderer_text_ralign = Gtk.CellRendererText(xalign=1.0)
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontFeatures.new("tnum 1"))
        renderer_text_tnum = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True, attributes=attrs
        )
        renderer_text_ralign_tnum = Gtk.CellRendererText(xalign=1.0, attributes=attrs)
        self._columns = (
            Gtk.TreeViewColumn(_("No"), renderer_text_ralign_tnum, text=0, weight=9),
            Gtk.TreeViewColumn(_("Disc"), renderer_text_ralign, text=1, weight=9),
            Gtk.TreeViewColumn(_("Title"), renderer_text, text=2, weight=9),
            Gtk.TreeViewColumn(_("Artist"), renderer_text, text=3, weight=9),
            Gtk.TreeViewColumn(_("Album"), renderer_text, text=4, weight=9),
            Gtk.TreeViewColumn(_("Length"), renderer_text_tnum, text=5, weight=9),
            Gtk.TreeViewColumn(_("Year"), renderer_text_tnum, text=6, weight=9),
            Gtk.TreeViewColumn(_("Genre"), renderer_text, text=7, weight=9),
        )
        for i, column in enumerate(self._columns):
            column.set_property("resizable", True)
            column.set_property("sizing", Gtk.TreeViewColumnSizing.FIXED)
            column.set_min_width(30)
            column.connect("notify::fixed-width", self._on_column_width, i)
        self._load_settings()

        # song popover
        self._song_popover = SongPopover(self._client, show_buttons=False)

        # connect
        self.connect("row-activated", self._on_row_activated)
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("key-release-event", self._on_key_release_event)
        self._row_deleted = self._store.connect("row-deleted", self._on_row_deleted)
        self._row_inserted = self._store.connect("row-inserted", self._on_row_inserted)

        self._client.emitter.connect("playlist", self._on_playlist_changed)
        self._client.emitter.connect("current_song", self._on_song_changed)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)

        self._settings.connect("changed::column-visibilities", self._load_settings)
        self._settings.connect("changed::column-permutation", self._load_settings)

    def _on_column_width(self, obj, typestring, pos):
        self._settings.array_modify(
            "ai", "column-sizes", pos, obj.get_property("fixed-width")
        )

    def _load_settings(self, *args):
        columns = self.get_columns()
        for column in columns:
            self.remove_column(column)
        sizes = self._settings.get_value("column-sizes").unpack()
        visibilities = self._settings.get_value("column-visibilities").unpack()
        for i in self._settings.get_value("column-permutation"):
            if sizes[i] > 0:
                self._columns[i].set_fixed_width(sizes[i])
            self._columns[i].set_visible(visibilities[i])
            self.append_column(self._columns[i])

    def _clear(self, *args):
        self._song_popover.popdown()
        self._set_playlist_info("")
        self._playlist_version = None
        self.set_property("selected-path", None)
        self._store.handler_block(self._row_inserted)
        self._store.handler_block(self._row_deleted)
        self._store.clear()
        self._store.handler_unblock(self._row_inserted)
        self._store.handler_unblock(self._row_deleted)

    def _select(self, path):
        self._unselect()
        try:
            self._store[path][9] = Pango.Weight.BOLD
            self.set_property("selected-path", path)
        except IndexError:  # invalid path
            pass

    def _unselect(self):
        if self.get_property("selected-path") is not None:
            try:
                self._store[self.get_property("selected-path")][9] = Pango.Weight.BOOK
                self.set_property("selected-path", None)
            except IndexError:  # invalid path
                self.set_property("selected-path", None)

    def scroll_to_selected_title(self):
        treeview, treeiter = self._selection.get_selected()
        if treeiter is not None:
            path = treeview.get_path(treeiter)
            self.scroll_to_cell(path, None, True, 0.25)

    def _refresh_selection(
        self,
    ):  # Gtk.TreePath(len(self._store) is used to generate an invalid TreePath (needed to unset cursor)
        self.set_cursor(Gtk.TreePath(len(self._store)), None, False)
        song = self._client.status().get("song")
        if song is None:
            self._selection.unselect_all()
            self._unselect()
        else:
            path = Gtk.TreePath(int(song))
            self._selection.select_path(path)
            self._select(path)

    def _set_playlist_info(self, text):
        if text:
            self._columns[2].set_title(" • ".join([_("Title"), text]))
        else:
            self._columns[2].set_title(_("Title"))

    def _on_button_press_event(self, widget, event):
        path_re = widget.get_path_at_pos(int(event.x), int(event.y))
        if path_re is not None:
            path = path_re[0]
            if event.button == 2 and event.type == Gdk.EventType.BUTTON_PRESS:
                self._store.remove(self._store.get_iter(path))
            elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                point = self.convert_bin_window_to_widget_coords(event.x, event.y)
                self._song_popover.open(self._store[path][8], widget, *point)

    def _on_key_release_event(self, widget, event):
        if event.keyval == Gdk.keyval_from_name("Delete"):
            treeview, treeiter = self._selection.get_selected()
            if treeiter is not None:
                try:
                    self._store.remove(treeiter)
                except:
                    pass

    def _on_row_deleted(self, model, path):  # sync treeview to mpd
        try:
            if self._inserted_path is not None:  # move
                path = int(path.to_string())
                if path > self._inserted_path:
                    path = path - 1
                if path < self._inserted_path:
                    self._inserted_path = self._inserted_path - 1
                self._client.move(path, self._inserted_path)
                self._inserted_path = None
            else:  # delete
                self._client.delete(path)  # bad song index possible
            self._playlist_version = int(self._client.status()["playlist"])
        except MPDBase.CommandError as e:
            self._playlist_version = None
            self._client.emitter.emit(
                "playlist", int(self._client.status()["playlist"])
            )
            raise e  # propagate exception

    def _on_row_inserted(self, model, path, treeiter):
        self._inserted_path = int(path.to_string())

    def _on_row_activated(self, widget, path, view_column):
        self._client.play(path)

    def _on_playlist_changed(self, emitter, version):
        self._store.handler_block(self._row_inserted)
        self._store.handler_block(self._row_deleted)
        self._song_popover.popdown()
        self._unselect()
        self._client.restrict_tagtypes(
            "track", "disc", "title", "artist", "album", "date", "genre"
        )
        songs = []
        if self._playlist_version is not None:
            songs = self._client.plchanges(self._playlist_version)
        else:
            songs = self._client.playlistinfo()
        self._client.tagtypes("all")
        if songs:
            self.freeze_child_notify()
            self._set_playlist_info("")
            for song in songs:
                try:
                    treeiter = self._store.get_iter(song["pos"])
                    self._store.set(
                        treeiter,
                        0,
                        song["track"][0],
                        1,
                        song["disc"][0],
                        2,
                        song["title"][0],
                        3,
                        str(song["artist"]),
                        4,
                        song["album"][0],
                        5,
                        str(song["duration"]),
                        6,
                        song["date"][0],
                        7,
                        str(song["genre"]),
                        8,
                        song["file"],
                        9,
                        Pango.Weight.BOOK,
                        10,
                        float(song["duration"]),
                    )
                except:
                    self._store.insert_with_valuesv(
                        -1,
                        range(11),
                        [
                            song["track"][0],
                            song["disc"][0],
                            song["title"][0],
                            str(song["artist"]),
                            song["album"][0],
                            str(song["duration"]),
                            song["date"][0],
                            str(song["genre"]),
                            song["file"],
                            Pango.Weight.BOOK,
                            float(song["duration"]),
                        ],
                    )
            self.thaw_child_notify()
        for i in reversed(
            range(int(self._client.status()["playlistlength"]), len(self._store))
        ):
            treeiter = self._store.get_iter(i)
            self._store.remove(treeiter)
        playlist_length = len(self._store)
        if playlist_length == 0:
            self._set_playlist_info("")
        else:
            duration = Duration(sum([row[10] for row in self._store]))
            translated_string = ngettext(
                "{number} song ({duration})",
                "{number} songs ({duration})",
                playlist_length,
            )
            self._set_playlist_info(
                translated_string.format(number=playlist_length, duration=duration)
            )
        self._refresh_selection()
        if self._playlist_version != version:
            self.scroll_to_selected_title()
        self._playlist_version = version
        self._store.handler_unblock(self._row_inserted)
        self._store.handler_unblock(self._row_deleted)

    def _on_song_changed(self, *args):
        self._refresh_selection()
        if self._client.status()["state"] == "play":
            self.scroll_to_selected_title()

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self._clear()

    def _on_reconnected(self, *args):
        self.set_sensitive(True)

    def show_info(self):
        treeview, treeiter = self._selection.get_selected()
        if treeiter is not None:
            path = self._store.get_path(treeiter)
            self._song_popover.open(
                self._store[path][8], self, *self.get_popover_point(path)
            )


class PlaylistWindow(Gtk.Overlay):
    def __init__(self, client, settings):
        super().__init__()
        self._back_to_current_song_button = Gtk.Button(
            image=Gtk.Image.new_from_icon_name(
                "go-previous-symbolic", Gtk.IconSize.BUTTON
            ),
            tooltip_text=_("Scroll to current song"),
            can_focus=False,
        )
        self._back_to_current_song_button.get_style_context().add_class("osd")
        self._back_button_revealer = Gtk.Revealer(
            child=self._back_to_current_song_button,
            transition_duration=0,
            margin_bottom=6,
            margin_start=6,
            halign=Gtk.Align.START,
            valign=Gtk.Align.END,
        )
        self._treeview = PlaylistView(client, settings)
        scroll = Gtk.ScrolledWindow(child=self._treeview)

        # connect
        self._back_to_current_song_button.connect(
            "clicked", self._on_back_to_current_song_button_clicked
        )
        scroll.get_vadjustment().connect(
            "value-changed", self._on_show_hide_back_button
        )
        self._treeview.connect("notify::selected-path", self._on_show_hide_back_button)
        settings.bind("mini-player", self, "no-show-all", Gio.SettingsBindFlags.GET)
        settings.bind(
            "mini-player",
            self,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )

        # packing
        self.add(scroll)
        self.add_overlay(self._back_button_revealer)

    def _on_show_hide_back_button(self, *args):
        visible_range = self._treeview.get_visible_range()
        if (
            visible_range is None
            or self._treeview.get_property("selected-path") is None
        ):
            self._back_button_revealer.set_reveal_child(False)
        else:
            current_song_visible = (
                visible_range[0]
                <= self._treeview.get_property("selected-path")
                <= visible_range[1]
            )
            self._back_button_revealer.set_reveal_child(not (current_song_visible))

    def _on_back_to_current_song_button_clicked(self, *args):
        self._treeview.set_cursor(
            Gtk.TreePath(len(self._treeview.get_model())), None, False
        )  # unset cursor
        if self._treeview.get_property("selected-path") is not None:
            self._treeview.get_selection().select_path(
                self._treeview.get_property("selected-path")
            )
        self._treeview.scroll_to_selected_title()
