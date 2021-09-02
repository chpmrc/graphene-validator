# errors.py

"""
A set of specific validation errors that can be used in different contexts.
Ideally specific validation errors should be carefully named and be self explanatory
"""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from graphql import GraphQLError


class ValidationError(ValueError):
    """
    A specific error class that indicates the presence of one or more invalid values
    in a mutation's input.
    """

    def __str__(self):
        return self.__class__.__name__

    @property
    def error_details(self) -> Iterable[Mapping[str, Any]]:
        return []


class SingleValidationError(ValidationError):
    @property
    def meta(self):
        """
        Any additional (structured) information that is useful to provide a valid value.
        """

    @property
    def code(self):
        return self.__class__.__name__

    @property
    def error_details(self) -> Iterable[Mapping[str, Any]]:
        return [{"code": self.code, "meta": self.meta}]


class EmptyString(SingleValidationError):
    pass


class InvalidEmailFormat(SingleValidationError):
    pass


class NegativeValue(SingleValidationError):
    pass


@dataclass
class NotInRange(SingleValidationError):
    min: Any = None
    max: Any = None

    @property
    def meta(self):
        return {"min": self.min, "max": self.max}


class LengthNotInRange(NotInRange):
    pass


class ValidationGraphQLError(GraphQLError):
    pass
