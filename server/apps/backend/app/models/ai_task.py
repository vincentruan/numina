# Re-export from packages — model now lives in packages/db/models/ai_task.py
from packages.db.models.ai_task import AITask

__all__ = ["AITask"]
