import re

from typing import Optional, Tuple

CLEAN_PATTERN = re.compile(r'[^a-zA-Z0-9]')
TRANSACTION_PATTERN = re.compile(
    r'^\s*(?:(.*?\D)\s+)?([-+]?\d*\.?\d+)(?:\s+(\D.*?))?\s*$')
ALPHA_SPACE_PATTERN = re.compile(r'^[a-zA-Z\s]*$')


def clean_string(string: str) -> str:
    """Remove alphanumeric characters from a string and make all characters
    lowercase.

    Args:
        string (str): A string.

    Returns:
        cleaned (str): A cleaned string.

    """
    return CLEAN_PATTERN.sub('', string).lower()


def parse_transaction(string: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse a transaction input to retrieve the quantity and transaction Good,
    or else return `None` for both.

    Args:
        string (str): Transaction string to parse

    Returns:
        quantity (Optional[int]): Transaction quantity, if valid.
        good_name (Optional[str]): Transaction good name, if valid.

    """
    try:
        match = re.match(TRANSACTION_PATTERN, string)

        if match:
            before, quantity, after = match.groups()

            # Convert the matched number
            if '.' in quantity or '-' in quantity or 'e' in quantity.lower():
                return None, None
            quantity = int(quantity)
            if quantity < 1:
                return None, None

            # Validate and clean up text
            good_name = before.strip() if before else after.strip()
            if before and after:  # Text should not appear on both sides
                return None, None

            # Ensure the text contains only alphabetic characters and spaces
            if good_name and not re.match(ALPHA_SPACE_PATTERN, good_name):
                return None, None

            return quantity, good_name.lower()
        else:
            return None, None
    except Exception:
        return None, None


def rgb_interpolate(
        start_color: Tuple[int, ...],
        end_color: Tuple[int, ...],
        fraction: float) -> str:
    """Interpolate between two RGB tuples based on the fraction, return the
    interpolated color's color code.

    Args:
        start_color (Tuple[int, ...]): Start RGB color, with values in 0-255.
        end_color (Tuple[int, ...]): End RGB color, with values in 0-255.
        fraction (float): Fraction to interpolate. 0 returns `start_color`,
            1 returns `end_color`.

    Returns:
        interpolated_hex_code (str): Interpolated RGB color's color code

    """
    assert 0 <= fraction <= 1, f'Got fraction {fraction}'
    rgb = tuple(
        int(start + (end - start) * fraction)
        for start, end in zip(start_color, end_color)
    )
    return f'rgb({rgb[0]},{rgb[1]},{rgb[2]})'
