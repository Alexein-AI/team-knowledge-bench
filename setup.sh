#!/usr/bin/env bash
# Checks the tools, verifies the Kiln data, and fetches Alexein's public Claude Code plugin at the commit the
# pilot used, with the bench patch applied. Safe to run again.
set -euo pipefail
cd "$(dirname "$0")"

PLUGINS_REPO="https://github.com/Alexein-AI/claude-plugins.git"
PLUGINS_COMMIT="bbcee2442a60046e84a4907217f848035531ab7f"   # bbcee24, plugin alexein 0.2.0
PATCH="patches/alexein-plugin-bench.patch"
VENDOR="vendor/claude-plugins"
PILOT_CLAUDE_CODE="2.1.326"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; exit 1; }; }
need git "https://git-scm.com"
need node "Node 22.18 or newer runs the TypeScript tests directly"
need python3 "Python 3.9 or newer"
need claude "Claude Code: npm install -g @anthropic-ai/claude-code"

node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (a<22 || (a===22 && b<18)) { console.error("Node "+process.versions.node+" is too old: the tests need 22.18+ (TypeScript without a flag)"); process.exit(1) }'
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9 or newer is needed")'
cc="$(claude --version 2>/dev/null | awk '{print $1}')"
if [ "$cc" != "$PILOT_CLAUDE_CODE" ]; then
  echo "note: Claude Code $cc here; the pilot ran $PILOT_CLAUDE_CODE. Results can differ between versions."
fi

echo "verifying data/kiln ..."
python3 load_kiln.py --verify

if [ ! -d "$VENDOR/.git" ]; then
  mkdir -p vendor
  git clone --quiet "$PLUGINS_REPO" "$VENDOR"
fi
git -C "$VENDOR" fetch --quiet origin "$PLUGINS_COMMIT" 2>/dev/null || git -C "$VENDOR" fetch --quiet origin
if git -C "$VENDOR" apply --reverse --check "../../$PATCH" 2>/dev/null; then
  echo "plugin: already at $PLUGINS_COMMIT with the bench patch"
else
  git -C "$VENDOR" checkout --quiet --force --detach "$PLUGINS_COMMIT"
  git -C "$VENDOR" apply "../../$PATCH"
  echo "plugin: $PLUGINS_COMMIT, bench patch applied"
fi
test "$(git -C "$VENDOR" rev-parse HEAD)" = "$PLUGINS_COMMIT" || { echo "plugin checkout is not at $PLUGINS_COMMIT"; exit 1; }

echo
echo "Ready. Next: load the corpus (python3 load_kiln.py --dry-run 2, then --yes), then python3 bench.py run ... (README)."
