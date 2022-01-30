import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import Gio


class MPDActionGroup(Gio.SimpleActionGroup):
    def __init__(self, client):
        super().__init__()
        self._client = client

        # actions
        self._disable_on_stop_data = ("next", "prev", "seek-forward", "seek-backward")
        self._enable_on_reconnect_data = (
            "toggle-play",
            "stop",
            "clear",
            "update",
            "repeat",
            "random",
            "single",
            "consume",
            "single-oneshot",
        )
        self._data = self._disable_on_stop_data + self._enable_on_reconnect_data
        for name in self._data:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", getattr(self, ("_on_" + name.replace("-", "_"))))
            self.add_action(action)

        # connect
        self._client.emitter.connect("state", self._on_state)
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect("reconnected", self._on_reconnected)

    def _on_toggle_play(self, action, param):
        self._client.toggle_play()

    def _on_stop(self, action, param):
        self._client.stop()

    def _on_next(self, action, param):
        self._client.next()

    def _on_prev(self, action, param):
        self._client.conditional_previous()

    def _on_seek_forward(self, action, param):
        self._client.seekcur("+10")

    def _on_seek_backward(self, action, param):
        self._client.seekcur("-10")

    def _on_clear(self, action, param):
        self._client.clear()

    def _on_update(self, action, param):
        self._client.update()

    def _on_repeat(self, action, param):
        self._client.toggle_option("repeat")

    def _on_random(self, action, param):
        self._client.toggle_option("random")

    def _on_single(self, action, param):
        self._client.toggle_option("single")

    def _on_consume(self, action, param):
        self._client.toggle_option("consume")

    def _on_single_oneshot(self, action, param):
        self._client.single("oneshot")

    def _on_state(self, emitter, state):
        state_dict = {"play": True, "pause": True, "stop": False}
        for action in self._disable_on_stop_data:
            self.lookup_action(action).set_enabled(state_dict[state])

    def _on_disconnected(self, *args):
        for action in self._data:
            self.lookup_action(action).set_enabled(False)

    def _on_reconnected(self, *args):
        for action in self._enable_on_reconnect_data:
            self.lookup_action(action).set_enabled(True)
