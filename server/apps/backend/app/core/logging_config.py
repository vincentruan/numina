# Re-export shim — implementation moved to packages/core/logging.py
from packages.core.logging import (
    archive_old_logs,
    cleanup_old_logs,
    get_logger,
    setup_logging,
)
