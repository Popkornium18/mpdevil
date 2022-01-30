import gi
from mpdevil.mpd_client_wrapper import Duration

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango


class SeekBar(Gtk.Box):
    def __init__(self, client):
        super().__init__(hexpand=True, margin_start=6, margin_right=6)
        self._client = client
        self._update = True
        self._jumped = False

        # labels
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontFeatures.new("tnum 1"))
        self._elapsed = Gtk.Label(xalign=0, attributes=attrs)
        self._rest = Gtk.Label(xalign=1, attributes=attrs)

        # event boxes
        elapsed_event_box = Gtk.EventBox(child=self._elapsed)
        rest_event_box = Gtk.EventBox(child=self._rest)

        # progress bar
        self._scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            show_fill_level=True,
            restrict_to_fill_level=False,
            draw_value=False,
            can_focus=False,
        )
        self._scale.set_increments(10, 60)
        self._adjustment = self._scale.get_adjustment()

        # connect
        elapsed_event_box.connect(
            "button-release-event", self._on_elapsed_button_release_event
        )
        rest_event_box.connect(
            "button-release-event", self._on_rest_button_release_event
        )
        self._scale.connect("change-value", self._on_change_value)
        self._scale.connect("scroll-event", lambda *args: True)  # disable mouse wheel
        self._scale.connect("button-press-event", self._on_scale_button_press_event)
        self._scale.connect("button-release-event", self._on_scale_button_release_event)
        self._client.emitter.connect("disconnected", self._disable)
        self._client.emitter.connect("state", self._on_state)
        self._client.emitter.connect("elapsed", self._refresh)

        # packing
        self.pack_start(elapsed_event_box, False, False, 0)
        self.pack_start(self._scale, True, True, 0)
        self.pack_end(rest_event_box, False, False, 0)

    def _refresh(self, emitter, elapsed, duration):
        self.set_sensitive(True)
        if duration > 0:
            if elapsed > duration:  # fix display error
                elapsed = duration
            self._adjustment.set_upper(duration)
            if self._update:
                self._scale.set_value(elapsed)
                self._elapsed.set_text(str(Duration(elapsed)))
                self._rest.set_text(str(Duration(elapsed - duration)))
            self._scale.set_fill_level(elapsed)
        else:
            self._disable()
            self._elapsed.set_text(str(Duration(elapsed)))

    def _disable(self, *args):
        self.set_sensitive(False)
        self._scale.set_fill_level(0)
        self._scale.set_range(0, 0)
        self._elapsed.set_text(str(Duration()))
        self._rest.set_text(str(Duration()))

    def _on_scale_button_press_event(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            self._update = False
            self._scale.set_has_origin(False)
        elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            self._jumped = False

    def _on_scale_button_release_event(self, widget, event):
        if event.button == 1:
            self._update = True
            self._scale.set_has_origin(True)
            if self._jumped:  # actual seek
                self._client.seekcur(self._scale.get_value())
                self._jumped = False
            else:  # restore state
                status = self._client.status()
                self._refresh(None, float(status["elapsed"]), float(status["duration"]))

    def _on_change_value(
        self, range, scroll, value
    ):  # value is inaccurate (can be above upper limit)
        if (
            scroll == Gtk.ScrollType.STEP_BACKWARD
            or scroll == Gtk.ScrollType.STEP_FORWARD
            or scroll == Gtk.ScrollType.PAGE_BACKWARD
            or scroll == Gtk.ScrollType.PAGE_FORWARD
        ):
            self._client.seekcur(value)
        elif scroll == Gtk.ScrollType.JUMP:
            duration = self._adjustment.get_upper()
            if value > duration:  # fix display error
                elapsed = duration
            else:
                elapsed = value
            self._elapsed.set_text(str(Duration(elapsed)))
            self._rest.set_text(str(Duration(elapsed - duration)))
            self._jumped = True

    def _on_elapsed_button_release_event(self, widget, event):
        if event.button == 1:
            self._client.seekcur(
                "-" + str(self._adjustment.get_property("step-increment"))
            )
        elif event.button == 3:
            self._client.seekcur(
                "+" + str(self._adjustment.get_property("step-increment"))
            )

    def _on_rest_button_release_event(self, widget, event):
        if event.button == 1:
            self._client.seekcur(
                "+" + str(self._adjustment.get_property("step-increment"))
            )
        elif event.button == 3:
            self._client.seekcur(
                "-" + str(self._adjustment.get_property("step-increment"))
            )

    def _on_state(self, emitter, state):
        if state == "stop":
            self._disable()
