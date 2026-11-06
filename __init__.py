"""Quick Settings Toolbar: the Options > Quick settings checkboxes as an optional toolbar."""

from functools import partial
from pathlib import Path
import re
import shutil

from PyQt6 import (
    QtCore,
    QtGui,
    QtWidgets,
)

from picard import log
from picard.config import get_config
from picard.const.appdirs import config_folder
from picard.i18n import gettext as _
from picard.options import (
    Option,
    get_option_title,
)


TOOLBAR_NAME = 'quick_settings_toolbar'
ALIASES_FILE = 'quick menu toolbar aliases.txt'  # lives in Picard's config folder
ALIASES_EXAMPLE_FILE = 'aliases.example.txt'  # ships with the plugin, copied on first run
CONFIGURE_PAGE = 'interface_quick_menu'


def ensure_aliases_file(plugin_dir):
    """Return the user's aliases file path, creating it from the shipped example if missing."""
    path = Path(config_folder()) / ALIASES_FILE
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plugin_dir / ALIASES_EXAMPLE_FILE, path)
        except OSError as e:
            log.warning('Quick Settings Toolbar: could not create %s: %s', path, e)
    return path


def load_aliases(path):
    """Read 'option_name = Short label' lines. Returns a dict in file order."""
    aliases = {}
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return aliases
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, label = line.split('=', 1)
        name, label = name.strip(), label.strip()
        if name and label:
            aliases[name] = label
    return aliases


def note_unaliased(path, entries):
    """Append a commented '# option_name = Full title' line for settings the file doesn't mention yet."""
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return
    missing = [(name, title) for name, title in entries if not re.search(rf'^\s*#?\s*{re.escape(name)}\s*=', text, re.M)]
    if not missing:
        return
    if text and not text.endswith('\n'):
        text += '\n'
    text += ''.join(f'# {name} = {title}\n' for name, title in missing)
    try:
        path.write_text(text, encoding='utf-8')
    except OSError as e:
        log.warning('Quick Settings Toolbar: could not update %s: %s', path, e)


class QuickSettingsToolbar(QtWidgets.QToolBar):
    def __init__(self, window, aliases_path):
        super().__init__(_("Quick settings"), parent=window)
        self.setObjectName(TOOLBAR_NAME)
        self._window = window
        self._aliases_path = aliases_path
        self._boxes = {}
        config = get_config()
        config.setting.setting_changed.connect(self._on_setting_changed)
        config.profiles.setting_changed.connect(self._on_profiles_changed)
        self.populate()

    def shutdown(self):
        config = get_config()
        for signal, slot in (
            (config.setting.setting_changed, self._on_setting_changed),
            (config.profiles.setting_changed, self._on_profiles_changed),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass

    def populate(self):
        config = get_config()
        aliases = load_aliases(self._aliases_path)
        order = {name: index for index, name in enumerate(aliases)}

        entries = []
        for setting_id in config.setting['quick_menu_items']:
            if Option.exists('setting', setting_id):
                entries.append((setting_id, _(get_option_title(setting_id))))
        entries.sort(key=lambda e: (order.get(e[0], len(order)), e[1].lower()))
        note_unaliased(self._aliases_path, entries)

        for action in self.actions():
            self.removeAction(action)
            action.deleteLater()
        self._boxes = {}

        if not entries:
            label = QtWidgets.QLabel(_("No quick settings configured"))
            label.setEnabled(False)
            self.addWidget(label)
            return

        for setting_id, full_title in entries:
            box = QtWidgets.QCheckBox(aliases.get(setting_id, full_title))
            box.setToolTip(full_title)
            box.setChecked(bool(config.setting[setting_id]))
            box.toggled.connect(partial(self._on_toggled, setting_id))
            self._boxes[setting_id] = box

            holder = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(holder)
            layout.setContentsMargins(6, 0, 6, 0)
            layout.addWidget(box)
            self.addWidget(holder)

    def _on_toggled(self, setting_id, checked):
        # Reuse the main window's handler so side effects (e.g. loading collections) still happen.
        # It flips the stored value, so only call it when the box and the setting disagree.
        if bool(get_config().setting[setting_id]) != checked:
            self._window._toggle_quick_setting(setting_id)

    def _on_setting_changed(self, name, old_value, new_value):
        if name == 'quick_menu_items':
            self.populate()
        elif name in self._boxes:
            box = self._boxes[name]
            with QtCore.QSignalBlocker(box):
                box.setChecked(bool(new_value))

    def _on_profiles_changed(self, *args):
        # Switching profiles can change both the list and the values.
        QtCore.QTimer.singleShot(0, self.populate)

    def contextMenuEvent(self, event):
        menu = self._window.createPopupMenu() or QtWidgets.QMenu(self)
        configure = QtGui.QAction(_("Configure quick settings…"), menu)
        configure.setMenuRole(QtGui.QAction.MenuRole.NoRole)
        configure.triggered.connect(lambda: self._window.show_options(CONFIGURE_PAGE))
        existing = menu.actions()
        if existing:
            menu.insertAction(existing[0], configure)
            menu.insertSeparator(existing[0])
        else:
            menu.addAction(configure)
        menu.exec(event.globalPos())
        event.accept()


_toolbar = None
_view_menu = None


def _add_view_menu_entry(window, toolbar):
    """Put the show/hide toggle in the View menu, right after the Search toolbar's."""
    search_toggle = window.search_toolbar.toggleViewAction()
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        actions = menu.actions()
        if search_toggle in actions:
            index = actions.index(search_toggle) + 1
            if index < len(actions):
                menu.insertAction(actions[index], toolbar.toggleViewAction())
            else:
                menu.addAction(toolbar.toggleViewAction())
            return menu
    return None


def _restore_saved_layout(window):
    """Picard restores window state before plugins load, so our toolbar missed it. Do it again.

    Only done when the saved state actually mentions our toolbar (i.e. not on first run).
    """
    state = get_config().persist['window_state']
    if state and TOOLBAR_NAME.encode('utf-16-be') in bytes(state):
        window.restoreState(state)


def enable(api):
    global _toolbar, _view_menu
    window = api.tagger.window
    _toolbar = QuickSettingsToolbar(window, ensure_aliases_file(api.plugin_dir))
    # Own row below the Actions/Search toolbars by default.
    window.addToolBarBreak(QtCore.Qt.ToolBarArea.TopToolBarArea)
    window.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, _toolbar)
    _view_menu = _add_view_menu_entry(window, _toolbar)
    _restore_saved_layout(window)


def disable():
    global _toolbar, _view_menu
    if _toolbar is None:
        return
    window = _toolbar.parentWidget()
    if _view_menu is not None:
        _view_menu.removeAction(_toolbar.toggleViewAction())
    _toolbar.shutdown()
    window.removeToolBarBreak(_toolbar)
    window.removeToolBar(_toolbar)
    _toolbar.deleteLater()
    _toolbar = None
    _view_menu = None
