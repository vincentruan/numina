# Re-export from packages — model now lives in packages/db/models/family.py
from packages.db.models.family import Family, generate_invite_code

__all__ = ["Family", "generate_invite_code"]
