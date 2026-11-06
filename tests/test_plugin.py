import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types


os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parent.parent
PICARD_SRC = os.environ.get('PICARD_SRC')
if not PICARD_SRC or not (Path(PICARD_SRC) / 'picard').is_dir():
    sys.exit('Set PICARD_SRC to a checkout of the Picard source, e.g. PICARD_SRC=~/src/picard python3 tests/test_plugin.py')
sys.path.insert(0, PICARD_SRC)

from PyQt6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication([])

import picard.options  # noqa: F401  registers all options
from picard import config as picard_config

work = Path(tempfile.mkdtemp())
plugin_dir = work / 'quick-settings-toolbar'
shutil.copytree(ROOT, plugin_dir, ignore=shutil.ignore_patterns('.git', 'tests', '__pycache__'))
files_before = sorted(p.name for p in plugin_dir.iterdir())
cfg_dir = work / 'cfg'
os.environ['PICARD_CONFIG_DIR'] = str(cfg_dir)
user_aliases = cfg_dir / 'quick menu toolbar aliases.txt'
example_before = (plugin_dir / 'aliases.example.txt').read_text()

picard_config.setup_config(app, str(work / 'picard.ini'))
cfg = picard_config.get_config()

spec = importlib.util.spec_from_file_location('qst_plugin', plugin_dir / '__init__.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class FakeWindow(QtWidgets.QMainWindow):
    """Minimal stand-in for Picard's MainWindow: same attribute names the plugin touches."""

    def __init__(self):
        super().__init__()
        self.shown_pages = []
        self.toolbar = self.addToolBar('Actions')
        self.toolbar.setObjectName('main_toolbar')
        self.toolbar.addAction('Add Files')
        self.search_toolbar = self.addToolBar('Search')
        self.search_toolbar.setObjectName('search_toolbar')
        self.search_toolbar.addWidget(QtWidgets.QLineEdit())
        view = self.menuBar().addMenu('&View')
        view.addAction('Show cover art')
        view.addAction(self.search_toolbar.toggleViewAction())
        view.addAction('Show filter bar')
        self.setCentralWidget(QtWidgets.QTextEdit())
        self.resize(900, 300)

    def show_options(self, page=None):
        self.shown_pages.append(page)

    def _toggle_quick_setting(self, setting_id):  # copy of MainWindow's implementation
        config = picard_config.get_config()
        config.setting[setting_id] = not config.setting[setting_id]


def make_api(window):
    return types.SimpleNamespace(tagger=types.SimpleNamespace(window=window), plugin_dir=plugin_dir)


def checks(toolbar):
    return {sid: box for sid, box in toolbar._boxes.items()}


failures = []


def check(cond, msg):
    print(('PASS  ' if cond else 'FAIL  ') + msg)
    if not cond:
        failures.append(msg)


# ---- 0. first run ----
check(not user_aliases.exists(), 'no user aliases file before first run')
# ---- 1. build ----
cfg.setting['quick_menu_items'] = [
    'rename_files', 'move_files', 'enable_tag_saving', 'save_images_to_tags', 'save_images_to_files',
]
w = FakeWindow()
plugin.enable(make_api(w))
tb = plugin._toolbar
w.show()
app.processEvents()

check(user_aliases.exists() and user_aliases.read_text().startswith('# Short labels'), 'first run copies example into config folder')
labels = [b.text() for b in tb._boxes.values()]
check(labels == ['Save tags', 'Rename', 'Move', 'Images in tags', 'Images saved separately'], f'labels/order from aliases.txt: {labels}')
tips = {sid: b.toolTip() for sid, b in tb._boxes.items()}
check(tips['save_images_to_files'] == 'Save images as separate files', f"tooltip is full title: {tips['save_images_to_files']!r}")
check(tips['enable_tag_saving'] == 'Save tags to files', f"tooltip full title 2: {tips['enable_tag_saving']!r}")
check(tb.isVisible(), 'toolbar visible by default')
check(w.toolBarBreak(tb), 'toolbar starts on its own row (break before it)')
check(w.toolBarArea(tb) == QtCore.Qt.ToolBarArea.TopToolBarArea, 'toolbar in top area')

view_actions = [a.text() for a in w.menuBar().actions()[0].menu().actions()]
check(view_actions == ['Show cover art', 'Search', 'Quick settings', 'Show filter bar'], f'View menu entry placement: {view_actions}')

# ---- 2. toggling ----
before = bool(cfg.setting['rename_files'])
tb._boxes['rename_files'].click()
check(bool(cfg.setting['rename_files']) != before, 'clicking checkbox flips config')
check(tb._boxes['rename_files'].isChecked() == bool(cfg.setting['rename_files']), 'checkbox matches config after click')
cfg.setting['move_files'] = True
check(tb._boxes['move_files'].isChecked(), 'external config change updates checkbox')
cfg.setting['move_files'] = False
check(not tb._boxes['move_files'].isChecked(), 'external change back updates checkbox')

# ---- 3. list changes ----
cfg.setting['quick_menu_items'] = ['rename_files', 'enable_ratings', 'save_images_to_files']
app.processEvents()
labels = [b.text() for b in tb._boxes.values()]
check(labels == ['Rename', 'Images saved separately', 'Enable track ratings'], f'repopulate after list change: {labels}')
check(len(tb.actions()) == 3, f'old widgets removed, actions={len(tb.actions())}')
text = user_aliases.read_text()
check('# enable_ratings = Enable track ratings' in text, 'unaliased setting appended as comment')
cfg.setting['quick_menu_items'] = ['rename_files', 'enable_ratings', 'save_images_to_files', 'move_files']
app.processEvents()
text2 = user_aliases.read_text()
check(text2.count('enable_ratings') == 1, 'comment line not duplicated on later repopulate')

# ---- 4. empty ----
cfg.setting['quick_menu_items'] = []
app.processEvents()
check(len(tb.actions()) == 1 and not tb._boxes, 'empty list shows placeholder only')
cfg.setting['quick_menu_items'] = ['rename_files']
app.processEvents()
check(list(tb._boxes) == ['rename_files'], 'recovers from empty')
cfg.setting['quick_menu_items'] = ['rename_files', 'move_files', 'enable_tag_saving', 'save_images_to_tags', 'save_images_to_files']
app.processEvents()

# ---- 5. context menu ----
captured = []
orig_exec = QtWidgets.QMenu.exec
QtWidgets.QMenu.exec = lambda self, *a: captured.append([x.text() for x in self.actions()])
ev = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, QtCore.QPoint(5, 5), QtCore.QPoint(5, 5))
tb.contextMenuEvent(ev)
QtWidgets.QMenu.exec = orig_exec
check(captured and captured[0][0] == 'Configure quick settings…', f'context menu starts with configure: {captured[0][:4] if captured else None}')
check(any('Quick settings' == t for t in captured[0]), 'context menu also keeps the toolbar toggle list')
conf = [a for a in w.createPopupMenu().actions()]  # sanity: Qt's own menu exists
check(len(conf) >= 3, 'createPopupMenu lists toolbars')

# trigger the configure action
def run_and_trigger(self, *a):
    for act in self.actions():
        if act.text().startswith('Configure'):
            act.trigger()
QtWidgets.QMenu.exec = run_and_trigger
tb.contextMenuEvent(ev)
QtWidgets.QMenu.exec = orig_exec
check(w.shown_pages == ['interface_quick_menu'], f'configure opens quick menu page: {w.shown_pages}')

# ---- 6. screenshot ----
app.processEvents()
w.grab().save(str(ROOT / 'tests' / 'shot_default.png'))

# ---- 7. layout persistence ----
tb.hide()
cfg.persist['window_state'] = w.saveState()
plugin.disable()
w.close()
w2 = FakeWindow()
plugin.enable(make_api(w2))
w2.show()
app.processEvents()
check(not plugin._toolbar.isVisible(), 'hidden state restored on next start')
plugin.disable()
w2.close()

cfg.persist['window_state'] = QtCore.QByteArray()
w3 = FakeWindow()
plugin.enable(make_api(w3))
w3.show()
app.processEvents()
check(plugin._toolbar.isVisible(), 'first run (no saved state): visible')
# moved to left side?  persist and restore area
w3.removeToolBar(plugin._toolbar)
w3.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, plugin._toolbar)
plugin._toolbar.show()
cfg.persist['window_state'] = w3.saveState()
plugin.disable()
w3.close()
w4 = FakeWindow()
plugin.enable(make_api(w4))
w4.show()
app.processEvents()
check(w4.toolBarArea(plugin._toolbar) == QtCore.Qt.ToolBarArea.BottomToolBarArea, 'moved-to-bottom position restored')
check(w4.toolBarArea(w4.toolbar) == QtCore.Qt.ToolBarArea.TopToolBarArea, 'other toolbars unaffected by re-restore')

# ---- 7b. files ----
check((plugin_dir / 'aliases.example.txt').read_text() == example_before, 'shipped example never modified')
check(sorted(p.name for p in plugin_dir.iterdir() if p.name != '__pycache__') == files_before, 'plugin folder untouched (no files written into it)')
user_aliases.write_text('rename_files = MyRename\n')
cfg.setting['quick_menu_items'] = ['rename_files']
w5 = FakeWindow()
plugin.enable(make_api(w5))
check(user_aliases.read_text().startswith('rename_files = MyRename'), 'existing user file is not overwritten by enable()')
check(plugin._toolbar._boxes['rename_files'].text() == 'MyRename', 'user edits are used')
plugin.disable()
w5.close()
w4 = FakeWindow()
plugin.enable(make_api(w4))

# ---- 8. disable / re-enable cleanliness ----
view_menu = w4.menuBar().actions()[0].menu()
plugin.disable()
check([a.text() for a in view_menu.actions()] == ['Show cover art', 'Search', 'Show filter bar'], 'disable removes View menu entry')
check(plugin._toolbar is None, 'disable clears module state')
app.processEvents()
plugin.enable(make_api(w4))
app.processEvents()
plugin.disable()
plugin.disable()  # double disable is safe
check(True, 'double disable does not raise')

print()
print('FAILURES:' if failures else 'ALL PASSED', failures or '')
sys.exit(1 if failures else 0)
