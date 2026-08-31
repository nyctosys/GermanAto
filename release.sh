#!/usr/bin/env bash
#
# Put the current origin/master live.
#
#   ./release.sh              deploy
#   ./release.sh --dry-run    show what would change, touch nothing
#
# Code only. Database migrations are deliberate and run separately - a release
# that needs one will say so in its commit message, and you run it by hand.
#
# Run as yourself, not with sudo: the clone uses your GitHub credentials, and
# the script escalates only for the steps that write to /opt.

set -euo pipefail

REPO="https://github.com/Al1Tar1q/germanato-app.git"
APP_DIR="/opt/germanato"
SERVICE="germanato"
OWNER="www-data:www-data"          # the user gunicorn runs as - not 'germanato'
PORT=5000

# Never delete these: the virtualenv, the secrets, customer payment proofs, logs.
EXCLUDES=(--exclude='env/' --exclude='.env' --exclude='static/uploads/'
          --exclude='logs/' --exclude='__pycache__/')

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

STAGE=$(mktemp -d /tmp/germanato-release-XXXXXX)
trap 'rm -rf "$STAGE"' EXIT

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\n\033[1;31mFAILED:\033[0m %s\n' "$1" >&2; exit 1; }

say "Fetching origin/master"
git clone --quiet --depth 1 "$REPO" "$STAGE/repo" || die "clone failed - check your GitHub credentials"
chmod -R a+rX "$STAGE/repo"
COMMIT=$(git -C "$STAGE/repo" log --oneline -1)
echo "    $COMMIT"

[[ -d "$STAGE/repo/backend" ]] || die "clone has no backend/ - wrong repository?"

say "Changes this release would make"
# Captured rather than piped: under `set -o pipefail` a failing rsync would
# otherwise be swallowed by the grep fallback and reported as "up to date".
CHANGES=$(sudo rsync -a --delete --dry-run --itemize-changes "${EXCLUDES[@]}" \
    "$STAGE/repo/backend/" "$APP_DIR/backend/") || die "could not read $APP_DIR - wrong path, or no permission"
echo "$CHANGES" | grep -E '^(\*deleting|[<>]f)' | sed 's/^/    /' \
  || echo "    (nothing - already up to date)"

if $DRY_RUN; then
    say "Dry run - nothing was written."
    exit 0
fi

say "Backing up current code"
BACKUP=~/germanato-code-$(date +%F-%H%M).tgz
sudo tar czf "$BACKUP" -C "$APP_DIR" \
    --exclude='backend/env' --exclude='backend/logs' \
    --exclude='backend/static/uploads' backend
echo "    $BACKUP"

say "Deploying"
sudo rsync -a --delete --chown="$OWNER" "${EXCLUDES[@]}" \
    "$STAGE/repo/backend/" "$APP_DIR/backend/"
sudo cp "$STAGE"/repo/*.py "$APP_DIR/"
sudo chown "$OWNER" "$APP_DIR"/*.py

say "Restarting $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || {
    sudo journalctl -u "$SERVICE" -n 30 --no-pager
    die "service did not come back - restore with: sudo tar xzf $BACKUP -C $APP_DIR"
}

say "Checking"
fail=0
for path in /inventory.html /static/js/app-shell.js /api/inventory; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT$path")
    case "$path:$code" in
        /api/*:401|/api/*:200|*:200) printf '    %-28s %s\n' "$path" "$code" ;;
        *) printf '    %-28s %s  <-- unexpected\n' "$path" "$code"; fail=1 ;;
    esac
done
[[ $fail -eq 0 ]] || die "smoke checks failed - restore with: sudo tar xzf $BACKUP -C $APP_DIR"

say "Live: $COMMIT"
echo "    Rollback if needed: sudo tar xzf $BACKUP -C $APP_DIR && sudo systemctl restart $SERVICE"
