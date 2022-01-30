import gi
from mpdevil.gui.main_window.settings_dialog import settings_tabs

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, client, settings, tab="view"):
        use_csd = settings.get_boolean("use-csd")
        if use_csd:
            super().__init__(
                title=_("Preferences"), transient_for=parent, use_header_bar=True
            )
        else:
            super().__init__(title=_("Preferences"), transient_for=parent)
            self.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_size(500, 400)

        # widgets
        view = settings_tabs.ViewSettings(settings)
        behavior = settings_tabs.BehaviorSettings(settings)
        profiles = settings_tabs.ProfileSettings(parent, client, settings)
        playlist = settings_tabs.PlaylistSettings(settings)

        # packing
        vbox = self.get_content_area()
        if use_csd:
            stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
            stack.add_titled(view, "view", _("View"))
            stack.add_titled(behavior, "behavior", _("Behavior"))
            stack.add_titled(playlist, "playlist", _("Playlist"))
            stack.add_titled(profiles, "profiles", _("Profiles"))
            stack_switcher = Gtk.StackSwitcher(stack=stack)
            vbox.set_property("border-width", 0)
            vbox.pack_start(stack, True, True, 0)
            header_bar = self.get_header_bar()
            header_bar.set_custom_title(stack_switcher)
        else:
            tabs = Gtk.Notebook()
            tabs.append_page(view, Gtk.Label(label=_("View")))
            tabs.append_page(behavior, Gtk.Label(label=_("Behavior")))
            tabs.append_page(playlist, Gtk.Label(label=_("Playlist")))
            tabs.append_page(profiles, Gtk.Label(label=_("Profiles")))
            vbox.set_property("spacing", 6)
            vbox.set_property("border-width", 6)
            vbox.pack_start(tabs, True, True, 0)
        self.show_all()
        if use_csd:
            stack.set_visible_child_name(tab)
        else:
            tabs.set_current_page(
                {"view": 0, "behavior": 1, "playlist": 2, "profiles": 3}[tab]
            )
