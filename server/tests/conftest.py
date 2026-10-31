"""Top-level test conftest — loaded at pytest startup, before any test module
is collected/imported.

With testpaths=["tests"], pytest only loads *this* conftest before collection;
subdirectory conftests (tests/backend/conftest.py) load lazily when their
directory is collected. Test modules in earlier directories (e.g. tests/agent)
import packages.core.settings during collection, creating the settings
singleton BEFORE tests/backend/conftest.py has a chance to set
AI_ENCRYPTION_KEY — leaving the singleton without the key and breaking every
Fernet encrypt/decrypt-dependent backend test (web-search providers, AI
provider config, circuit breaker metadata).

Setting it here guarantees the env var exists before the first settings import,
regardless of collection order. The backend conftest sets the same value
explicitly (kept for standalone `pytest tests/backend` runs).
"""

import os

os.environ.setdefault("AI_ENCRYPTION_KEY", "TWkvLCaoHF_ZlwIUzytBOveIw5wmZj4ggVjWMgJr9BM=")
