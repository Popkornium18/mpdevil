import gi
from mpdevil.gui.main_window.settings_dialog.util import (
    IntRow,
    ProfileEntryMask,
    ToggleRow,
)

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class SettingsList(Gtk.Frame):
    def __init__(self):
        super().__init__(border_width=18, valign=Gtk.Align.START)
        self._list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list_box.set_header_func(self._header_func)
        self._list_box.connect("row-activated", self._on_row_activated)
        self.add(self._list_box)

    def append(self, row):
        self._list_box.insert(row, -1)

    def _header_func(self, row, before, *args):
        if before is not None:
            row.set_header(Gtk.Separator())

    def _on_row_activated(self, list_box, row):
        if isinstance(row, ToggleRow):
            row.toggle()


class PlaylistSettings(Gtk.Box):
    def __init__(self, settings):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=18
        )
        self._settings = settings

        # label
        label = Gtk.Label(
            label=_("Choose the order of information to appear in the playlist:"),
            wrap=True,
            xalign=0,
        )

        # treeview
        # (toggle, header, actual_index)
        self._store = Gtk.ListStore(bool, str, int)
        treeview = Gtk.TreeView(
            model=self._store, reorderable=True, headers_visible=False, search_column=-1
        )
        self._selection = treeview.get_selection()

        # columns
        renderer_text = Gtk.CellRendererText()
        renderer_toggle = Gtk.CellRendererToggle()
        column_toggle = Gtk.TreeViewColumn("", renderer_toggle, active=0)
        treeview.append_column(column_toggle)
        column_text = Gtk.TreeViewColumn("", renderer_text, text=1)
        treeview.append_column(column_text)

        # fill store
        self._headers = [
            _("No"),
            _("Disc"),
            _("Title"),
            _("Artist"),
            _("Album"),
            _("Length"),
            _("Year"),
            _("Genre"),
        ]
        self._fill()

        # scroll
        scroll = Gtk.ScrolledWindow(child=treeview)

        # toolbar
        toolbar = Gtk.Toolbar(icon_size=Gtk.IconSize.SMALL_TOOLBAR)
        toolbar.get_style_context().add_class("inline-toolbar")
        self._up_button = Gtk.ToolButton(icon_name="go-up-symbolic", sensitive=False)
        self._down_button = Gtk.ToolButton(
            icon_name="go-down-symbolic", sensitive=False
        )
        toolbar.insert(self._up_button, 0)
        toolbar.insert(self._down_button, 1)

        # column chooser
        frame = Gtk.Frame(child=scroll)
        column_chooser = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        column_chooser.pack_start(frame, True, True, 0)
        column_chooser.pack_start(toolbar, False, False, 0)

        # connect
        self._row_deleted = self._store.connect("row-deleted", self._save_permutation)
        renderer_toggle.connect("toggled", self._on_cell_toggled)
        self._up_button.connect("clicked", self._on_up_button_clicked)
        self._down_button.connect("clicked", self._on_down_button_clicked)
        self._selection.connect("changed", self._set_button_sensitivity)

        # packing
        self.pack_start(label, False, False, 0)
        self.pack_start(column_chooser, True, True, 0)

    def _fill(self, *args):
        visibilities = self._settings.get_value("column-visibilities").unpack()
        for actual_index in self._settings.get_value("column-permutation"):
            self._store.append(
                [visibilities[actual_index], self._headers[actual_index], actual_index]
            )

    def _save_permutation(self, *args):
        permutation = []
        for row in self._store:
            permutation.append(row[2])
        self._settings.set_value("column-permutation", GLib.Variant("ai", permutation))

    def _set_button_sensitivity(self, *args):
        treeiter = self._selection.get_selected()[1]
        if treeiter is None:
            self._up_button.set_sensitive(False)
            self._down_button.set_sensitive(False)
        else:
            path = self._store.get_path(treeiter)
            if self._store.iter_next(treeiter) is None:
                self._up_button.set_sensitive(True)
                self._down_button.set_sensitive(False)
            elif not path.prev():
                self._up_button.set_sensitive(False)
                self._down_button.set_sensitive(True)
            else:
                self._up_button.set_sensitive(True)
                self._down_button.set_sensitive(True)

    def _on_cell_toggled(self, widget, path):
        self._store[path][0] = not self._store[path][0]
        self._settings.array_modify(
            "ab", "column-visibilities", self._store[path][2], self._store[path][0]
        )

    def _on_up_button_clicked(self, *args):
        treeiter = self._selection.get_selected()[1]
        path = self._store.get_path(treeiter)
        path.prev()
        prev = self._store.get_iter(path)
        self._store.move_before(treeiter, prev)
        self._set_button_sensitivity()
        self._save_permutation()

    def _on_down_button_clicked(self, *args):
        treeiter = self._selection.get_selected()[1]
        path = self._store.get_path(treeiter)
        next = self._store.iter_next(treeiter)
        self._store.move_after(treeiter, next)
        self._set_button_sensitivity()
        self._save_permutation()


class BehaviorSettings(SettingsList):
    def __init__(self, settings):
        super().__init__()
        toggle_data = [
            (_("Support “MPRIS”"), "mpris", True),
            (_("Sort albums by year"), "sort-albums-by-year", False),
            (_("Send notification on title change"), "send-notify", False),
            (_("Play selected albums and titles immediately"), "force-mode", False),
            (_("Rewind via previous button"), "rewind-mode", False),
            (_("Stop playback on quit"), "stop-on-quit", False),
        ]
        for label, key, restart_required in toggle_data:
            row = ToggleRow(label, settings, key, restart_required)
            self.append(row)


class ProfileSettings(Gtk.Box):
    def __init__(self, parent, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings

        # stack
        self._stack = Gtk.Stack()
        self._stack.add_titled(
            ProfileEntryMask(settings.get_profile(0), parent), "0", _("Profile 1")
        )
        self._stack.add_titled(
            ProfileEntryMask(settings.get_profile(1), parent), "1", _("Profile 2")
        )
        self._stack.add_titled(
            ProfileEntryMask(settings.get_profile(2), parent), "2", _("Profile 3")
        )
        self._stack.connect(
            "show",
            lambda *args: self._stack.set_visible_child_name(
                str(self._settings.get_int("active-profile"))
            ),
        )

        # connect button
        connect_button = Gtk.Button(
            label=_("Connect"),
            margin_start=18,
            margin_end=18,
            margin_bottom=18,
            halign=Gtk.Align.CENTER,
        )
        connect_button.get_style_context().add_class("suggested-action")
        connect_button.connect("clicked", self._on_connect_button_clicked)

        # packing
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(self._stack, False, False, 0)
        vbox.pack_start(connect_button, False, False, 0)
        switcher = Gtk.StackSidebar(stack=self._stack)
        self.pack_start(switcher, False, False, 0)
        self.pack_start(vbox, True, True, 0)

    def _on_connect_button_clicked(self, *args):
        selected = int(self._stack.get_visible_child_name())
        if selected == self._settings.get_int("active-profile"):
            self._client.reconnect()
        else:
            self._settings.set_int("active-profile", selected)


class ViewSettings(SettingsList):
    def __init__(self, settings):
        super().__init__()
        toggle_data = [
            (_("Use Client-side decoration"), "use-csd", True),
            (_("Show stop button"), "show-stop", False),
            (_("Show audio format"), "show-audio-format", False),
            (_("Show lyrics button"), "show-lyrics-button", False),
            (_("Place playlist at the side"), "playlist-right", False),
        ]
        for label, key, restart_required in toggle_data:
            row = ToggleRow(label, settings, key, restart_required)
            self.append(row)
        int_data = [
            (_("Main cover size"), (100, 1200, 10), "track-cover"),
            (_("Album view cover size"), (50, 600, 10), "album-cover"),
            (_("Action bar icon size"), (16, 64, 2), "icon-size"),
        ]
        for label, (vmin, vmax, step), key in int_data:
            row = IntRow(label, vmin, vmax, step, settings, key)
            self.append(row)
