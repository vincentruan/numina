# Re-export shim — implementation moved to packages/db/models/asset.py
from packages.db.models.asset import Asset, asset_tags

__all__ = ["Asset", "asset_tags"]
