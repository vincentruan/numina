"""Key prefix constants for the unified Cache.

Callers construct keys as ``f"{RATE_LIMIT}:{scope}:{key}"``.
"""

RATE_LIMIT = "ratelimit"
CAPTCHA = "captcha"
FAM_SETTING = "famsetting"
AGENT_REG = "agentreg"
FX_RATE = "fxrate"
SEC_EVENT = "secevent"
SEC_SUSPECT = "secsuspect"
SEC_COUNTER = "seccounter"
