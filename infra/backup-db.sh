#!/usr/bin/env bash
# Nightly pg_dump of the outreach database.
#
# Neon did this for you. A docker volume does not: Postgres is the source of
# truth (DEPLOYMENT.md section 8) - the schedule, targets, threads and the
# encrypted Google refresh tokens all live there. Losing the volume without a
# dump means every user reconnects Google and the history is gone.
#
# Install:
#   chmod +x infra/backup-db.sh
#   crontab -e
#     30 2 * * * /home/admin1/projects/email/infra/backup-db.sh >> /home/admin1/backups/email/cron.log 2>&1
#
# MASTER_KEY IS NOT IN THESE DUMPS, and a restore is useless without the same
# one - the refresh tokens are encrypted under it. Back it up separately;
# ~/env-backups on this box is where the other stacks keep theirs.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-/home/admin1/projects/email/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-/home/admin1/projects/email/.env}"
DEST="${BACKUP_DIR:-/home/admin1/backups/email}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/outreach-$STAMP.dump"

mkdir -p "$DEST"

# -T because cron has no TTY. Custom format so pg_restore can do selective
# restores and parallel loads.
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
    pg_dump -U outreach -d outreach --format=custom > "$OUT"

# A zero-byte file means pg_dump failed after the shell already created the
# redirect target. Bail before the rotation below deletes a good backup to
# make room for a broken one.
if [ ! -s "$OUT" ]; then
    echo "FAILED: $OUT is empty, not rotating" >&2
    rm -f "$OUT"
    exit 1
fi

find "$DEST" -name 'outreach-*.dump' -mtime "+$KEEP_DAYS" -delete

echo "ok $STAMP $(du -h "$OUT" | cut -f1)"

# Restore, for when you need it (this DROPS and recreates objects):
#   docker compose -f "$COMPOSE_FILE" exec -T postgres \
#       pg_restore -U outreach -d outreach --clean --if-exists < outreach-YYYYMMDD-HHMMSS.dump
