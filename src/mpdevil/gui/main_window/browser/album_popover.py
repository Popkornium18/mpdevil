from gettext import gettext as _
import gi
from mpdevil.gui.main_window.songs_window import SongsWindow
from mpdevil.mpd_client_wrapper import Duration

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango, GLib


class AlbumPopover(Gtk.Popover):
    def __init__(self, client, settings):
        super().__init__()
        self._client = client
        self._settings = settings
        self._rect = Gdk.Rectangle()

        # songs window
        # (track, title (artist), duration, file, search text)
        self._store = Gtk.ListStore(str, str, str, str, str)
        songs_window = SongsWindow(self._client, self._store, 3, popover_mode=True)

        # scroll
        self._scroll = songs_window.get_scroll()
        self._scroll.set_propagate_natural_height(True)
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # songs view
        self._songs_view = songs_window.get_treeview()
        self._songs_view.set_property("search-column", 4)

        # columns
        renderer_text = Gtk.CellRendererText(
            width_chars=80, ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True
        )
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontFeatures.new("tnum 1"))
        renderer_text_tnum = Gtk.CellRendererText(
            ellipsize=Pango.EllipsizeMode.END, ellipsize_set=True, attributes=attrs
        )
        renderer_text_ralign_tnum = Gtk.CellRendererText(xalign=1.0, attributes=attrs)
        column_track = Gtk.TreeViewColumn(_("No"), renderer_text_ralign_tnum, text=0)
        column_track.set_property("resizable", False)
        self._songs_view.append_column(column_track)
        self._column_title = Gtk.TreeViewColumn(_("Title"), renderer_text, markup=1)
        self._column_title.set_property("resizable", False)
        self._column_title.set_property("expand", True)
        self._songs_view.append_column(self._column_title)
        column_time = Gtk.TreeViewColumn(_("Length"), renderer_text_tnum, text=2)
        column_time.set_property("resizable", False)
        self._songs_view.append_column(column_time)

        # connect
        songs_window.connect("button-clicked", lambda *args: self.popdown())

        # packing
        self.add(songs_window)
        songs_window.show_all()

    def open(self, albumartist, albumartistsort, album, albumsort, date, widget, x, y):
        self._rect.x = x
        self._rect.y = y
        self.set_pointing_to(self._rect)
        self.set_relative_to(widget)
        self._scroll.set_max_content_height(4 * widget.get_allocated_height() // 7)
        self._store.clear()
        tag_filter = (
            "albumartist",
            albumartist,
            "albumartistsort",
            albumartistsort,
            "album",
            album,
            "albumsort",
            albumsort,
            "date",
            date,
        )
        count = self._client.count(*tag_filter)
        duration = str(Duration(float(count["playtime"])))
        length = int(count["songs"])
        text = ngettext(
            "{number} song ({duration})", "{number} songs ({duration})", length
        ).format(number=length, duration=duration)
        self._column_title.set_title(" • ".join([_("Title"), text]))
        self._client.restrict_tagtypes("track", "title", "artist")
        songs = self._client.find(*tag_filter)
        self._client.tagtypes("all")
        for song in songs:
            track = song["track"][0]
            title = song["title"][0]
            # only show artists =/= albumartist
            try:
                song["artist"].remove(albumartist)
            except ValueError:
                pass
            artist = str(song["artist"])
            if artist == albumartist or not artist:
                title_artist = f"<b>{GLib.markup_escape_text(title)}</b>"
            else:
                title_artist = f"<b>{GLib.markup_escape_text(title)}</b> • {GLib.markup_escape_text(artist)}"
            self._store.append(
                [track, title_artist, str(song["duration"]), song["file"], title]
            )
        self._songs_view.scroll_to_cell(
            Gtk.TreePath(0), None, False
        )  # clear old scroll position
        self.popup()
        self._songs_view.columns_autosize()
