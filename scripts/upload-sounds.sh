#!/usr/bin/env bash
# Uploads the sounds of the Muslim Reminder app to the CDN
# (https://cdn.muslim-reminder.com/v1/sounds/…), where the integration plays them from.
#
#   scripts/upload-sounds.sh <path to a clone of muslimreminder/app>
#
# Needs wrangler, signed in to the Cloudflare account of the
# muslimreminder-content bucket. The list must match SALAWAT_SOUNDS and
# ADHAN_SOUNDS of custom_components/muslim_reminder/const.py.
set -euo pipefail

APP=${1:?"path to a clone of muslimreminder/app"}
RAW="$APP/android/app/src/main/res/raw"
BUCKET=muslimreminder-content
PREFIX=v1/sounds

put() {
    local source=$1 key=$2
    echo "→ $PREFIX/$key"
    npx --yes wrangler r2 object put "$BUCKET/$PREFIX/$key" --remote --file "$source" \
        --content-type audio/mpeg --cache-control "public, max-age=604800"
}

for n in 1 2 3 4 5 6 7; do
    put "$RAW/reminder_$n.mp3" "salawat/reminder_$n.mp3"
done
# Not 3 (Karl Jenkins, a commercial recording) nor 4 (iOS only, no full version).
for n in 1 2 5 6 7 8 9 10 11; do
    put "$RAW/adhan_$n.mp3" "adhan/adhan_$n.mp3"
    if [ -f "$RAW/adhan_${n}_full.mp3" ] && [ "$n" -le 9 ]; then
        put "$RAW/adhan_${n}_full.mp3" "adhan/adhan_${n}_full.mp3"
    fi
done
