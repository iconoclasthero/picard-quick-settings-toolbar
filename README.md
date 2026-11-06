# Picard Quick Settings Toolbar

A plugin for [MusicBrainz Picard](https://picard.musicbrainz.org/) 3.x that shows the
**Options → Quick settings** checkboxes as an optional toolbar, so the settings you
flip often are one click away instead of two menus deep.

- One checkbox per entry in your quick settings list.
- Short labels (aliases) on the toolbar; the full option title appears on hover.
- Toggle the toolbar from **View → Quick settings**. Position and visibility are remembered.
- Right-click the toolbar for **Configure quick settings…** (plus Qt's usual toolbar list).
- Stays in sync with the Options → Quick settings menu, and updates when you change
  the list in **Options → Interface → Quick settings**.
- Profile switching is wired up to refresh the toolbar, but that path is untested.

Written for Picard 3.0.x (plugin API `3.0`). Checked headless against the Picard source; see
*Development / tests* for what that does and doesn't cover.

## Install

Close Picard, then from a clone of this repo:

```bash
./install.sh
```

It runs `picard-cli --yes plugins install <this folder> --no-git --reinstall`, which makes
Picard load the plugin **directly from this folder**. Edit files here, restart Picard, done.
`PICARD_CLI=/path/to/picard-cli ./install.sh` if `picard-cli` isn't on your `PATH`.
`./install.sh --remove` uninstalls.

Notes:

- The `--yes` flag must come **before** `plugins` (it is a global option of `picard-cli`).
- `--no-git` is what makes it load in place. Without it Picard treats the folder as a git
  plugin and manages its own copy. Picard prints a couple of warnings about git features
  being disabled; that is expected.
- Keep the clone somewhere permanent. If you move or delete the folder, Picard loses the plugin.

Then start Picard and tick **View → Quick settings** if the toolbar isn't showing.

## Short labels (aliases)

Aliases live in **`quick menu toolbar aliases.txt`** in Picard's config folder
(Linux: `~/.config/MusicBrainz/Picard/`). They are *not* stored in this repo, so plugin
updates and reinstalls never overwrite them.

The first time the plugin runs it copies [`aliases.example.txt`](aliases.example.txt) there.
Edit that copy:

```
# option_name = Short label
rename_files = Rename
save_images_to_files = Images saved separately
```

- The toolbar shows the short label; the tooltip shows the full option title.
- Settings without an alias use their full title.
- Toolbar order follows the order of lines in the file; unlisted settings come after, A–Z.
- When you add a setting to the quick list, the plugin appends a commented line for it
  (`# option_name = Full title`) to your file. Remove the `# ` and edit the label.
- After editing, restart Picard, or disable and re-enable the plugin.

## How it works (short version)

Picard 3's plugin API has no toolbar hook, so the plugin reaches the main window through
`api.tagger.window` and adds a normal Qt toolbar. That means it depends on a few Picard
internals (see `CLAUDE.md`), so check it still works after upgrading Picard.

Picard restores its window layout *before* plugins load, so the plugin re-applies the saved
layout once its toolbar exists. The toolbar therefore appears a moment after the main window.

## Development / tests

`tests/test_plugin.py` builds the toolbar against a stand-in main window, using Picard's real
config code, with no display needed (Qt `offscreen`). It covers labels, tooltips, ordering,
two-way sync, list changes, the right-click menu, saved layout, and clean enable/disable.

```bash
pip install PyQt6 -r /path/to/picard/requirements.txt
git clone https://github.com/metabrainz/picard /path/to/picard
PICARD_SRC=/path/to/picard python3 tests/test_plugin.py
```

It ends with `ALL PASSED` or a list of failures. It does not start the real Picard window,
so a final manual check in Picard is still worthwhile after Picard upgrades.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
