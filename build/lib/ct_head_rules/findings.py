"""Input types shared by all rules."""

from enum import Enum


class Finding(Enum):
    """A clinical finding whose absence must be stated, never assumed.

    Deliberately not a bool: every member is truthy, so `if not finding:` can
    never quietly turn UNKNOWN into ABSENT. Compare with `is` instead.
    """

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
