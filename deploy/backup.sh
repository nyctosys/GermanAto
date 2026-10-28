#!/usr/bin/env bash
# Nightly backup: the database and the uploaded proof files into one dated folder, then old ones pruned.
# Usage: deploy/backup.sh [backup-dir]   (default ./backups; keeps the newest $KEEP, default 14)
# Cron:  0 2 * * *  cd /path/to/germanato && deploy/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
DIR="${1:-backups}"; KEEP="${KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"; OUT="$DIR/$STAMP"
mkdir -p "$OUT"
# Under Docker the tools run inside the containers; BACKUP_LOCAL=1 uses a Postgres reachable from this shell instead.
if [ "${BACKUP_LOCAL:-0}" = 1 ]; then
  pg_dump --format=custom --no-owner "$DATABASE_URL_PLAIN" > "$OUT/db.dump"
  [ -d "${STORAGE_DIR:-}" ] && tar -C "$STORAGE_DIR" -czf "$OUT/files.tar.gz" . || tar -czf "$OUT/files.tar.gz" -T /dev/null
else
  docker compose exec -T db pg_dump -U postgres --format=custom --no-owner germanato > "$OUT/db.dump"
  docker compose exec -T api tar -C /data/files -czf - . > "$OUT/files.tar.gz"
fi
[ -s "$OUT/db.dump" ] || { echo "backup failed: empty dump" >&2; rm -rf "$OUT"; exit 1; }
( cd "$OUT" && shasum -a 256 db.dump files.tar.gz > SHA256SUMS )
ls -1d "$DIR"/*/ | sort | awk -v k="$KEEP" '{a[NR]=$0} END{for(i=1;i<=NR-k;i++)print a[i]}' | while read -r old; do rm -rf "$old"; done
echo "backup ok: $OUT"
