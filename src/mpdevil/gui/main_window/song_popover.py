from gettext import gettext as _
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, Pango, GLib


class SongPopover(Gtk.Popover):
    def __init__(self, client, show_buttons=True):
        super().__init__()
        self._client = client
        self._rect = Gdk.Rectangle()
        self._uri = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, border_width=6, spacing=6)

        # open-with button
        open_button = Gtk.Button(
            image=Gtk.Image.new_from_icon_name(
                "document-open-symbolic", Gtk.IconSize.BUTTON
            ),
            tooltip_text=_("Open with…"),
        )
        open_button.get_style_context().add_class("osd")

        # open button revealer
        self._open_button_revealer = Gtk.Revealer(
            child=open_button,
            transition_duration=0,
            margin_bottom=6,
            margin_end=6,
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
        )

        # buttons
        if show_buttons:
            button_box = Gtk.ButtonBox(layout_style=Gtk.ButtonBoxStyle.EXPAND)
            data = (
                (_("Append"), "list-add-symbolic", "append"),
                (_("Play"), "media-playback-start-symbolic", "play"),
                (_("Enqueue"), "insert-object-symbolic", "enqueue"),
            )
            for label, icon, mode in data:
                button = Gtk.Button(
                    label=label,
                    image=Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON),
                )
                button.connect("clicked", self._on_button_clicked, mode)
                button_box.pack_start(button, True, True, 0)
            box.pack_end(button_box, False, False, 0)

        # treeview
        # (tag, display-value, tooltip)
        self._store = Gtk.ListStore(str, str, str)
        self._treeview = Gtk.TreeView(
            model=self._store,
            headers_visible=False,
            search_column=-1,
            tooltip_column=2,
            can_focus=False,
        )
        self._treeview.get_selection().set_mode(Gtk.SelectionMode.NONE)

        # columns
        renderer_text = Gtk.CellRendererText(
            width_chars=50, ellipsize=Pango.EllipsizeMode.MIDDLE, ellipsize_set=True
        )
        renderer_text_ralign = Gtk.CellRendererText(
            xalign=1.0, weight=Pango.Weight.BOLD
        )
        column_tag = Gtk.TreeViewColumn(_("MPD-Tag"), renderer_text_ralign, text=0)
        column_tag.set_property("resizable", False)
        self._treeview.append_column(column_tag)
        column_value = Gtk.TreeViewColumn(_("Value"), renderer_text, text=1)
        column_value.set_property("resizable", False)
        self._treeview.append_column(column_value)

        # scroll
        self._scroll = Gtk.ScrolledWindow(
            child=self._treeview, propagate_natural_height=True
        )
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # overlay
        overlay = Gtk.Overlay(child=self._scroll)
        overlay.add_overlay(self._open_button_revealer)

        # connect
        open_button.connect("clicked", self._on_open_button_clicked)

        # packing
        frame = Gtk.Frame(child=overlay)
        box.pack_start(frame, True, True, 0)
        self.add(box)
        box.show_all()

    def open(self, uri, widget, x, y):
        self._uri = uri
        self._rect.x, self._rect.y = x, y
        self.set_pointing_to(self._rect)
        self.set_relative_to(widget)
        window = self.get_toplevel()
        self._scroll.set_max_content_height(window.get_size()[1] // 2)
        self._store.clear()
        song = self._client.lsinfo(uri)[0]
        for tag, value in song.items():
            if tag == "duration":
                self._store.append([tag + ":", str(value), locale.str(value)])
            elif tag in ("last-modified", "format"):
                self._store.append([tag + ":", str(value), value.raw()])
            else:
                self._store.append(
                    [tag + ":", str(value), GLib.markup_escape_text(str(value))]
                )
        abs_path = self._client.get_absolute_path(uri)
        if abs_path is None:  # show open with button when song is on the same computer
            self._open_button_revealer.set_reveal_child(False)
        else:
            self._gfile = Gio.File.new_for_path(abs_path)
            self._open_button_revealer.set_reveal_child(True)
        self.popup()
        self._treeview.columns_autosize()

    def _on_open_button_clicked(self, *args):
        self.popdown()
        dialog = Gtk.AppChooserDialog(
            gfile=self._gfile, transient_for=self.get_toplevel()
        )
        app_chooser = dialog.get_widget()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            app = app_chooser.get_app_info()
            app.launch([self._gfile], None)
        dialog.destroy()

    def _on_button_clicked(self, widget, mode):
        self._client.files_to_playlist([self._uri], mode)
        self.popdown()
