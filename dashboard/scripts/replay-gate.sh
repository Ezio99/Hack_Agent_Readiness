#!/usr/bin/env bash
# Publication gate for the static deployment workflow. Run from dashboard/ . The approval phrase arrives ONLY through the
# APPROVAL_PHRASE environment variable (never interpolated into shell source), and is compared as data.
#   no public/replays/ and no phrase   -> allow=0 (public build without replay data; the default)
#   public/replays/ + exact phrase     -> allow=1 (replay files were explicitly approved)
#   anything else                      -> exit 1
set -euo pipefail
REQUIRED="REPLAY-FILES-APPROVED-FOR-PUBLICATION"
PHRASE="${APPROVAL_PHRASE-}"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"
if [ -d public/replays ]; then
  if [ "$PHRASE" != "$REQUIRED" ]; then
    echo "dashboard/public/replays exists on this ref but the exact approval phrase was not supplied: refusing to build." >&2
    exit 1
  fi
  echo "allow=1" >> "$OUT"
else
  if [ -n "$PHRASE" ]; then
    echo "an approval phrase was supplied but no replay files exist on this ref: refusing (nothing to approve)." >&2
    exit 1
  fi
  echo "allow=0" >> "$OUT"
fi
