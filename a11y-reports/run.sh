#!/usr/bin/env bash
# Lighthouse a11y runner. Usage: ./run.sh <before|after> [pages...]
set -euo pipefail

cd "$(dirname "$0")/.."
export CHROME_PATH="$HOME/.cache/puppeteer/chrome/linux-148.0.7778.97/chrome-linux64/chrome"
TAG="${1:?usage: run.sh <before|after> [pages...]}"
shift || true
PAGES=("$@")
if [ ${#PAGES[@]} -eq 0 ]; then
  PAGES=("/" "/events" "/results" "/clubs" "/gymnasts" "/login")
fi

for p in "${PAGES[@]}"; do
  slug="$(echo "$p" | tr '/' '-' | sed 's/^-//;s/-$//')"
  [ -z "$slug" ] && slug=home
  out="a11y-reports/${slug}-${TAG}.json"
  echo "==> $p -> $out"
  npx --yes lighthouse "http://localhost:5173${p}" \
    --only-categories=accessibility \
    --output=json --output-path="$out" \
    --quiet 2>/dev/null || true
  # print the a11y score
  node -e 'const r=require("./'$out'"); const s=r.categories?.accessibility?.score; const f=r.audits; const failures=Object.entries(f).filter(([k,v])=>v.score!==null&&v.score<1&&["failed"].includes(v.scoreDisplayMode)).map(([k])=>k); console.log("  a11y score:", s===null?"n/a":Math.round(s*100)); if(failures.length){console.log("  failed audits:", failures.join(", "))}'
done
