"""Last line of defence on what leaves the app: hide email addresses and card-length digit runs."""

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Customers paste numbers with dots, tabs, non-breaking spaces and Unicode dashes too.
# Keep the digit count bounded; transaction IDs and the last four alone are not card numbers.
CARD_NUMBER = re.compile(r"(?<!\w)\d(?:[\s.\-\u2010-\u2015\u200b]*\d){12,18}(?!\w)")


def redact(text: str, *, emails: bool = True) -> tuple[str, list[str]]:
    """Return the cleaned text and a list of what was hidden."""
    hidden = []

    def hide(kind):
        def replace(_match):
            hidden.append(kind)
            return f"[{kind} hidden]"
        return replace

    text = CARD_NUMBER.sub(hide("card number"), text)
    if emails:
        text = EMAIL.sub(hide("email"), text)
    return text, hidden
