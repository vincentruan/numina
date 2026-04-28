"""OCR accuracy calculator using Levenshtein distance."""


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row: list[int] = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio using Levenshtein distance.

    Returns:
        float: 0.0 to 1.0 (0% to 100% match)
    """
    if not s1 and not s2:
        return 1.0

    if not s1 or not s2:
        return 0.0

    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)


def calculate_ocr_accuracy(expected: str, actual: str) -> int:
    """Calculate OCR accuracy percentage.

    Args:
        expected: Expected text string
        actual: OCR extracted text string

    Returns:
        int: 0 to 100 percentage
    """
    return int(levenshtein_ratio(expected, actual) * 100)
