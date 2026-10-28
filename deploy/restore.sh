#!/usr/bin/env bash
# Restore a backup made by backup.sh. This REPLACES the current database and files.
# Usage: deploy/restore.sh backups/20261028-020000
set -euo pipefail
SRC="${1:?usage: restore.sh <backup folder>}"
( cd "$SRC" && shasum -a 256 -c SHA256SUMS )   # refuse a damaged backup before touching anything
read -r -p "This replaces ALL current data with $SRC. Type RESTORE to continue: " ok
[ "$ok" = RESTORE ] || { echo "cancelled"; exit 1; }
if [ "${BACKUP_LOCAL:-0}" = 1 ]; then
  pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL_PLAIN" "$SRC/db.dump"
  mkdir -p "$STORAGE_DIR" && tar -C "$STORAGE_DIR" -xzf "$SRC/files.tar.gz"
else
  docker compose stop api web sync
  docker compose exec -T db pg_restore -U postgres --clean --if-exists --no-owner -d germanato < "$SRC/db.dump"
  docker compose run --rm -T --entrypoint sh api -c "tar -C /data/files -xzf -" < "$SRC/files.tar.gz"
  docker compose start api web
fi
echo "restore ok from $SRC"
