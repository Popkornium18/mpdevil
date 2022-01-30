import gi
import collections
import datetime
import os
import locale
from mpd import MPDClient, base as MPDBase
from gettext import ngettext
from mpdevil.constants import (
    COVER_REGEX,
    FALLBACK_COVER,
    FALLBACK_SOCKET,
    FALLBACK_LIB,
)

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GObject, GLib


class Duration:
    def __init__(self, value=None):
        if value is None:
            self._fallback = True
            self._value = 0.0
        else:
            self._fallback = False
            self._value = float(value)

    def __str__(self):
        if self._fallback:
            return "‒‒∶‒‒"
        else:
            if self._value < 0:
                sign = "−"
                value = -int(self._value)
            else:
                sign = ""
                value = int(self._value)
            delta = datetime.timedelta(seconds=value)
            if delta.days > 0:
                days = ngettext("{days} day", "{days} days", delta.days).format(
                    days=delta.days
                )
                time_string = f"{days}, {datetime.timedelta(seconds=delta.seconds)}"
            else:
                time_string = str(delta).lstrip("0").lstrip(":")
            return sign + time_string.replace(":", "∶")  # use 'ratio' as delimiter

    def __float__(self):
        return self._value


class _LastModified:
    def __init__(self, date):
        self._date = date

    def __str__(self):
        time = datetime.datetime.strptime(self._date, "%Y-%m-%dT%H:%M:%SZ")
        return time.strftime("%a %d %B %Y, %H∶%M UTC")

    def raw(self):
        return self._date


class Format:
    def __init__(self, audio_format):
        self._format = audio_format

    def __str__(self):
        # see: https://www.musicpd.org/doc/html/user.html#audio-output-format
        samplerate, bits, channels = self._format.split(":")
        if bits == "f":
            bits = "32fp"
        try:
            int_chan = int(channels)
        except ValueError:
            int_chan = 0
        try:
            freq = locale.str(int(samplerate) / 1000)
        except ValueError:
            freq = samplerate
        channels = ngettext(
            "{channels} channel", "{channels} channels", int_chan
        ).format(channels=int_chan)
        return f"{freq} kHz • {bits} bit • {channels}"

    def raw(self):
        return self._format


class _MultiTag(list):
    def __str__(self):
        return ", ".join(self)


class _Song(collections.UserDict):
    def __setitem__(self, key, value):
        if (
            key == "time"
        ):  # time is deprecated https://mpd.readthedocs.io/en/latest/protocol.html#other-metadata
            pass
        elif key == "duration":
            super().__setitem__(key, Duration(value))
        elif key == "format":
            super().__setitem__(key, Format(value))
        elif key == "last-modified":
            super().__setitem__(key, _LastModified(value))
        elif key in ("range", "file", "pos", "id"):
            super().__setitem__(key, value)
        else:
            if isinstance(value, list):
                super().__setitem__(key, _MultiTag(value))
            else:
                super().__setitem__(key, _MultiTag([value]))

    def __missing__(self, key):
        if self.data:
            if key == "albumartist":
                return self["artist"]
            elif key == "albumartistsort":
                return self["albumartist"]
            elif key == "artistsort":
                return self["artist"]
            elif key == "albumsort":
                return self["album"]
            elif key == "title":
                return _MultiTag([os.path.basename(self.data["file"])])
            elif key == "duration":
                return Duration()
            else:
                return _MultiTag([""])
        else:
            return None


class _BinaryCover(bytes):
    def get_pixbuf(self, size):
        loader = GdkPixbuf.PixbufLoader()
        try:
            loader.write(self)
            loader.close()
            raw_pixbuf = loader.get_pixbuf()
            ratio = raw_pixbuf.get_width() / raw_pixbuf.get_height()
            if ratio > 1:
                pixbuf = raw_pixbuf.scale_simple(
                    size, size / ratio, GdkPixbuf.InterpType.BILINEAR
                )
            else:
                pixbuf = raw_pixbuf.scale_simple(
                    size * ratio, size, GdkPixbuf.InterpType.BILINEAR
                )
        except gi.repository.GLib.Error:  # load fallback if cover can't be loaded
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(FALLBACK_COVER, size, size)
        return pixbuf


class _FileCover(str):
    def get_pixbuf(self, size):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(self, size, size)
        except gi.repository.GLib.Error:  # load fallback if cover can't be loaded
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(FALLBACK_COVER, size, size)
        return pixbuf


class _EventEmitter(GObject.Object):
    __gsignals__ = {
        "updating_db": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "updated_db": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "disconnected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "reconnected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "connection_error": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "current_song": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "state": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "elapsed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (
                float,
                float,
            ),
        ),
        "volume": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "playlist": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "repeat": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "random": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "single": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "consume": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "audio": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "bitrate": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }


class Client(MPDClient):
    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self.emitter = _EventEmitter()
        self._last_status = {}
        self._refresh_interval = self._settings.get_int("refresh-interval")
        self._main_timeout_id = None
        self.lib_path = None

        # connect
        self._settings.connect(
            "changed::active-profile", self._on_active_profile_changed
        )

    # workaround for list group
    # see: https://github.com/Mic92/python-mpd2/pull/187
    def _parse_objects(self, lines, delimiters=[], lookup_delimiter=False):
        obj = {}
        for key, value in self._parse_pairs(lines):
            key = key.lower()
            if lookup_delimiter and key not in delimiters:
                delimiters = delimiters + [key]
            if obj:
                if key in delimiters:
                    if lookup_delimiter:
                        if key in obj:
                            yield obj
                            obj = obj.copy()
                            while delimiters[-1] != key:
                                obj.pop(delimiters[-1], None)
                                delimiters.pop()
                    else:
                        yield obj
                        obj = {}
                elif key in obj:
                    if not isinstance(obj[key], list):
                        obj[key] = [obj[key], value]
                    else:
                        obj[key].append(value)
                    continue
            obj[key] = value
        if obj:
            yield obj

    _parse_objects_direct = _parse_objects

    # overloads
    def currentsong(self, *args):
        return _Song(super().currentsong(*args))

    def search(self, *args):
        return [_Song(song) for song in super().search(*args)]

    def find(self, *args):
        return [_Song(song) for song in super().find(*args)]

    def playlistinfo(self):
        return [_Song(song) for song in super().playlistinfo()]

    def plchanges(self, version):
        return [_Song(song) for song in super().plchanges(version)]

    def lsinfo(self, uri):
        return [_Song(song) for song in super().lsinfo(uri)]

    def start(self):
        self.emitter.emit("disconnected")  # bring player in defined state
        profile = self._settings.get_active_profile()
        if profile.get_boolean("socket-connection"):
            socket = profile.get_string("socket")
            if not socket:
                socket = FALLBACK_SOCKET
            args = (socket, None)
        else:
            args = (profile.get_string("host"), profile.get_int("port"))
        try:
            self.connect(*args)
            if profile.get_string("password"):
                self.password(profile.get_string("password"))
        except:
            self.emitter.emit("connection_error")
            return False
        # connect successful
        if profile.get_boolean("socket-connection"):
            self.lib_path = self.config()
        else:
            self.lib_path = self._settings.get_active_profile().get_string("path")
            if not self.lib_path:
                self.lib_path = FALLBACK_LIB
        if "status" in self.commands():
            self._main_timeout_id = GLib.timeout_add(
                self._refresh_interval, self._main_loop
            )
            self.emitter.emit("reconnected")
            return True
        else:
            self.disconnect()
            self.emitter.emit("connection_error")
            print("No read permission, check your mpd config.")
            return False

    def reconnect(self):
        if self._main_timeout_id is not None:
            GLib.source_remove(self._main_timeout_id)
            self._main_timeout_id = None
        self._last_status = {}
        self.disconnect()
        self.start()

    def connected(self):
        try:
            self.ping()
            return True
        except:
            return False

    def _to_playlist(
        self, append, mode="default"
    ):  # modes: default, play, append, enqueue
        if mode == "default":
            if self._settings.get_boolean("force-mode"):
                mode = "play"
            else:
                mode = "enqueue"
        if mode == "append":
            append()
        elif mode == "play":
            self.clear()
            append()
            self.play()
        elif mode == "enqueue":
            status = self.status()
            if status["state"] == "stop":
                self.clear()
                append()
            else:
                self.moveid(status["songid"], 0)
                current_song_file = self.currentsong()["file"]
                try:
                    self.delete(
                        (1,)
                    )  # delete all songs, but the first. bad song index possible
                except MPDBase.CommandError:
                    pass
                append()
                duplicates = self.playlistfind("file", current_song_file)
                if len(duplicates) > 1:
                    self.move(0, duplicates[1]["pos"])
                    self.delete(int(duplicates[1]["pos"]) - 1)

    def files_to_playlist(self, files, mode="default"):
        def append():
            for f in files:
                self.add(f)

        self._to_playlist(append, mode)

    def filter_to_playlist(self, tag_filter, mode="default"):
        def append():
            if tag_filter:
                self.findadd(*tag_filter)
            else:
                self.searchadd("any", "")

        self._to_playlist(append, mode)

    def album_to_playlist(
        self, albumartist, albumartistsort, album, albumsort, date, mode="default"
    ):
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
        self.filter_to_playlist(tag_filter, mode)

    def artist_to_playlist(self, artist, genre, mode="default"):
        def append():
            if genre is None:
                genre_filter = ()
            else:
                genre_filter = ("genre", genre)
            if artist is None:
                artists = self.get_artists(genre)
            else:
                artists = [artist]
            for albumartist, albumartistsort in artists:
                albums = self.list(
                    "album",
                    "albumartist",
                    albumartist,
                    "albumartistsort",
                    albumartistsort,
                    *genre_filter,
                    "group",
                    "date",
                    "group",
                    "albumsort",
                )
                for album in albums:
                    self.findadd(
                        "albumartist",
                        albumartist,
                        "albumartistsort",
                        albumartistsort,
                        "album",
                        album["album"],
                        "albumsort",
                        album["albumsort"],
                        "date",
                        album["date"],
                    )

        self._to_playlist(append, mode)

    def comp_list(self, *args):  # simulates listing behavior of python-mpd2 1.0
        native_list = self.list(*args)
        if len(native_list) > 0:
            if isinstance(native_list[0], dict):
                return [l[args[0]] for l in native_list]
            else:
                return native_list
        else:
            return []

    def get_artists(self, genre):
        if genre is None:
            artists = self.list("albumartist", "group", "albumartistsort")
        else:
            artists = self.list(
                "albumartist", "genre", genre, "group", "albumartistsort"
            )
        return [
            (artist["albumartist"], artist["albumartistsort"]) for artist in artists
        ]

    def get_cover_path(self, song):
        path = None
        song_file = song["file"]
        profile = self._settings.get_active_profile()
        if self.lib_path is not None:
            regex_str = profile.get_string("regex")
            if regex_str:
                regex_str = regex_str.replace(
                    "%AlbumArtist%", re.escape(song["albumartist"][0])
                )
                regex_str = regex_str.replace("%Album%", re.escape(song["album"][0]))
                try:
                    regex = re.compile(regex_str, flags=re.IGNORECASE)
                except re.error:
                    print("illegal regex:", regex_str)
                    return None
            else:
                regex = re.compile(COVER_REGEX, flags=re.IGNORECASE)
            song_dir = os.path.join(self.lib_path, os.path.dirname(song_file))
            if song_dir.lower().endswith(".cue"):
                song_dir = os.path.dirname(
                    song_dir
                )  # get actual directory of .cue file
            if os.path.isdir(song_dir):
                for f in os.listdir(song_dir):
                    if regex.match(f):
                        path = os.path.join(song_dir, f)
                        break
        return path

    def get_cover_binary(self, uri):
        try:
            binary = self.albumart(uri)["binary"]
        except:
            try:
                binary = self.readpicture(uri)["binary"]
            except:
                binary = None
        return binary

    def get_cover(self, song):
        cover_path = self.get_cover_path(song)
        if cover_path is None:
            cover_binary = self.get_cover_binary(song["file"])
            if cover_binary is None:
                cover = _FileCover(FALLBACK_COVER)
            else:
                cover = _BinaryCover(cover_binary)
        else:
            cover = _FileCover(cover_path)
        return cover

    def get_absolute_path(self, uri):
        if self.lib_path is not None:
            path = os.path.join(self.lib_path, uri)
            if os.path.isfile(path):
                return path
            else:
                return None
        else:
            return None

    def toggle_play(self):
        status = self.status()
        if status["state"] == "play":
            self.pause(1)
        elif status["state"] == "pause":
            self.pause(0)
        else:
            try:
                self.play()
            except:
                pass

    def toggle_option(self, option):  # repeat, random, single, consume
        new_state = int(self.status()[option] == "0")
        func = getattr(self, option)
        func(new_state)

    def conditional_previous(self):
        if self._settings.get_boolean("rewind-mode"):
            double_click_time = Gtk.Settings.get_default().get_property(
                "gtk-double-click-time"
            )
            status = self.status()
            if float(status.get("elapsed", 0)) * 1000 > double_click_time:
                self.seekcur(0)
            else:
                self.previous()
        else:
            self.previous()

    def restrict_tagtypes(self, *tags):
        self.command_list_ok_begin()
        self.tagtypes("clear")
        for tag in tags:
            self.tagtypes("enable", tag)
        self.command_list_end()

    def _main_loop(self, *args):
        try:
            status = self.status()
            diff = set(status.items()) - set(self._last_status.items())
            for key, val in diff:
                if key == "elapsed":
                    if "duration" in status:
                        self.emitter.emit(
                            "elapsed", float(val), float(status["duration"])
                        )
                    else:
                        self.emitter.emit("elapsed", float(val), 0.0)
                elif key == "bitrate":
                    if val == "0":
                        self.emitter.emit("bitrate", None)
                    else:
                        self.emitter.emit("bitrate", val)
                elif key == "songid":
                    self.emitter.emit("current_song")
                elif key in ("state", "single", "audio"):
                    self.emitter.emit(key, val)
                elif key == "volume":
                    self.emitter.emit("volume", float(val))
                elif key == "playlist":
                    self.emitter.emit("playlist", int(val))
                elif key in ("repeat", "random", "consume"):
                    if val == "1":
                        self.emitter.emit(key, True)
                    else:
                        self.emitter.emit(key, False)
                elif key == "updating_db":
                    self.emitter.emit("updating_db")
            diff = set(self._last_status) - set(status)
            for key in diff:
                if "songid" == key:
                    self.emitter.emit("current_song")
                elif "volume" == key:
                    self.emitter.emit("volume", -1)
                elif "updating_db" == key:
                    self.emitter.emit("updated_db")
                elif "bitrate" == key:
                    self.emitter.emit("bitrate", None)
                elif "audio" == key:
                    self.emitter.emit("audio", None)
            self._last_status = status
        except (MPDBase.ConnectionError, ConnectionResetError) as e:
            self.disconnect()
            self._last_status = {}
            self.emitter.emit("disconnected")
            self.emitter.emit("connection_error")
            self._main_timeout_id = None
            return False
        return True

    def _on_active_profile_changed(self, *args):
        self.reconnect()
