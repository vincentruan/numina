"""PIN emoji constants — single source of truth for child PIN validation."""

ALLOWED_EMOJIS: frozenset[str] = frozenset({
    "🐱", "🐶", "🐸", "🦊", "🐼", "🐨",
    "🦁", "🐯", "🌟", "🌈", "🍎", "🎈",
})

# Ordered list for consistent frontend display
ALLOWED_EMOJIS_ORDERED: list[str] = [
    "🐱", "🐶", "🐸", "🦊", "🐼", "🐨",
    "🦁", "🐯", "🌟", "🌈", "🍎", "🎈",
]

# Numeric PIN constants (for adult second factor)
NUMERIC_PIN_MIN_LENGTH = 4
NUMERIC_PIN_MAX_LENGTH = 6
