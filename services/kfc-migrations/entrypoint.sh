#!/usr/bin/env sh
# kfc-migrations entrypoint: wait for the Citus coordinator to accept
# connections, then apply every Alembic migration (which itself issues
# the create_distributed_table() DDL — see migrations/versions/0001_*.py).
# Worker registration (citus_add_node) is a separate, earlier step —
# deploy/citus/register-workers.sh, run by the citus-init compose service —
# because create_distributed_table requires the coordinator to already
# know about its workers.
set -eu

echo "kfc-migrations: waiting for ${DATABASE_URL:?DATABASE_URL is required}"
python /app/wait_for_postgres.py

echo "kfc-migrations: running alembic upgrade head"
alembic -c /app/alembic.ini upgrade head

echo "kfc-migrations: done"
