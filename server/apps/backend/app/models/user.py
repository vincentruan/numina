# Re-export from packages — model now lives in packages/db/models/user.py
from packages.db.models.user import User

__all__ = ["User"]
