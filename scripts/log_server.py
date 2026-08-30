import logging
import os
"""Legacy log_server helpers (deprecated).

The log viewing and streaming functionality has been moved into the Flask
application (app/views.py). This module is retained only for backward
compatibility. Importing and calling its helpers will log a deprecation
message and return no-op behaviours.
"""

import logging
from typing import Generator, Optional

logger = logging.getLogger(__name__)


def get_logs_html() -> str:
    """Return a short HTML notice indicating deprecation.

    The full log viewer is now served by the Flask app at `/log` and
    `/logs/stream`.
    """
    return (
        "<html><body><h2>Log viewer moved to Flask application</h2>"
        "<p>Use <a href=\"/log\">/log</a> to view logs.</p></body></html>"
    )


def stream_log_generator(log_path: str, last_n: int = 50, poll_interval: float = 0.5) -> Generator[str, None, None]:
    """Deprecated stream generator.

    Yield a single SSE message informing clients that the function is
    deprecated. The Flask app provides a robust implementation.
    """
    logger.info('stream_log_generator deprecated; use /logs/stream in Flask')
    yield 'data: [log streaming disabled: use /log]\n\n'


def start_log_server(*args, **kwargs) -> Optional[object]:
    logger.info('start_log_server deprecated: log server is integrated into Flask')
    return None


def stop_log_server(server: object) -> None:
    logger.info('stop_log_server called on deprecated module')
    return None
