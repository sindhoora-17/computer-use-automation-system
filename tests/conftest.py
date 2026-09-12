from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from urllib.error import URLError
from urllib.request import urlopen

import pytest


TARGET_URL = (
    "http://127.0.0.1:5000"
)


def _target_app_is_ready() -> bool:
    """
    Return True only when the process listening on port
    5000 is actually the Meridian test application.

    A plain TCP-port check is not enough on macOS because
    AirPlay Receiver may also listen on port 5000.
    """

    try:
        with urlopen(
            f"{TARGET_URL}/content/search",
            timeout=0.5,
        ) as response:
            body = (
                response.read()
                .decode(
                    "utf-8",
                    errors="ignore",
                )
            )

        return (
            "Member Search" in body
        )

    except (
        URLError,
        TimeoutError,
        OSError,
    ):
        return False


def _wait_for_target_app(
    process: subprocess.Popen[bytes],
    timeout_s: float = 10.0,
) -> None:
    deadline = (
        time.time()
        + timeout_s
    )

    while time.time() < deadline:
        if _target_app_is_ready():
            return

        if process.poll() is not None:
            raise RuntimeError(
                "Target application exited before "
                "becoming ready. Port 5000 may "
                "already be in use."
            )

        time.sleep(
            0.1
        )

    raise RuntimeError(
        "Target application did not become ready "
        "within the expected time. Port 5000 may "
        "already be occupied by another process."
    )


@pytest.fixture(
    scope="session",
    autouse=True,
)
def target_app_server() -> Iterator[None]:
    if _target_app_is_ready():
        yield
        return

    env = os.environ.copy()

    env[
        "TARGET_APP_BYPASS_AUTH"
    ] = "true"

    env[
        "TARGET_APP_USERNAME"
    ] = "operator"

    env[
        "TARGET_APP_PASSWORD"
    ] = "demo123"

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "target_app.server",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_target_app(
            process
        )

        yield

    finally:
        if process.poll() is None:
            process.terminate()

            try:
                process.wait(
                    timeout=5
                )

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()