from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
import time

from dotenv import load_dotenv

from .automation import run_automation, transcript_provider_label
from .database import init_db


LOGGER = logging.getLogger("meetwise.worker")
STOP_EVENT = threading.Event()


def _request_stop(signum: int, frame: object) -> None:
    del signum, frame
    STOP_EVENT.set()


def run_once() -> bool:
    result = run_automation()
    LOGGER.info(
        "automation detected=%s processed=%s waiting=%s no_ai=%s failed=%s",
        result.detected,
        result.processed,
        result.waiting_for_transcript,
        result.completed_without_ai,
        result.failed,
    )
    return not result.failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Meetwise automatic meeting processor")
    parser.add_argument(
        "--once", action="store_true", help="Run one automation cycle and exit"
    )
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_db()
    LOGGER.info("worker started transcript_provider=%s", transcript_provider_label())

    if args.once:
        return 0 if run_once() else 1

    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)
    poll_seconds = max(int(os.getenv("AUTOMATION_POLL_SECONDS", "30")), 10)
    while not STOP_EVENT.is_set():
        try:
            run_once()
        except Exception:
            LOGGER.exception("automation cycle failed")
        STOP_EVENT.wait(poll_seconds)
    LOGGER.info("worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
