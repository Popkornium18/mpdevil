import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib


class MPRISInterface:  # TODO emit Seeked if needed
    """
    based on 'Lollypop' (master 22.12.2020) by Cedric Bellegarde <cedric.bellegarde@adishatz.org>
    and 'mpDris2' (master 19.03.2020) by Jean-Philippe Braun <eon@patapon.info>, Mantas Mikulėnas <grawity@gmail.com>
    """

    _MPRIS_IFACE = "org.mpris.MediaPlayer2"
    _MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
    _MPRIS_NAME = "org.mpris.MediaPlayer2.mpdevil"
    _MPRIS_PATH = "/org/mpris/MediaPlayer2"
    _INTERFACES_XML = """
	<!DOCTYPE node PUBLIC
	"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
	"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
	<node>
		<interface name="org.freedesktop.DBus.Introspectable">
			<method name="Introspect">
				<arg name="data" direction="out" type="s"/>
			</method>
		</interface>
		<interface name="org.freedesktop.DBus.Properties">
			<method name="Get">
				<arg name="interface" direction="in" type="s"/>
				<arg name="property" direction="in" type="s"/>
				<arg name="value" direction="out" type="v"/>
			</method>
			<method name="Set">
				<arg name="interface_name" direction="in" type="s"/>
				<arg name="property_name" direction="in" type="s"/>
				<arg name="value" direction="in" type="v"/>
			</method>
			<method name="GetAll">
				<arg name="interface" direction="in" type="s"/>
				<arg name="properties" direction="out" type="a{sv}"/>
			</method>
		</interface>
		<interface name="org.mpris.MediaPlayer2">
			<method name="Raise">
			</method>
			<method name="Quit">
			</method>
			<property name="CanQuit" type="b" access="read" />
			<property name="CanRaise" type="b" access="read" />
			<property name="HasTrackList" type="b" access="read"/>
			<property name="Identity" type="s" access="read"/>
			<property name="DesktopEntry" type="s" access="read"/>
			<property name="SupportedUriSchemes" type="as" access="read"/>
			<property name="SupportedMimeTypes" type="as" access="read"/>
		</interface>
		<interface name="org.mpris.MediaPlayer2.Player">
			<method name="Next"/>
			<method name="Previous"/>
			<method name="Pause"/>
			<method name="PlayPause"/>
			<method name="Stop"/>
			<method name="Play"/>
			<method name="Seek">
				<arg direction="in" name="Offset" type="x"/>
			</method>
			<method name="SetPosition">
				<arg direction="in" name="TrackId" type="o"/>
				<arg direction="in" name="Position" type="x"/>
			</method>
			<method name="OpenUri">
				<arg direction="in" name="Uri" type="s"/>
			</method>
			<signal name="Seeked">
				<arg name="Position" type="x"/>
			</signal>
			<property name="PlaybackStatus" type="s" access="read"/>
			<property name="LoopStatus" type="s" access="readwrite"/>
			<property name="Rate" type="d" access="readwrite"/>
			<property name="Shuffle" type="b" access="readwrite"/>
			<property name="Metadata" type="a{sv}" access="read"/>
			<property name="Volume" type="d" access="readwrite"/>
			<property name="Position" type="x" access="read"/>
			<property name="MinimumRate" type="d" access="read"/>
			<property name="MaximumRate" type="d" access="read"/>
			<property name="CanGoNext" type="b" access="read"/>
			<property name="CanGoPrevious" type="b" access="read"/>
			<property name="CanPlay" type="b" access="read"/>
			<property name="CanPause" type="b" access="read"/>
			<property name="CanSeek" type="b" access="read"/>
			<property name="CanControl" type="b" access="read"/>
		</interface>
	</node>
	"""

    def __init__(self, window, client, settings):
        self._window = window
        self._client = client
        self._settings = settings
        self._metadata = {}

        # MPRIS property mappings
        self._prop_mapping = {
            self._MPRIS_IFACE: {
                "CanQuit": (GLib.Variant("b", False), None),
                "CanRaise": (GLib.Variant("b", True), None),
                "HasTrackList": (GLib.Variant("b", False), None),
                "Identity": (GLib.Variant("s", "mpdevil"), None),
                "DesktopEntry": (GLib.Variant("s", "org.mpdevil.mpdevil"), None),
                "SupportedUriSchemes": (GLib.Variant("s", "None"), None),
                "SupportedMimeTypes": (GLib.Variant("s", "None"), None),
            },
            self._MPRIS_PLAYER_IFACE: {
                "PlaybackStatus": (self._get_playback_status, None),
                "LoopStatus": (self._get_loop_status, self._set_loop_status),
                "Rate": (GLib.Variant("d", 1.0), None),
                "Shuffle": (self._get_shuffle, self._set_shuffle),
                "Metadata": (self._get_metadata, None),
                "Volume": (self._get_volume, self._set_volume),
                "Position": (self._get_position, None),
                "MinimumRate": (GLib.Variant("d", 1.0), None),
                "MaximumRate": (GLib.Variant("d", 1.0), None),
                "CanGoNext": (self._get_can_next_prev, None),
                "CanGoPrevious": (self._get_can_next_prev, None),
                "CanPlay": (self._get_can_play_pause_seek, None),
                "CanPause": (self._get_can_play_pause_seek, None),
                "CanSeek": (self._get_can_play_pause_seek, None),
                "CanControl": (GLib.Variant("b", True), None),
            },
        }

        # start
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(
            self._bus, self._MPRIS_NAME, Gio.BusNameOwnerFlags.NONE, None, None
        )
        self._node_info = Gio.DBusNodeInfo.new_for_xml(self._INTERFACES_XML)
        for interface in self._node_info.interfaces:
            self._bus.register_object(
                self._MPRIS_PATH, interface, self._handle_method_call, None, None
            )

        # connect
        self._client.emitter.connect("state", self._on_state_changed)
        self._client.emitter.connect("current_song", self._on_song_changed)
        self._client.emitter.connect("volume", self._on_volume_changed)
        self._client.emitter.connect("repeat", self._on_loop_changed)
        self._client.emitter.connect("single", self._on_loop_changed)
        self._client.emitter.connect("random", self._on_random_changed)
        self._client.emitter.connect("connection_error", self._on_connection_error)
        self._client.emitter.connect("reconnected", self._on_reconnected)

    def _handle_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):
        args = list(parameters.unpack())
        result = getattr(self, method_name)(*args)
        out_args = (
            self._node_info.lookup_interface(interface_name)
            .lookup_method(method_name)
            .out_args
        )
        if out_args:
            signature = "(" + "".join([arg.signature for arg in out_args]) + ")"
            variant = GLib.Variant(signature, (result,))
            invocation.return_value(variant)
        else:
            invocation.return_value(None)

    # setter and getter
    def _get_playback_status(self):
        if self._client.connected():
            status = self._client.status()
            return GLib.Variant(
                "s",
                {"play": "Playing", "pause": "Paused", "stop": "Stopped"}[
                    status["state"]
                ],
            )
        return GLib.Variant("s", "Stopped")

    def _set_loop_status(self, value):
        if self._client.connected():
            if value == "Playlist":
                self._client.repeat(1)
                self._client.single(0)
            elif value == "Track":
                self._client.repeat(1)
                self._client.single(1)
            elif value == "None":
                self._client.repeat(0)
                self._client.single(0)

    def _get_loop_status(self):
        if self._client.connected():
            status = self._client.status()
            if status["repeat"] == "1":
                if status.get("single", "0") == "0":
                    return GLib.Variant("s", "Playlist")
                else:
                    return GLib.Variant("s", "Track")
            else:
                return GLib.Variant("s", "None")
        return GLib.Variant("s", "None")

    def _set_shuffle(self, value):
        if self._client.connected():
            if value:
                self._client.random("1")
            else:
                self._client.random("0")

    def _get_shuffle(self):
        if self._client.connected():
            if self._client.status()["random"] == "1":
                return GLib.Variant("b", True)
            else:
                return GLib.Variant("b", False)
        return GLib.Variant("b", False)

    def _get_metadata(self):
        return GLib.Variant("a{sv}", self._metadata)

    def _get_volume(self):
        if self._client.connected():
            return GLib.Variant(
                "d", float(self._client.status().get("volume", 0)) / 100
            )
        return GLib.Variant("d", 0)

    def _set_volume(self, value):
        if self._client.connected():
            if value >= 0 and value <= 1:
                self._client.setvol(int(value * 100))

    def _get_position(self):
        if self._client.connected():
            status = self._client.status()
            return GLib.Variant("x", float(status.get("elapsed", 0)) * 1000000)
        return GLib.Variant("x", 0)

    def _get_can_next_prev(self):
        if self._client.connected():
            status = self._client.status()
            if status["state"] == "stop":
                return GLib.Variant("b", False)
            else:
                return GLib.Variant("b", True)
        return GLib.Variant("b", False)

    def _get_can_play_pause_seek(self):
        return GLib.Variant("b", self._client.connected())

    # introspect methods
    def Introspect(self):
        return self._INTERFACES_XML

    # property methods
    def Get(self, interface_name, prop):
        getter, setter = self._prop_mapping[interface_name][prop]
        if callable(getter):
            return getter()
        return getter

    def Set(self, interface_name, prop, value):
        getter, setter = self._prop_mapping[interface_name][prop]
        if setter is not None:
            setter(value)

    def GetAll(self, interface_name):
        read_props = {}
        try:
            props = self._prop_mapping[interface_name]
            for key, (getter, setter) in props.items():
                if callable(getter):
                    getter = getter()
                read_props[key] = getter
        except KeyError:  # interface has no properties
            pass
        return read_props

    def PropertiesChanged(
        self, interface_name, changed_properties, invalidated_properties
    ):
        self._bus.emit_signal(
            None,
            self._MPRIS_PATH,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant.new_tuple(
                GLib.Variant("s", interface_name),
                GLib.Variant("a{sv}", changed_properties),
                GLib.Variant("as", invalidated_properties),
            ),
        )

    # root methods
    def Raise(self):
        self._window.present()

    def Quit(self):
        app_action_group = self._window.get_action_group("app")
        quit_action = app_action_group.lookup_action("quit")
        quit_action.activate()

    # player methods
    def Next(self):
        self._client.next()

    def Previous(self):
        self._client.conditional_previous()

    def Pause(self):
        self._client.pause(1)

    def PlayPause(self):
        self._client.toggle_play()

    def Stop(self):
        self._client.stop()

    def Play(self):
        self._client.play()

    def Seek(self, offset):
        if offset > 0:
            offset = "+" + str(offset / 1000000)
        else:
            offset = str(offset / 1000000)
        self._client.seekcur(offset)

    def SetPosition(self, trackid, position):
        song = self._client.currentsong()
        if str(trackid).split("/")[-1] != song["id"]:
            return
        mpd_pos = position / 1000000
        if mpd_pos >= 0 and mpd_pos <= float(song["duration"]):
            self._client.seekcur(str(mpd_pos))

    def OpenUri(self, uri):
        pass

    def Seeked(self, position):
        self._bus.emit_signal(
            None,
            self._MPRIS_PATH,
            self._MPRIS_PLAYER_IFACE,
            "Seeked",
            GLib.Variant.new_tuple(GLib.Variant("x", position)),
        )

    # other methods
    def _update_metadata(self):
        """
        Translate metadata returned by MPD to the MPRIS v2 syntax.
        http://www.freedesktop.org/wiki/Specifications/mpris-spec/metadata
        """
        song = self._client.currentsong()
        self._metadata = {}
        for tag, xesam_tag in (
            ("album", "album"),
            ("title", "title"),
            ("date", "contentCreated"),
        ):
            if tag in song:
                self._metadata[f"xesam:{xesam_tag}"] = GLib.Variant("s", song[tag][0])
        for tag, xesam_tag in (("track", "trackNumber"), ("disc", "discNumber")):
            if tag in song:
                self._metadata[f"xesam:{xesam_tag}"] = GLib.Variant(
                    "i", int(song[tag][0])
                )
        for tag, xesam_tag in (
            ("albumartist", "albumArtist"),
            ("artist", "artist"),
            ("composer", "composer"),
            ("genre", "genre"),
        ):
            if tag in song:
                self._metadata[f"xesam:{xesam_tag}"] = GLib.Variant("as", song[tag])
        if "id" in song:
            self._metadata["mpris:trackid"] = GLib.Variant(
                "o", f"{self._MPRIS_PATH}/Track/{song['id']}"
            )
        if "duration" in song:
            self._metadata["mpris:length"] = GLib.Variant(
                "x", float(song["duration"]) * 1000000
            )
        if "file" in song:
            song_file = song["file"]
            if "://" in song_file:  # remote file
                self._metadata["xesam:url"] = GLib.Variant("s", song_file)
            else:
                song_path = self._client.get_absolute_path(song_file)
                if song_path is not None:
                    self._metadata["xesam:url"] = GLib.Variant(
                        "s", f"file://{song_path}"
                    )
                cover_path = self._client.get_cover_path(song)
                if cover_path is not None:
                    self._metadata["mpris:artUrl"] = GLib.Variant(
                        "s", f"file://{cover_path}"
                    )

    def _update_property(self, interface_name, prop):
        getter, setter = self._prop_mapping[interface_name][prop]
        if callable(getter):
            value = getter()
        else:
            value = getter
        self.PropertiesChanged(interface_name, {prop: value}, [])
        return value

    def _on_state_changed(self, *args):
        self._update_property(self._MPRIS_PLAYER_IFACE, "PlaybackStatus")
        self._update_property(self._MPRIS_PLAYER_IFACE, "CanGoNext")
        self._update_property(self._MPRIS_PLAYER_IFACE, "CanGoPrevious")

    def _on_song_changed(self, *args):
        self._update_metadata()
        self._update_property(self._MPRIS_PLAYER_IFACE, "Metadata")

    def _on_volume_changed(self, *args):
        self._update_property(self._MPRIS_PLAYER_IFACE, "Volume")

    def _on_loop_changed(self, *args):
        self._update_property(self._MPRIS_PLAYER_IFACE, "LoopStatus")

    def _on_random_changed(self, *args):
        self._update_property(self._MPRIS_PLAYER_IFACE, "Shuffle")

    def _on_reconnected(self, *args):
        properties = ("CanPlay", "CanPause", "CanSeek")
        for p in properties:
            self._update_property(self._MPRIS_PLAYER_IFACE, p)

    def _on_connection_error(self, *args):
        self._metadata = {}
        properties = (
            "PlaybackStatus",
            "CanGoNext",
            "CanGoPrevious",
            "Metadata",
            "Volume",
            "LoopStatus",
            "Shuffle",
            "CanPlay",
            "CanPause",
            "CanSeek",
        )
        for p in properties:
            self._update_property(self._MPRIS_PLAYER_IFACE, p)
