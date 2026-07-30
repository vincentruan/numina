# Re-export shim — implementation moved to packages/storage/factory.py
from packages.storage.factory import (
    get_backend_for_type,
    get_local_backend,
    reset_instances,
)
