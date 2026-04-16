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
