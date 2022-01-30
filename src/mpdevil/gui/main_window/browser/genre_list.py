from gettext import gettext as _
from mpdevil.gui.main_window.browser.selection_list import SelectionList


class GenreList(SelectionList):
    def __init__(self, client):
        super().__init__(_("all genres"))
        self._client = client

        # connect
        self._client.emitter.connect("disconnected", self._on_disconnected)
        self._client.emitter.connect_after("reconnected", self._on_reconnected)
        self._client.emitter.connect("updated_db", self._refresh)

    def deactivate(self):
        self.select_all()

    def _refresh(self, *args):
        l = self._client.comp_list("genre")
        self.set_items(list(zip(l, l)))
        self.select_all()

    def _on_disconnected(self, *args):
        self.set_sensitive(False)
        self.clear()

    def _on_reconnected(self, *args):
        self._refresh()
        self.set_sensitive(True)
