#!/usr/bin/env sh
# Daily backup: PostgreSQL dump + uploaded files. Cron: 30 3 * * * cd /opt/sazeh && ./deploy/backup.sh
set -eu
cd "$(dirname "$0")/.."
. ./.env.production
TS=$(date +%Y%m%d-%H%M)
mkdir -p backups
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-structuralaiaagent}" -Fc > "backups/db-$TS.dump"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend \
  tar -czf - -C /data files > "backups/files-$TS.tgz"
find backups -type f -mtime +14 -delete
echo "backup ok: $TS"
