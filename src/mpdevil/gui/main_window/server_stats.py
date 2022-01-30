import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class ServerStats(Gtk.Dialog):
    def __init__(self, parent, client, settings):
        use_csd = settings.get_boolean("use-csd")
        super().__init__(
            title=_("Stats"),
            transient_for=parent,
            use_header_bar=use_csd,
            resizable=False,
        )
        if not use_csd:
            self.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        # grid
        grid = Gtk.Grid(row_spacing=6, column_spacing=12, border_width=6)

        # populate
        display_str = {
            "protocol": _("<b>Protocol:</b>"),
            "uptime": _("<b>Uptime:</b>"),
            "playtime": _("<b>Playtime:</b>"),
            "artists": _("<b>Artists:</b>"),
            "albums": _("<b>Albums:</b>"),
            "songs": _("<b>Songs:</b>"),
            "db_playtime": _("<b>Total Playtime:</b>"),
            "db_update": _("<b>Database Update:</b>"),
        }
        stats = client.stats()
        stats["protocol"] = str(client.mpd_version)
        for key in ("uptime", "playtime", "db_playtime"):
            stats[key] = str(Duration(stats[key]))
        stats["db_update"] = str(
            datetime.datetime.fromtimestamp(int(stats["db_update"]))
        ).replace(":", "∶")

        for i, key in enumerate(
            (
                "protocol",
                "uptime",
                "playtime",
                "db_update",
                "db_playtime",
                "artists",
                "albums",
                "songs",
            )
        ):
            grid.attach(
                Gtk.Label(label=display_str[key], use_markup=True, xalign=1), 0, i, 1, 1
            )
            grid.attach(Gtk.Label(label=stats[key], xalign=0), 1, i, 1, 1)

        # packing
        vbox = self.get_content_area()
        vbox.set_property("border-width", 6)
        vbox.pack_start(grid, True, True, 0)
        self.show_all()
        self.run()
