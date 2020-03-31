import graphene
import functools

from graphene import List, Scalar
from graphene.types.inputfield import InputField
from graphql import GraphQLError

from .errors import ValidationError
from .utils import _get_path, _to_camel_case, _unpack_input_tree, _unwrap_validator


def validated(cls):
    """
    A class decorator to validate mutation input based on its input fields.
    This allows to define (and reuse) validation logic and have the mutation only worry about
    business logic.

    The validator class (InputObjectType) can implement either field level validation
    (`validate_{field_name}` static methods) and/or a generc `validate` method that receives the
    whole input tree.

    The `validate_{field_name}` methods must raise a ValidationError instance
    in case of invalid input. This will be converted into a proper GraphQLError.

    Nested validators and lists are supported.

    Example usage:

    class PeopleInput(graphene.InputObjectType):
        name = graphene.String()

        @staticmethod
        def validate_name(name):
            if not 300 < len(name) < 3:
                raise LengthNotInRange(min=1, max=300)
            return name

    class MyInputObjectType(graphene.InputObjectType):
        email = graphene.String()
        people = graphene.List(PeopleInput)

        @staticmethod
        def validate_email(email):
            if "@" not in email:
                raise InvalidEmailFormat
            return email

    @validated
    class MyMutation(graphene.Mutation):
        class Arguments:
            inpt = graphene.Argument(MyInputObjectType)

        def mutate(parent, info, inpt):
            pass


    Example output:
        {
            "errors": [
                {
                    "message": "ValidationError",
                    ...
                    "extensions": {
                        "validationErrors": [
                            {
                                "code": "InvalidEmailFormat",
                                "path": [
                                    "email"
                                ]
                            },
                            {
                                "code": "LengthNotInRange",
                                "path": [
                                    "people",
                                    0,
                                    "name"
                                ],
                                "meta": {"min": 1, "max": 300}
                            }
                        ]
                    }
                }
            ],
            ...
        }

    """

    class Wrapper(cls):
        def mutate(self, info, **kwargs):  # pylint: disable=too-many-locals
            errors = []
            # Assume only a single input tree is given as kwarg
            input_key, input_tree = list(kwargs.items())[0]
            root_validator = _unwrap_validator(
                getattr(cls.Arguments, input_key).type)
            # Run a BFS on the input tree, flattening everything to a list of fields to validate
            # and a list of subtrees to validate as a whole (for codependent fields)
            fields_to_validate, subtrees_to_validate = _unpack_input_tree(
                input_tree, root_validator
            )

            # Run field level validation logic
            for ftv in fields_to_validate:
                name, value, validator, _parent, _idx = ftv
                path = _get_path(ftv)
                try:
                    new_value = getattr(
                        validator, f"validate_{name}", lambda value: value)(value)
                    # If validator changed the value we need to update it in the input tree
                    if new_value != value:
                        # Grab a ref to the field to change by following the path in the input tree
                        field = functools.reduce(
                            lambda obj, k: obj[k] if k else obj, path[:-1], input_tree
                        )
                        field[name] = new_value
                except ValidationError as ve:
                    errors.append(
                        {"code": str(ve), "path": path, "meta": ve.meta})

            # Don't run subtree level validation if one or more fields are invalid
            if not errors:
                # Run validation logic for the input subtrees
                subtrees_to_validate.append((input_tree, root_validator))
                for stv in subtrees_to_validate:
                    value, validator = stv
                    try:
                        input_tree.update(
                            getattr(validator, f"validate",
                                    lambda values: values)(value)
                        )
                    except ValidationError as ve:
                        # Here we can't build the path so we let the caller customize it
                        errors.append(
                            {"code": str(ve), "path": ve.path, "meta": ve.meta})

            if errors:
                raise GraphQLError(
                    message="ValidationError", extensions={"validationErrors": errors},
                )
            return cls.mutate(self, info, **kwargs)

    return Wrapper


# utils.py


def _to_camel_case(name):
    return "".join([word.title() if idx > 0 else word for idx, word in enumerate(name.split("_"))])


def _get_path(field):
    """
    Reconstruct the path to the given field, including list indices.
    """
    name, _value, _validator, parent, idx = field
    path = [idx, _to_camel_case(name)] if idx is not None else [
        _to_camel_case(name)]
    while parent:
        pname, _pvalue, _pvalidator, parent, pidx = parent
        path.insert(0, _to_camel_case(pname))
        if pidx:
            path.insert(0, pidx)
    return path


def _unwrap_validator(validator):
    """
    Unwrap validator from wrappers such as NonNull etc.
    """
    while hasattr(validator, "of_type"):
        validator = validator.of_type
    return validator


def _unpack_input_tree(input_tree, validator_cls):
    """
    Runs a BFS on the input tree, reducing a set of complex input objects to a list of scalars
    with related validators, as well as slicing the input tree into subtrees to be validated
    as a whole.

    returns:
        fields_to_validate: the final result is a list of tuples, each containing:
            - Name of the field to validate
            - Its value
            - The validator class to be used
            - The parent tuple
            - The index (if it's a list item)

        subtrees_to_validate: input subtrees to pass to the high level validate methods, tuples:
            - Subtree (dict)
            - Related validator class
    """
    fields_to_validate = []
    subtrees_to_validate = []
    fields_to_unpack = [
        (name, value, validator_cls, None, None) for name, value in input_tree.items()
    ]
    while fields_to_unpack:
        current = fields_to_unpack.pop(0)
        name, value, validator, parent, idx = current
        validator = _unwrap_validator(validator)
        # Look up whether corresponding field is a complex type (list/input field)
        field_type = getattr(validator, name)
        if isinstance(field_type, graphene.types.inputfield.InputField):
            inner_validator = _unwrap_validator(field_type.type)
            subtrees_to_validate.append((value, inner_validator))
            # Unpack nested input fields
            fields_to_unpack.extend(
                (name, value, inner_validator, current, None) for name, value in value.items()
            )
        elif isinstance(field_type, graphene.List):
            # TODO(mc): better way to check if it's a scalar?
            if isinstance(field_type.of_type._meta, graphene.types.scalars.ScalarOptions):
                # List of scalar types, validate
                fields_to_validate.append(
                    (name, value, validator, parent, None))
            else:
                # List of complex types, unpack
                inner_validator = _unwrap_validator(field_type)
                for idx, item in enumerate(value):
                    subtrees_to_validate.append((item, inner_validator))
                    fields_to_unpack.extend(
                        (name, value, inner_validator, current, idx) for name, value in item.items()
                    )
        else:
            # Scalar type, we can mark for validation!
            fields_to_validate.append((name, value, validator, parent, idx))
    return fields_to_validate, subtrees_to_validate
