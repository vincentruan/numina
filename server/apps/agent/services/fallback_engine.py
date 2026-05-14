"""FallbackEngine — retained for import compatibility but no longer used as a dispatch path.

DeerFlow is the mandatory execution path. If DeerFlow fails, the orchestrator
returns a structured error response to the caller rather than silently degrading
to direct LLM calls.

This module is kept to avoid breaking any test fixtures that import it directly.
"""
