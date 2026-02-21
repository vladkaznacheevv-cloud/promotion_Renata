import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def _enabled() -> bool:
    return (os.getenv("GETCOURSE_CRON_ENABLED", "false").strip().lower() == "true")


def _interval_seconds() -> int:
    raw = (os.getenv("GETCOURSE_CRON_INTERVAL_MINUTES") or "").strip()
    try:
        minutes = int(raw) if raw else 360
    except Exception:
        minutes = 360
    return max(minutes, 1) * 60


def main() -> int:
    interval = _interval_seconds()
    if not _enabled():
        print("[getcourse_cron] disabled; exiting")
        return 0

    print(f"[getcourse_cron] started; interval_seconds={interval}")
    while True:
        started = datetime.now(tz=timezone.utc).isoformat()
        print(f"[getcourse_cron] tick started_at={started}")
        result = subprocess.run(
            [sys.executable, "legacy/getcourse/sync_getcourse.py"],
            check=False,
            text=True,
        )
        print(f"[getcourse_cron] tick finished returncode={result.returncode}")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
