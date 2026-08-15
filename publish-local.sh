#!/bin/bash
# Full scrape from this machine (residential IP — Eventbrite/Rich Mix work here,
# they 403/405 GitHub Actions) and publish output/ to the gh-pages branch.
# Installed as a launchd job: see launchd/com.b1rdmania.london-culture.plist
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Python/3.12/bin:$PATH"
git pull -q --rebase origin master || true
python3 scrape.py "$@"
WT=$(mktemp -d)
git worktree add -q "$WT" gh-pages 2>/dev/null || { git fetch -q origin gh-pages; git worktree add -q "$WT" gh-pages; }
cp output/index.html output/events.json output/health.json "$WT"/
( cd "$WT" && git add -A && git -c user.name=b1rdmania -c user.email=102524336+b1rdmania@users.noreply.github.com \
    commit -q -m "local scrape $(date +%F\ %H:%M)" && git push -q origin gh-pages ) || echo "nothing to publish"
git worktree remove -f "$WT"
