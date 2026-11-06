#!/usr/bin/env bash
# Install (or reinstall) this plugin into Picard 3 so it loads straight from this folder.
# Edits made here take effect the next time Picard starts.
#
#   ./install.sh                 install / reinstall
#   ./install.sh --remove        uninstall
#   PICARD_CLI=/path/to/picard-cli ./install.sh     use a specific picard-cli
#
# Close Picard first, then start it again afterwards.

set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cli=${PICARD_CLI:-picard-cli}
plugin_id=$(basename "$here")

if ! command -v "$cli" >/dev/null 2>&1; then
    echo "error: '$cli' not found. Put picard-cli on your PATH or set PICARD_CLI=/path/to/picard-cli" >&2
    exit 1
fi

# --yes is a global option, so it goes before the subcommand.
if [[ "${1:-}" == "--remove" ]]; then
    "$cli" --yes plugins remove "$plugin_id"
    echo "Removed. Your aliases file (in Picard's config folder) was left alone."
    exit 0
fi

# --no-git: load from this folder as-is, even though it is a git checkout.
"$cli" --yes plugins install "$here" --no-git --reinstall

echo
echo "Done. Start Picard, then tick View > Quick settings."
echo "Your short labels live in: ~/.config/MusicBrainz/Picard/quick menu toolbar aliases.txt"
echo "(created from aliases.example.txt the first time the plugin runs)."
