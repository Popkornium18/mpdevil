import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class TreeView(Gtk.TreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_popover_point(self, path):
        cell = self.get_cell_area(path, None)
        cell.x, cell.y = self.convert_bin_window_to_widget_coords(cell.x, cell.y)
        rect = self.get_visible_rect()
        rect.x, rect.y = self.convert_tree_to_widget_coords(rect.x, rect.y)
        return (
            rect.x + rect.width // 2,
            max(min(cell.y + cell.height // 2, rect.y + rect.height), rect.y),
        )
