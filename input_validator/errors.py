# errors.py

"""
A set of specific validation errors that can be used in different contexts.
Ideally specific validation errors should be carefully named and be self explanatory
"""

from dataclasses import dataclass
from typing import Any

import graphene


class ValidationError(ValueError):
    """
    A specific error class that indicates the presence of one or more invalid values
    in a mutation's input.
    """

    def __init__(self, *args, path=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path

    def __str__(self):
        return self.__class__.__name__

    @property
    def meta(self):
        """
        Any additional (structured) information that is useful to provide a valid value.
        """

    @property
    def code(self):
        return self.__class__.__name__


class EmptyString(ValidationError):
    pass


class InvalidEmailFormat(ValidationError):
    pass


class NegativeValue(ValidationError):
    pass


@dataclass
class NotInRange(ValidationError):
    min: Any = None
    max: Any = None

    @property
    def meta(self):
        return {"min": self.min, "max": self.max}


class LengthNotInRange(NotInRange):
    pass
