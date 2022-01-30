import locale
import gi
from mpdevil.gui.main_window.tree_view import TreeView

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GObject


class SelectionList(TreeView):
    __gsignals__ = {
        "item-selected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "clear": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, select_all_string):
        super().__init__(
            activate_on_single_click=True,
            search_column=0,
            headers_visible=False,
            fixed_height_mode=True,
        )
        self.select_all_string = select_all_string
        self._selected_path = None

        # store
        # (item, weight, initial-letter, weight-initials, sort-string)
        self._store = Gtk.ListStore(str, Pango.Weight, str, Pango.Weight, str)
        self._store.append(
            [self.select_all_string, Pango.Weight.BOOK, "", Pango.Weight.BOOK, ""]
        )
        self.set_model(self._store)
        self._selection = self.get_selection()

        # columns
        renderer_text_malign = Gtk.CellRendererText(xalign=0.5)
        self._column_initial = Gtk.TreeViewColumn(
            "", renderer_text_malign, text=2, weight=3
        )
        self._column_initial.set_property("sizing", Gtk.TreeViewColumnSizing.FIXED)
        self._column_initial.set_property("min-width", 30)
        self.append_column(self._column_initial)
        renderer_text = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True
        )
        self._column_item = Gtk.TreeViewColumn("", renderer_text, text=0, weight=1)
        self._column_item.set_property("sizing", Gtk.TreeViewColumnSizing.FIXED)
        self._column_item.set_property("expand", True)
        self.append_column(self._column_item)

        # connect
        self.connect("row-activated", self._on_row_activated)

    def clear(self):
        self._store.clear()
        self._store.append(
            [self.select_all_string, Pango.Weight.BOOK, "", Pango.Weight.BOOK, ""]
        )
        self._selected_path = None
        self.emit("clear")

    def set_items(self, items):
        self.clear()
        current_char = ""
        items.sort(key=lambda item: locale.strxfrm(item[1]))
        items.sort(key=lambda item: locale.strxfrm(item[1][:1]))
        for item in items:
            if current_char == item[1][:1].upper():
                self._store.insert_with_valuesv(
                    -1,
                    range(5),
                    [item[0], Pango.Weight.BOOK, "", Pango.Weight.BOOK, item[1]],
                )
            else:
                self._store.insert_with_valuesv(
                    -1,
                    range(5),
                    [
                        item[0],
                        Pango.Weight.BOOK,
                        item[1][:1].upper(),
                        Pango.Weight.BOLD,
                        item[1],
                    ],
                )
                current_char = item[1][:1].upper()

    def get_item_at_path(self, path):
        if path == Gtk.TreePath(0):
            return None
        else:
            return self._store[path][0, 4]

    def length(self):
        return len(self._store) - 1

    def select_path(self, path):
        self.set_cursor(path, None, False)
        self.row_activated(path, self._column_item)

    def select(self, item):
        row_num = len(self._store)
        for i in range(0, row_num):
            path = Gtk.TreePath(i)
            if self._store[path][0] == item[0] and self._store[path][4] == item[1]:
                self.select_path(path)
                break

    def select_all(self):
        self.set_cursor(Gtk.TreePath(0), None, False)
        self.row_activated(Gtk.TreePath(0), self._column_item)

    def get_path_selected(self):
        if self._selected_path is None:
            raise ValueError("None selected")
        else:
            return self._selected_path

    def get_item_selected(self):
        return self.get_item_at_path(self.get_path_selected())

    def highlight_selected(self):
        self.set_cursor(self._selected_path, None, False)

    def _on_row_activated(self, widget, path, view_column):
        if path != self._selected_path:
            if self._selected_path is not None:
                self._store[self._selected_path][1] = Pango.Weight.BOOK
            self._store[path][1] = Pango.Weight.BOLD
            self._selected_path = path
            self.emit("item-selected")
