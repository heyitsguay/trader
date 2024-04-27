import re

from typing import Optional, Tuple

CLEAN_PATTERN = re.compile(r'^[a-zA-Z0-9]')
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
