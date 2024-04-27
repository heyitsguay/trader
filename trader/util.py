import re

CLEAN_PATTERN = re.compile(r'^[a-zA-Z0-9]')


def clean_string(string: str) -> str:
    """Remove alphanumeric characters from a string and make all characters
    lowercase.

    Args:
        string (str): A string.

    Returns:
        cleaned (str): A cleaned string.

    """
    return CLEAN_PATTERN.sub('', string).lower()
