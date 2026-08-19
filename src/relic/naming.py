import socket
from datetime import datetime


def default_archive_name(now: datetime | None = None) -> str:
    """Build a default archive name: "<hostname>-<date>-<seconds since midnight>".

    The seconds-since-midnight suffix keeps names unique if you run `relic
    create` more than once on the same day.
    """
    now = now or datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_since_midnight = int((now - midnight).total_seconds())
    hostname = socket.gethostname().split(".")[0]
    return f"{hostname}-{now.date().isoformat()}-{seconds_since_midnight}"
