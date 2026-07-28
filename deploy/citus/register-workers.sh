#!/usr/bin/env bash
# Registers both Citus workers with the coordinator (Server_Design.md §4:
# "Citus (Coordinator + 2 Workers) with an initialization script to
# register workers"). Runs once, in the `citus-init` compose service,
# after the coordinator and both workers report healthy — and before
# kfc-migrations, since create_distributed_table requires the coordinator
# to already know its workers.
#
# Idempotent: citus_add_node is safe to call again (Citus raises a
# duplicate-node notice, not an error, on repeat `docker compose up`).
set -euo pipefail

: "${COORDINATOR_HOST:?COORDINATOR_HOST is required}"
: "${COORDINATOR_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${PGPASSWORD:?PGPASSWORD (POSTGRES_PASSWORD) is required}"
: "${WORKER_1_HOST:?WORKER_1_HOST is required}"
: "${WORKER_2_HOST:?WORKER_2_HOST is required}"
: "${WORKER_PORT:=5432}"

export PGPASSWORD

psql_coordinator() {
    psql -v ON_ERROR_STOP=1 -h "$COORDINATOR_HOST" -p "$COORDINATOR_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}

echo "register-workers: waiting for coordinator at ${COORDINATOR_HOST}:${COORDINATOR_PORT}"
until psql_coordinator -c "SELECT 1" > /dev/null 2>&1; do
    sleep 2
done

for worker_host in "$WORKER_1_HOST" "$WORKER_2_HOST"; do
    echo "register-workers: waiting for worker at ${worker_host}:${WORKER_PORT}"
    until psql -v ON_ERROR_STOP=1 -h "$worker_host" -p "$WORKER_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" > /dev/null 2>&1; do
        sleep 2
    done
done

echo "register-workers: adding ${WORKER_1_HOST}:${WORKER_PORT} and ${WORKER_2_HOST}:${WORKER_PORT} to the coordinator"
psql_coordinator <<SQL
SELECT citus_add_node('${WORKER_1_HOST}', ${WORKER_PORT})
WHERE NOT EXISTS (
    SELECT 1 FROM pg_dist_node WHERE nodename = '${WORKER_1_HOST}' AND nodeport = ${WORKER_PORT}
);
SELECT citus_add_node('${WORKER_2_HOST}', ${WORKER_PORT})
WHERE NOT EXISTS (
    SELECT 1 FROM pg_dist_node WHERE nodename = '${WORKER_2_HOST}' AND nodeport = ${WORKER_PORT}
);
SQL

echo "register-workers: current cluster membership:"
psql_coordinator -c "SELECT nodename, nodeport, isactive FROM pg_dist_node;"
echo "register-workers: done"
