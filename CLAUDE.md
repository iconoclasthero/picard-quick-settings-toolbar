# Notes for AI assistants working in this repo

## About the owner
The owner does not read or write Python and cannot review code. Don't ask them to
review Python or explain code in Python terms. Explain what a change *does* and prove
it with the tests. Ask questions in plain language; make sensible decisions yourself.

## What this is
A Picard 3.x plugin (`__init__.py` + `MANIFEST.toml`) that shows the Quick settings
menu entries as a toolbar of checkboxes. See `README.md` for behaviour.

## Always do before finishing a change
1. Run the tests: `PICARD_SRC=/path/to/picard-checkout python3 tests/test_plugin.py`
   (needs `pip install --break-system-packages PyQt6 -r <picard>/requirements.txt`;
   shallow-clone `https://github.com/metabrainz/picard` for the source). All checks must pass.
2. Add a check to `tests/test_plugin.py` for any new behaviour or bug fixed.
3. If install steps changed, test `install.sh` in a sandbox with `PICARD_CONFIG_DIR`,
   `PICARD_PLUGIN_DIR` and `HOME` pointed at temp dirs and `QT_QPA_PLATFORM=offscreen`.
4. Keep `README.md` in sync.

## Picard internals the plugin depends on (verify after Picard upgrades)
- `api.tagger.window`: the main window; attributes used: `search_toolbar`, `menuBar()`,
  `createPopupMenu()`, `show_options('interface_quick_menu')`, and the **private**
  method `_toggle_quick_setting(setting_id)`.
- Config: `config.setting['quick_menu_items']`, `config.setting.setting_changed` and
  `config.profiles.setting_changed` signals, `config.persist['window_state']`.
- `picard.options`: `Option.exists`, `get_option_title`; `picard.const.appdirs.config_folder`.
- Window state is restored *before* plugins load, so `_restore_saved_layout` re-applies it
  (looks for the toolbar's object name, UTF-16-BE encoded, inside the saved bytes).

## Gotchas
- `picard-cli --yes` is a **global** option and must come before `plugins`.
- The user's alias file is `~/.config/MusicBrainz/Picard/quick menu toolbar aliases.txt`
  (via `config_folder()`), never inside the plugin folder. The plugin copies
  `aliases.example.txt` there on first run and never overwrites it.
- Picard 3 plugin folder is `<AppData>/MusicBrainz/Picard/plugins3` (v2 used `.config/.../plugins`).
  Local plugins installed with `--no-git` load from wherever the clone lives.
- Tests use a fake main window, not the real one; they cannot catch Picard-side layout changes.

## Style
Follow Picard's conventions: single quotes, 120-column lines, imports at top with one name per
line in parentheses, no inline imports. Translatable UI strings go through `picard.i18n.gettext`.
