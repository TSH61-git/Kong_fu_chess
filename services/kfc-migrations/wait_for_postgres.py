# Standalone readiness wait for the migrations runner — deliberately not
# importing server.observability.connectivity so this image has no
# dependency on the application source tree, only its own requirements.txt.
from __future__ import annotations

import os
import sys
import time

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
ATTEMPTS = int(os.environ.get("MIGRATIONS_WAIT_ATTEMPTS", "30"))
DELAY_SECONDS = float(os.environ.get("MIGRATIONS_WAIT_DELAY_SECONDS", "2.0"))


def main() -> None:
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.close()
            print(f"Postgres/Citus reachable (attempt {attempt})")
            return
        except Exception as exc:  # noqa: BLE001 - broad on purpose while retrying
            last_error = exc
            print(f"Postgres not yet reachable (attempt {attempt}/{ATTEMPTS}): {exc}")
            time.sleep(DELAY_SECONDS)
    print(f"Postgres never became reachable at {DATABASE_URL}: {last_error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
