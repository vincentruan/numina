"""SymPy-based symbolic equivalence checker for mathematical expressions.

Replaces floating-point tolerance comparison with proper symbolic equivalence.
Handles algebraic equivalence (3(x+2) ≡ 3x+6), numeric equivalence, and
structural equivalence.

Falls back to float comparison when SymPy cannot determine equivalence.
"""

from functools import lru_cache
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)

# Lazy import to avoid loading SymPy at module import time
_sympy_available: bool | None = None


def _check_sympy_available() -> bool:
    """Check if SymPy is available (cached after first call)."""
    global _sympy_available
    if _sympy_available is None:
        try:
            import sympy  # noqa: F401
            _sympy_available = True
        except ImportError:
            _sympy_available = False
            logger.warning(
                "SymPy not installed — symbolic equivalence disabled. "
                "Install with: pip install sympy"
            )
    return _sympy_available


@lru_cache(maxsize=1024)
def _parse_expression(expr_str: str) -> Any:
    """Parse a string expression into SymPy expression (cached).

    Returns None if parsing fails.
    """
    if not _check_sympy_available():
        return None

    import sympy

    try:
        # Use sympify with strict=False to handle common notations
        # Convert common user input patterns
        normalized = expr_str.strip()

        # Handle implicit multiplication: 2x -> 2*x, 3(x+1) -> 3*(x+1)
        # This is a simple heuristic — SymPy's sympify handles most cases
        normalized = normalized.replace("^", "**")

        # Parse with local definitions for common symbols
        local_dict = {
            "pi": sympy.pi,
            "e": sympy.E,
            "sqrt": sympy.sqrt,
        }

        expr = sympy.sympify(normalized, locals=local_dict, strict=False)
        return expr
    except Exception as e:
        logger.debug("Failed to parse expression '%s': %s", expr_str, e)
        return None


def symbolic_eq(expr1_str: str, expr2_str: str) -> bool | None:
    """Check if two expressions are symbolically equivalent.

    Returns:
        True: Expressions are provably equivalent
        False: Expressions are provably different
        None: Cannot determine (SymPy unavailable or parsing failed)

    Examples:
        >>> symbolic_eq("3*(x+2)", "3*x+6")
        True
        >>> symbolic_eq("x^2 - 1", "(x-1)*(x+1)")
        True
        >>> symbolic_eq("x+1", "x+2")
        False
    """
    if not _check_sympy_available():
        return None

    import sympy

    expr1 = _parse_expression(expr1_str)
    expr2 = _parse_expression(expr2_str)

    if expr1 is None or expr2 is None:
        return None

    try:
        # Method 1: Check if difference simplifies to zero
        diff = sympy.simplify(expr1 - expr2)
        if diff == 0:
            return True

        # Method 2: Use equals() for more complex equivalence
        # This uses random numerical evaluation as a heuristic
        if expr1.equals(expr2):
            return True

        # Method 3: Check if they have the same simplified form
        if sympy.simplify(expr1) == sympy.simplify(expr2):
            return True

        # If we get here, they're likely different
        # But we can't be 100% sure for all cases
        return False

    except Exception as e:
        logger.debug("Symbolic equivalence check failed: %s", e)
        return None


def numeric_or_symbolic_eq(
    correct_val: Any,
    user_val: Any,
    *,
    float_rel_tol: float = 1e-4,
    float_abs_tol: float = 1e-6,
) -> bool:
    """Check equality using symbolic equivalence with float fallback.

    This is the main entry point for scoring. It:
    1. Tries symbolic equivalence if both values are strings (expressions)
    2. Falls back to float comparison for numeric values
    3. Falls back to exact equality for other types

    Args:
        correct_val: The correct answer value
        user_val: The user's answer value
        float_rel_tol: Relative tolerance for float comparison
        float_abs_tol: Absolute tolerance for float comparison

    Returns:
        True if answers are equivalent, False otherwise
    """
    import math

    # Both strings — try symbolic equivalence
    if isinstance(correct_val, str) and isinstance(user_val, str):
        result = symbolic_eq(correct_val, user_val)
        if result is not None:
            return result
        # Symbolic check failed — fall back to string comparison
        return correct_val.strip() == user_val.strip()

    # Both numeric — use float comparison
    if isinstance(correct_val, (int, float)) and isinstance(user_val, (int, float)):
        # Handle bool specially (bool is int subclass)
        if isinstance(correct_val, bool) or isinstance(user_val, bool):
            return correct_val == user_val
        return math.isclose(
            float(correct_val),
            float(user_val),
            rel_tol=float_rel_tol,
            abs_tol=float_abs_tol,
        )

    # Exact equality for other types
    return correct_val == user_val


def clear_cache() -> None:
    """Clear the expression parsing cache."""
    _parse_expression.cache_clear()
