from gettext import gettext as _
import gi
from mpdevil.gui.main_window.song_popover import SongPopover
from mpdevil.gui.main_window.tree_view import TreeView

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, Gdk


class SongsView(TreeView):
    def __init__(self, client, store, file_column_id):
        super().__init__(model=store, search_column=-1, activate_on_single_click=True)
        self._client = client
        self._store = store
        self._file_column_id = file_column_id

        # selection
        self._selection = self.get_selection()

        # song popover
        self._song_popover = SongPopover(self._client)

        # connect
        self.connect("row-activated", self._on_row_activated)
        self.connect("button-press-event", self._on_button_press_event)

    def clear(self):
        self._song_popover.popdown()
        self._store.clear()

    def get_files(self):
        return_list = []
        for row in self._store:
            return_list.append(row[self._file_column_id])
        return return_list

    def _on_row_activated(self, widget, path, view_column):
        self._client.files_to_playlist([self._store[path][self._file_column_id]])

    def _on_button_press_event(self, widget, event):
        path_re = widget.get_path_at_pos(int(event.x), int(event.y))
        if path_re is not None:
            path = path_re[0]
            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self._client.files_to_playlist(
                    [self._store[path][self._file_column_id]], "play"
                )
            elif event.button == 2 and event.type == Gdk.EventType.BUTTON_PRESS:
                self._client.files_to_playlist(
                    [self._store[path][self._file_column_id]], "append"
                )
            elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                uri = self._store[path][self._file_column_id]
                point = self.convert_bin_window_to_widget_coords(event.x, event.y)
                self._song_popover.open(uri, widget, *point)

    def show_info(self):
        treeview, treeiter = self._selection.get_selected()
        if treeiter is not None:
            path = self._store.get_path(treeiter)
            self._song_popover.open(
                self._store[path][self._file_column_id],
                self,
                *self.get_popover_point(path)
            )

    def add_to_playlist(self, mode):
        treeview, treeiter = self._selection.get_selected()
        if treeiter is not None:
            self._client.files_to_playlist(
                [self._store.get_value(treeiter, self._file_column_id)], mode
            )


class SongsWindow(Gtk.Box):
    __gsignals__ = {"button-clicked": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, client, store, file_column_id, popover_mode=False):
        if popover_mode:
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, border_width=6, spacing=6
            )
        else:
            super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._client = client

        # treeview
        self._songs_view = SongsView(client, store, file_column_id)

        # scroll
        self._scroll = Gtk.ScrolledWindow(child=self._songs_view)

        # buttons
        button_box = Gtk.ButtonBox(layout_style=Gtk.ButtonBoxStyle.EXPAND)
        data = (
            (
                _("_Append"),
                _("Add all titles to playlist"),
                "list-add-symbolic",
                "append",
            ),
            (
                _("_Play"),
                _("Directly play all titles"),
                "media-playback-start-symbolic",
                "play",
            ),
            (
                _("_Enqueue"),
                _(
                    "Append all titles after the currently playing track and clear the playlist from all other songs"
                ),
                "insert-object-symbolic",
                "enqueue",
            ),
        )
        for label, tooltip, icon, mode in data:
            button = Gtk.Button.new_with_mnemonic(label)
            button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
            button.set_tooltip_text(tooltip)
            button.connect("clicked", self._on_button_clicked, mode)
            button_box.pack_start(button, True, True, 0)

        # action bar
        self._action_bar = Gtk.ActionBar()

        # packing
        if popover_mode:
            self.pack_end(button_box, False, False, 0)
            frame = Gtk.Frame(child=self._scroll)
            self.pack_start(frame, True, True, 0)
        else:
            self._action_bar.pack_start(button_box)
            self.pack_end(self._action_bar, False, False, 0)
            self.pack_start(self._scroll, True, True, 0)

    def get_treeview(self):
        return self._songs_view

    def get_action_bar(self):
        return self._action_bar

    def get_scroll(self):
        return self._scroll

    def _on_button_clicked(self, widget, mode):
        self._client.files_to_playlist(self._songs_view.get_files(), mode)
        self.emit("button-clicked")
