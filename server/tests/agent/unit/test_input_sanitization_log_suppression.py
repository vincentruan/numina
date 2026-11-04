"""Tests for input sanitization log suppression (U5).

Verifies the logging filter downgrades "rfind failed" WARNINGs to DEBUG
without affecting other log messages from the same logger.
"""

import logging

from apps.agent.app.main import _SanitizationWarningFilter


def test_rfind_warning_downgraded_to_debug():
    """WARNING with 'rfind failed' → downgraded to DEBUG level."""
    filt = _SanitizationWarningFilter()
    record = logging.LogRecord(
        name="deerflow.agents.middlewares.input_sanitization_middleware",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="rfind failed with original_user_content set",
        args=(),
        exc_info=None,
    )

    assert record.levelno == logging.WARNING
    result = filt.filter(record)
    assert result is True  # not suppressed
    assert record.levelno == logging.DEBUG  # downgraded


def test_other_warning_not_affected():
    """Other WARNING messages from the same logger stay at WARNING level."""
    filt = _SanitizationWarningFilter()
    record = logging.LogRecord(
        name="deerflow.agents.middlewares.input_sanitization_middleware",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="some other warning message",
        args=(),
        exc_info=None,
    )

    result = filt.filter(record)
    assert result is True
    assert record.levelno == logging.WARNING  # unchanged


def test_info_messages_pass_through():
    """INFO-level messages are not affected by the filter."""
    filt = _SanitizationWarningFilter()
    record = logging.LogRecord(
        name="deerflow.agents.middlewares.input_sanitization_middleware",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="rfind failed with original_user_content set",
        args=(),
        exc_info=None,
    )

    result = filt.filter(record)
    assert result is True
    assert record.levelno == logging.INFO  # INFO not downgraded
