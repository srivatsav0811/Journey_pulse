#!/usr/bin/env bash
# Build the browser demo (site/) and publish it to the gh-pages branch of `origin`.
# Needs the datasets you want to include under data/raw/ (synthetic is always included).
# Only aggregated transition counts are published, never raw events.
set -euo pipefail
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" scripts/build_static_site.py
remote=$(git remote get-url origin)
name=$(git config user.name || echo "JourneyPulse")
email=$(git config user.email || echo "noreply@example.com")
tmp=$(mktemp -d)
cp -R site/. "$tmp"/
(
  cd "$tmp"
  git init -q -b gh-pages
  git add -A
  git -c user.name="$name" -c user.email="$email" commit -q -m "Deploy browser demo"
  git -c credential.helper= -c credential.helper="!gh auth git-credential" push -q -f "$remote" gh-pages
)
rm -rf "$tmp"
echo "Pushed to gh-pages. In GitHub: Settings -> Pages -> Deploy from branch gh-pages (root)."
