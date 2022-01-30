from gettext import gettext as _
import gi
from mpdevil.mpris_interface import MPRISInterface
from mpdevil.gui.main_window.audio_format import AudioFormat
from mpdevil.gui.main_window.auto_sized_icon import AutoSizedIcon
from mpdevil.gui.main_window.browser import Browser
from mpdevil.gui.main_window.cover_lyrics_window import CoverLyricsWindow
from mpdevil.gui.main_window.playback_control import PlaybackControl
from mpdevil.gui.main_window.playback_options import PlaybackOptions
from mpdevil.gui.main_window.playlist_window import PlaylistWindow
from mpdevil.gui.main_window.search_window import SearchWindow
from mpdevil.gui.main_window.seek_bar import SeekBar
from mpdevil.gui.main_window.volume_button import VolumeButton
from mpdevil.gui.main_window.update_notify import UpdateNotify
from mpdevil.gui.main_window.connection_notify import ConnectionNotify
from mpdevil.gui.main_window.settings_dialog import SettingsDialog

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, GLib


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, client, settings, notify, **kwargs):
        super().__init__(title=("mpdevil"), icon_name="org.mpdevil.mpdevil", **kwargs)
        self.set_default_icon_name("org.mpdevil.mpdevil")
        self.set_default_size(settings.get_int("width"), settings.get_int("height"))
        if settings.get_boolean("maximize"):
            self.maximize()  # request maximize
        self._client = client
        self._settings = settings
        self._notify = notify
        self._use_csd = self._settings.get_boolean("use-csd")
        self._size = None  # needed for window size saving

        # MPRIS
        if self._settings.get_boolean("mpris"):
            dbus_service = MPRISInterface(self, self._client, self._settings)

        # actions
        simple_actions_data = (
            "settings",
            "profile-settings",
            "stats",
            "help",
            "menu",
            "toggle-lyrics",
            "back-to-current-album",
            "toggle-search",
            "profile-next",
            "profile-prev",
            "show-info",
        )
        for name in simple_actions_data:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", getattr(self, ("_on_" + name.replace("-", "_"))))
            self.add_action(action)
        for name in ("append", "play", "enqueue"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._on_add_to_playlist, name)
            self.add_action(action)
        self.add_action(self._settings.create_action("mini-player"))
        self.add_action(self._settings.create_action("genre-filter"))
        self.add_action(self._settings.create_action("active-profile"))

        # shortcuts
        builder = Gtk.Builder()
        builder.add_from_resource("/org/mpdevil/mpdevil/ShortcutsWindow.ui")
        self.set_help_overlay(builder.get_object("shortcuts_window"))

        # widgets
        self._paned0 = Gtk.Paned()
        self._paned2 = Gtk.Paned()
        self._browser = Browser(self._client, self._settings)
        self._search_window = SearchWindow(self._client)
        self._cover_lyrics_window = CoverLyricsWindow(self._client, self._settings)
        playlist_window = PlaylistWindow(self._client, self._settings)
        playback_control = PlaybackControl(self._client, self._settings)
        seek_bar = SeekBar(self._client)
        audio = AudioFormat(self._client, self._settings)
        playback_options = PlaybackOptions(self._client, self._settings)
        volume_button = VolumeButton(self._client, self._settings)
        update_notify = UpdateNotify(self._client)
        connection_notify = ConnectionNotify(self._client, self._settings)

        def icon(name):
            if self._use_csd:
                return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.BUTTON)
            else:
                return AutoSizedIcon(name, "icon-size", self._settings)

        self._search_button = Gtk.ToggleButton(
            image=icon("system-search-symbolic"),
            tooltip_text=_("Search"),
            can_focus=False,
            no_show_all=True,
        )
        self._settings.bind(
            "mini-player",
            self._search_button,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )
        self._back_button = Gtk.Button(
            image=icon("go-previous-symbolic"),
            tooltip_text=_("Back to current album"),
            can_focus=False,
            no_show_all=True,
        )
        self._settings.bind(
            "mini-player",
            self._back_button,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )

        # stack
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self._stack.add_named(self._browser, "browser")
        self._stack.add_named(self._search_window, "search")
        self._settings.bind(
            "mini-player", self._stack, "no-show-all", Gio.SettingsBindFlags.GET
        )
        self._settings.bind(
            "mini-player",
            self._stack,
            "visible",
            Gio.SettingsBindFlags.INVERT_BOOLEAN | Gio.SettingsBindFlags.GET,
        )

        # menu
        subsection = Gio.Menu()
        subsection.append(_("Preferences"), "win.settings")
        subsection.append(_("Keyboard Shortcuts"), "win.show-help-overlay")
        subsection.append(_("Help"), "win.help")
        subsection.append(_("About mpdevil"), "app.about")
        mpd_subsection = Gio.Menu()
        mpd_subsection.append(_("Update Database"), "mpd.update")
        mpd_subsection.append(_("Server Stats"), "win.stats")
        profiles_subsection = Gio.Menu()
        for num, profile in enumerate((_("Profile 1"), _("Profile 2"), _("Profile 3"))):
            item = Gio.MenuItem.new(profile, None)
            item.set_action_and_target_value(
                "win.active-profile", GLib.Variant("i", num)
            )
            profiles_subsection.append_item(item)
        menu = Gio.Menu()
        menu.append(_("Mini Player"), "win.mini-player")
        menu.append(_("Genre Filter"), "win.genre-filter")
        menu.append_section(None, profiles_subsection)
        menu.append_section(None, mpd_subsection)
        menu.append_section(None, subsection)

        # menu button / popover
        if self._use_csd:
            menu_icon = Gtk.Image.new_from_icon_name(
                "open-menu-symbolic", Gtk.IconSize.BUTTON
            )
        else:
            menu_icon = AutoSizedIcon("open-menu-symbolic", "icon-size", self._settings)
        self._menu_button = Gtk.MenuButton(
            image=menu_icon, tooltip_text=_("Menu"), can_focus=False
        )
        menu_popover = Gtk.Popover.new_from_model(self._menu_button, menu)
        self._menu_button.set_popover(menu_popover)

        # connect
        self._search_button.connect("toggled", self._on_search_button_toggled)
        self._back_button.connect("clicked", self._on_back_button_clicked)
        self._back_button.connect(
            "button-press-event", self._on_back_button_press_event
        )
        self._search_window.connect(
            "close", lambda *args: self._search_button.set_active(False)
        )
        self._settings.connect_after("changed::mini-player", self._mini_player)
        self._settings.connect_after("notify::cursor-watch", self._on_cursor_watch)
        self._settings.connect("changed::playlist-right", self._on_playlist_pos_changed)
        self._client.emitter.connect("current_song", self._on_song_changed)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)
        # auto save window state and size
        self.connect("size-allocate", self._on_size_allocate)
        self._settings.bind("maximize", self, "is-maximized", Gio.SettingsBindFlags.SET)

        # packing
        self._on_playlist_pos_changed()  # set orientation
        self._paned0.pack1(self._cover_lyrics_window, False, False)
        self._paned0.pack2(playlist_window, True, False)
        self._paned2.pack1(self._stack, True, False)
        self._paned2.pack2(self._paned0, False, False)
        action_bar = Gtk.ActionBar()
        if self._use_csd:
            self._header_bar = Gtk.HeaderBar(show_close_button=True)
            self.set_titlebar(self._header_bar)
            self._header_bar.pack_start(self._back_button)
            self._header_bar.pack_end(self._menu_button)
            self._header_bar.pack_end(self._search_button)
        else:
            action_bar.pack_start(self._back_button)
            action_bar.pack_end(self._menu_button)
            action_bar.pack_end(self._search_button)
        action_bar.pack_start(playback_control)
        action_bar.pack_start(seek_bar)
        action_bar.pack_start(audio)
        action_bar.pack_start(playback_options)
        action_bar.pack_start(volume_button)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(self._paned2, True, True, 0)
        vbox.pack_start(action_bar, False, False, 0)
        overlay = Gtk.Overlay(child=vbox)
        overlay.add_overlay(update_notify)
        overlay.add_overlay(connection_notify)
        self.add(overlay)
        # bring player in consistent state
        self._client.emitter.emit("disconnected")
        self._mini_player()
        # indicate connection process in window title
        if self._use_csd:
            self._header_bar.set_subtitle(_("connecting…"))
        else:
            self.set_title("mpdevil " + _("connecting…"))
        self.show_all()
        while Gtk.events_pending():  # ensure window is visible
            Gtk.main_iteration_do(True)
        # restore paned settings when window is visible (fixes a bug when window is maximized)
        self._settings.bind(
            "paned0", self._paned0, "position", Gio.SettingsBindFlags.DEFAULT
        )
        self._settings.bind(
            "paned1", self._browser.paned1, "position", Gio.SettingsBindFlags.DEFAULT
        )
        self._settings.bind(
            "paned2", self._paned2, "position", Gio.SettingsBindFlags.DEFAULT
        )
        self._settings.bind(
            "paned3", self._browser, "position", Gio.SettingsBindFlags.DEFAULT
        )

        # start client
        def callback(*args):
            self._client.start()  # connect client
            return False

        GLib.idle_add(callback)

    def _mini_player(self, *args):
        if self._settings.get_boolean("mini-player"):
            if self.is_maximized():
                self.unmaximize()
            self.resize(1, 1)
        else:
            self.resize(
                self._settings.get_int("width"), self._settings.get_int("height")
            )
            self.show_all()

    def _on_toggle_lyrics(self, action, param):
        self._cover_lyrics_window.lyrics_button.emit("clicked")

    def _on_back_to_current_album(self, action, param):
        self._back_button.emit("clicked")

    def _on_toggle_search(self, action, param):
        self._search_button.emit("clicked")

    def _on_settings(self, action, param):
        settings = SettingsDialog(self, self._client, self._settings)
        settings.run()
        settings.destroy()

    def _on_profile_settings(self, action, param):
        settings = SettingsDialog(self, self._client, self._settings, "profiles")
        settings.run()
        settings.destroy()

    def _on_stats(self, action, param):
        stats = ServerStats(self, self._client, self._settings)
        stats.destroy()

    def _on_help(self, action, param):
        Gtk.show_uri_on_window(
            self, "https://github.com/SoongNoonien/mpdevil/wiki/Usage", Gdk.CURRENT_TIME
        )

    def _on_menu(self, action, param):
        self._menu_button.emit("clicked")

    def _on_profile_next(self, action, param):
        current_profile = self._settings.get_int("active-profile")
        self._settings.set_int("active-profile", ((current_profile + 1) % 3))

    def _on_profile_prev(self, action, param):
        current_profile = self._settings.get_int("active-profile")
        self._settings.set_int("active-profile", ((current_profile - 1) % 3))

    def _on_show_info(self, action, param):
        widget = self.get_focus()
        if hasattr(widget, "show_info") and callable(widget.show_info):
            widget.show_info()

    def _on_add_to_playlist(self, action, param, mode):
        widget = self.get_focus()
        if hasattr(widget, "add_to_playlist") and callable(widget.add_to_playlist):
            widget.add_to_playlist(mode)

    def _on_search_button_toggled(self, button):
        if button.get_active():
            self._stack.set_visible_child_name("search")
            self._search_window.search_entry.grab_focus()
        else:
            self._stack.set_visible_child_name("browser")

    def _on_back_button_clicked(self, *args):
        self._search_button.set_active(False)
        self._browser.back_to_current_album()

    def _on_back_button_press_event(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self._browser.back_to_current_album(force=True)

    def _on_song_changed(self, *args):
        song = self._client.currentsong()
        if song:
            if "date" in song:
                date = f"({song['date']})"
            else:
                date = ""
            album_with_date = " ".join(filter(None, (str(song["album"]), date)))
            if self._use_csd:
                self.set_title(
                    " • ".join(filter(None, (str(song["title"]), str(song["artist"]))))
                )
                self._header_bar.set_subtitle(album_with_date)
            else:
                self.set_title(
                    " • ".join(
                        filter(
                            None,
                            (str(song["title"]), str(song["artist"]), album_with_date),
                        )
                    )
                )
            if self._settings.get_boolean("send-notify"):
                if not self.is_active() and self._client.status()["state"] == "play":
                    self._notify.update(
                        str(song["title"]), f"{song['artist']}\n{album_with_date}"
                    )
                    pixbuf = self._client.get_cover(song).get_pixbuf(400)
                    self._notify.set_image_from_pixbuf(pixbuf)
                    self._notify.show()
        else:
            self.set_title("mpdevil")
            if self._use_csd:
                self._header_bar.set_subtitle("")

    def _on_reconnected(self, *args):
        for action in (
            "stats",
            "toggle-lyrics",
            "back-to-current-album",
            "toggle-search",
        ):
            self.lookup_action(action).set_enabled(True)
        self._search_button.set_sensitive(True)
        self._back_button.set_sensitive(True)

    def _on_disconnected(self, *args):
        self.set_title("mpdevil")
        if self._use_csd:
            self._header_bar.set_subtitle("")
        for action in (
            "stats",
            "toggle-lyrics",
            "back-to-current-album",
            "toggle-search",
        ):
            self.lookup_action(action).set_enabled(False)
        self._search_button.set_active(False)
        self._search_button.set_sensitive(False)
        self._back_button.set_sensitive(False)

    def _on_size_allocate(self, widget, rect):
        if not self.is_maximized() and not self._settings.get_boolean("mini-player"):
            size = self.get_size()
            if size != self._size:  # prevent unneeded write operations
                self._settings.set_int("width", size[0])
                self._settings.set_int("height", size[1])
                self._size = size

    def _on_cursor_watch(self, obj, typestring):
        if obj.get_property("cursor-watch"):
            watch_cursor = Gdk.Cursor(Gdk.CursorType.WATCH)
            self.get_window().set_cursor(watch_cursor)
        else:
            self.get_window().set_cursor(None)

    def _on_playlist_pos_changed(self, *args):
        if self._settings.get_boolean("playlist-right"):
            self._paned0.set_orientation(Gtk.Orientation.VERTICAL)
            self._paned2.set_orientation(Gtk.Orientation.HORIZONTAL)
        else:
            self._paned0.set_orientation(Gtk.Orientation.HORIZONTAL)
            self._paned2.set_orientation(Gtk.Orientation.VERTICAL)
