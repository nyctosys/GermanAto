# Workshop server runbook

The workshop PC runs the database, the API and the web app in Docker. Every phone, tablet and PC in the workshop opens `http://<the PC's address>:3000`.

## First install
1. Install Docker (Docker Desktop, or Docker Engine on Linux) and set it to start with the PC.
2. Copy the project to the PC. Copy `workshop.env.example` to `.env` and set `DB_PASSWORD` to a long random password. Keep `.env` private; it is never committed.
3. Start it:
   ```bash
   docker compose up -d --build
   ```
   The API upgrades the database by itself on every start.
4. Create the branch and the first admin (once):
   ```bash
   docker compose exec -e ADMIN_PASSWORD='choose-a-password' api python -m app.seed --branch-name "GermanATO Lahore" --admin-username admin
   ```
5. Give the PC a fixed address on the router, so devices always find it. Attendance terminals push to `http://<PC address>:8000/iclock/cdata`.

## Everyday
| Task | Command |
|---|---|
| Is it running? | `docker compose ps` and open `http://<PC>:3000/api/health` |
| Logs | `docker compose logs -f api` |
| Update to a new version | `git pull && docker compose up -d --build` |
| Stop / start | `docker compose stop` / `docker compose start` |

## Backups
`deploy/backup.sh` saves the database and every uploaded proof file into `backups/<date-time>/` with checksums, and keeps the newest 14 (`KEEP=30` for more).

Schedule it nightly (Linux/macOS `crontab -e`):
```
0 2 * * *  cd /path/to/germanato && deploy/backup.sh >> backups/backup.log 2>&1
```
**Copy the `backups` folder off the PC** (a USB drive or cloud storage) at least weekly. A backup on the same disk does not survive a dead disk.

### Restore
This **replaces everything** with the chosen backup.
```bash
deploy/restore.sh backups/20261028-020000
```
It checks the checksums first (a damaged backup is refused), asks you to type `RESTORE`, stops the app, restores, and starts it again. Test a restore on a spare PC once, so the first time is not an emergency.

## Power cuts
Use a UPS. After a cut, `docker compose up -d` brings everything back; PostgreSQL recovers its own log. If the app misbehaves afterwards, restore last night's backup.

## Cloud sync
Leave `SYNC_CLOUD_URL` and `SYNC_TOKEN` empty until the cloud server exists. Then fill them in and run `docker compose --profile sync up -d`. See section 25 of the system guide.

## Settings reference
`workshop.env.example` lists every setting with a comment. WhatsApp details go there too (system guide, section 24).
