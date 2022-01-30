import gi
from mpdevil.constants import FALLBACK_SOCKET, FALLBACK_LIB

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio


class LibPathEntry(Gtk.Entry):
    def __init__(self, parent, **kwargs):
        super().__init__(placeholder_text=FALLBACK_LIB, **kwargs)
        self.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, "folder-open-symbolic"
        )
        self.connect("icon-release", self._on_icon_release, parent)

    def _on_icon_release(self, widget, icon_pos, event, parent):
        dialog = Gtk.FileChooserNative(
            title=_("Choose directory"),
            transient_for=parent,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        folder = self.get_text()
        if not folder:
            folder = self.get_placeholder_text()
        dialog.set_current_folder(folder)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            self.set_text(dialog.get_filename())
        dialog.destroy()


class PasswordEntry(Gtk.Entry):
    def __init__(self, **kwargs):
        super().__init__(
            visibility=False,
            caps_lock_warning=False,
            input_purpose=Gtk.InputPurpose.PASSWORD,
            **kwargs
        )
        self.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic"
        )
        self.connect("icon-release", self._on_icon_release)

    def _on_icon_release(self, *args):
        if (
            self.get_icon_name(Gtk.EntryIconPosition.SECONDARY)
            == "view-conceal-symbolic"
        ):
            self.set_visibility(True)
            self.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic"
            )
        else:
            self.set_visibility(False)
            self.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic"
            )


class ProfileEntryMask(Gtk.Grid):
    def __init__(self, profile, parent):
        super().__init__(row_spacing=6, column_spacing=6, border_width=18)
        socket_button = Gtk.CheckButton(label=_("Connect via Unix domain socket"))
        profile.bind(
            "socket-connection", socket_button, "active", Gio.SettingsBindFlags.DEFAULT
        )
        socket_entry = Gtk.Entry(
            placeholder_text=FALLBACK_SOCKET, hexpand=True, no_show_all=True
        )
        profile.bind("socket", socket_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        profile.bind(
            "socket-connection", socket_entry, "visible", Gio.SettingsBindFlags.GET
        )
        host_entry = Gtk.Entry(hexpand=True, no_show_all=True)
        profile.bind("host", host_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        profile.bind(
            "socket-connection",
            host_entry,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        port_entry = Gtk.SpinButton.new_with_range(0, 65535, 1)
        port_entry.set_property("no-show-all", True)
        profile.bind("port", port_entry, "value", Gio.SettingsBindFlags.DEFAULT)
        profile.bind(
            "socket-connection",
            port_entry,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        password_entry = PasswordEntry(hexpand=True)
        profile.bind("password", password_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        path_entry = LibPathEntry(parent, hexpand=True, no_show_all=True)
        profile.bind("path", path_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        profile.bind(
            "socket-connection",
            path_entry,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        regex_entry = Gtk.Entry(hexpand=True, placeholder_text=COVER_REGEX)
        regex_entry.set_tooltip_text(
            _(
                "The first image in the same directory as the song file "
                "matching this regex will be displayed. %AlbumArtist% and "
                "%Album% will be replaced by the corresponding tags of the song."
            )
        )
        profile.bind("regex", regex_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        socket_label = Gtk.Label(
            label=_("Socket:"), xalign=1, margin_end=6, no_show_all=True
        )
        profile.bind(
            "socket-connection", socket_label, "visible", Gio.SettingsBindFlags.GET
        )
        host_label = Gtk.Label(
            label=_("Host:"), xalign=1, margin_end=6, no_show_all=True
        )
        profile.bind(
            "socket-connection",
            host_label,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        password_label = Gtk.Label(label=_("Password:"), xalign=1, margin_end=6)
        path_label = Gtk.Label(label=_("Music lib:"), xalign=1, no_show_all=True)
        profile.bind(
            "socket-connection",
            path_label,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        regex_label = Gtk.Label(label=_("Cover regex:"), xalign=1, margin_end=6)

        # packing
        self.attach(socket_button, 0, 0, 3, 1)
        self.attach(socket_label, 0, 1, 1, 1)
        self.attach_next_to(host_label, socket_label, Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(password_label, host_label, Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(path_label, password_label, Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(regex_label, path_label, Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(socket_entry, socket_label, Gtk.PositionType.RIGHT, 2, 1)
        self.attach_next_to(host_entry, host_label, Gtk.PositionType.RIGHT, 1, 1)
        self.attach_next_to(port_entry, host_entry, Gtk.PositionType.RIGHT, 1, 1)
        self.attach_next_to(
            password_entry, password_label, Gtk.PositionType.RIGHT, 2, 1
        )
        self.attach_next_to(path_entry, path_label, Gtk.PositionType.RIGHT, 2, 1)
        self.attach_next_to(regex_entry, regex_label, Gtk.PositionType.RIGHT, 2, 1)


class IntRow(Gtk.ListBoxRow):
    def __init__(self, label, vmin, vmax, step, settings, key):
        super().__init__(activatable=False)
        label = Gtk.Label(label=label, xalign=0, valign=Gtk.Align.CENTER, margin=6)
        spin_button = Gtk.SpinButton.new_with_range(vmin, vmax, step)
        spin_button.set_valign(Gtk.Align.CENTER)
        spin_button.set_halign(Gtk.Align.END)
        spin_button.set_margin_end(12)
        spin_button.set_margin_start(12)
        spin_button.set_margin_top(6)
        spin_button.set_margin_bottom(6)
        settings.bind(key, spin_button, "value", Gio.SettingsBindFlags.DEFAULT)
        box = Gtk.Box()
        box.pack_start(label, False, False, 0)
        box.pack_end(spin_button, False, False, 0)
        self.add(box)


class ToggleRow(Gtk.ListBoxRow):
    def __init__(self, label, settings, key, restart_required=False):
        super().__init__()
        label = Gtk.Label(label=label, xalign=0, valign=Gtk.Align.CENTER, margin=6)
        self._switch = Gtk.Switch(
            halign=Gtk.Align.END,
            valign=Gtk.Align.CENTER,
            margin_top=6,
            margin_bottom=6,
            margin_start=12,
            margin_end=12,
        )
        settings.bind(key, self._switch, "active", Gio.SettingsBindFlags.DEFAULT)
        box = Gtk.Box()
        box.pack_start(label, False, False, 0)
        box.pack_end(self._switch, False, False, 0)
        if restart_required:
            box.pack_end(
                Gtk.Label(label=_("(restart required)"), margin=6, sensitive=False),
                False,
                False,
                0,
            )
        self.add(box)

    def toggle(self):
        self._switch.set_active(not self._switch.get_active())
