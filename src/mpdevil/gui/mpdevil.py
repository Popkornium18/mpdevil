import os
import locale
from gettext import gettext as _, bindtextdomain, textdomain
import gi
from mpdevil.gui.main_window import MainWindow
from mpdevil.gui.mpda_action_group import MPDActionGroup
from mpdevil.mpd_client_wrapper import Client
from mpdevil.constants import LOCALE_DIR, RESOURCES_DIR

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import Gtk, GObject, Gio, Gdk, GLib, Notify

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error as e:
    print(e)
locale.bindtextdomain("mpdevil", LOCALE_DIR)
locale.textdomain("mpdevil")
bindtextdomain("mpdevil", localedir=LOCALE_DIR)
textdomain("mpdevil")
Gio.Resource._register(
    Gio.resource_load(os.path.join(RESOURCES_DIR, "mpdevil.gresource"))
)


class Settings(Gio.Settings):
    BASE_KEY = "org.mpdevil.mpdevil"
    # temp settings
    cursor_watch = GObject.Property(type=bool, default=False)

    def __init__(self):
        super().__init__(schema=self.BASE_KEY)
        self._profiles = (
            self.get_child("profile1"),
            self.get_child("profile2"),
            self.get_child("profile3"),
        )

    def array_append(self, vtype, key, value):  # append to Gio.Settings array
        array = self.get_value(key).unpack()
        array.append(value)
        self.set_value(key, GLib.Variant(vtype, array))

    def array_delete(self, vtype, key, pos):  # delete entry of Gio.Settings array
        array = self.get_value(key).unpack()
        array.pop(pos)
        self.set_value(key, GLib.Variant(vtype, array))

    def array_modify(
        self, vtype, key, pos, value
    ):  # modify entry of Gio.Settings array
        array = self.get_value(key).unpack()
        array[pos] = value
        self.set_value(key, GLib.Variant(vtype, array))

    def get_profile(self, num):
        return self._profiles[num]

    def get_active_profile(self):
        return self.get_profile(self.get_int("active-profile"))


class mpdevil(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.mpdevil.mpdevil",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.add_main_option(
            "debug",
            ord("d"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Debug mode"),
            None,
        )
        self._settings = Settings()
        self._client = Client(self._settings)
        Notify.init("mpdevil")
        self._notify = Notify.Notification()
        self._window = None

    def do_activate(self):
        if not self._window:  # allow just one instance
            self._window = MainWindow(
                self._client, self._settings, self._notify, application=self
            )
            self._window.connect("delete-event", self._on_quit)
            self._window.insert_action_group("mpd", MPDActionGroup(self._client))
            # accelerators
            action_accels = (
                ("app.quit", ["<Control>q"]),
                ("win.mini-player", ["<Control>m"]),
                ("win.help", ["F1"]),
                ("win.menu", ["F10"]),
                ("win.show-help-overlay", ["<Control>question"]),
                ("win.toggle-lyrics", ["<Control>l"]),
                ("win.back-to-current-album", ["Escape"]),
                ("win.toggle-search", ["<control>f"]),
                ("mpd.update", ["F5"]),
                ("mpd.clear", ["<Shift>Delete"]),
                ("mpd.toggle-play", ["space"]),
                ("mpd.stop", ["<Shift>space"]),
                ("mpd.next", ["KP_Add"]),
                ("mpd.prev", ["KP_Subtract"]),
                ("mpd.repeat", ["<Control>r"]),
                ("mpd.random", ["<Control>s"]),
                ("mpd.single", ["<Control>1"]),
                ("mpd.consume", ["<Control>o"]),
                ("mpd.single-oneshot", ["<Control>space"]),
                ("mpd.seek-forward", ["KP_Multiply"]),
                ("mpd.seek-backward", ["KP_Divide"]),
                ("win.profile-next", ["<Control>p"]),
                ("win.profile-prev", ["<Shift><Control>p"]),
                ("win.show-info", ["<Control>i", "Menu"]),
                ("win.append", ["<Control>plus"]),
                ("win.play", ["<Control>Return"]),
                ("win.enqueue", ["<Control>e"]),
                ("win.genre-filter", ["<Control>g"]),
            )
            for action, accels in action_accels:
                self.set_accels_for_action(action, accels)
            # disable item activation on space key pressed in treeviews
            Gtk.binding_entry_remove(
                Gtk.binding_set_find("GtkTreeView"),
                Gdk.keyval_from_name("space"),
                Gdk.ModifierType.MOD2_MASK,
            )
        self._window.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self._on_about)
        self.add_action(action)
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self._on_quit)
        self.add_action(action)

    def do_command_line(self, command_line):
        # convert GVariantDict -> GVariant -> dict
        options = command_line.get_options_dict().end().unpack()
        if "debug" in options:
            import logging

            logging.basicConfig(level=logging.DEBUG)
        self.activate()
        return 0

    def _on_about(self, *args):
        builder = Gtk.Builder()
        builder.add_from_resource("/org/mpdevil/mpdevil/AboutDialog.ui")
        dialog = builder.get_object("about_dialog")
        dialog.set_transient_for(self._window)
        dialog.run()
        dialog.destroy()

    def _on_quit(self, *args):
        if self._settings.get_boolean("stop-on-quit") and self._client.connected():
            self._client.stop()
        self._notify.close()
        Notify.uninit()
        self.quit()
