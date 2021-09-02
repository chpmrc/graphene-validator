import functools

from .errors import ValidationError, ValidationGraphQLError
from .utils import _get_path, _unpack_input_tree, _unwrap_validator


def _do_validation(info, input_tree, input_arg, **kwargs):
    errors = []

    root_validator = _unwrap_validator(
        getattr(input_arg, "get_type", lambda: input_arg.type)()
    )
    # Run a BFS on the input tree, flattening everything to a list of fields to validate
    # and a list of subtrees to validate as a whole (for codependent fields)
    fields_to_validate, subtrees_to_validate = _unpack_input_tree(
        input_tree, root_validator
    )

    # Run field level validation logic
    for ftv in fields_to_validate:
        name, value, validator, _parent, _idx = ftv
        try:
            new_value = getattr(
                validator,
                f"validate_{name}",
                lambda value, info, **kwargs: value,
            )(value, info, **kwargs)
            # If validator changed the value we need to update it in the input tree
            if new_value != value:
                path = _get_path(ftv, False)
                # Grab a ref to the field to change by following the path in the input tree
                field = functools.reduce(
                    lambda obj, k: obj[k] if k else obj, path[:-1], input_tree
                )
                field[name] = new_value
        except ValidationError as ve:
            # Insert the field's path into the error details
            common_detail = {"path": _get_path(ftv)}
            for error_detail in ve.error_details:
                error_detail.update(common_detail)
                errors.append(error_detail)

    # Don't run subtree level validation if one or more fields are invalid
    if not errors:
        # Run validation logic for the input subtrees
        subtrees_to_validate.append((input_tree, root_validator))
        for stv in subtrees_to_validate:
            value, validator = stv
            try:
                getattr(
                    validator,
                    "validate",
                    lambda values, info, **kwargs: values,
                )(value, info)
            except ValidationError as ve:
                errors += list(ve.error_details)

    if errors:
        raise ValidationGraphQLError(
            message="ValidationError",
            extensions={"validationErrors": errors},
        )


def validated(cls):
    """
    A class decorator to validate mutation input based on its input fields.
    This allows to define (and reuse) validation logic and have the mutation only worry about
    business logic.

    The validator class (InputObjectType) can implement either field level validation
    (`validate_{field_name}` static methods) and/or a generc `validate` method that receives the
    whole input tree.

    The `validate_{field_name}` methods must raise a ValidationError instance
    in case of invalid input. The ValidationErrors are collected and any errors
    are reported by raising a dedicated GraphQLError subclass, ValidationGraphQLError.

    Nested validators and lists are supported.

    Example usage:

    class PeopleInput(graphene.InputObjectType):
        name = graphene.String()

        @staticmethod
        def validate_name(name, info, **input):
            if not 300 < len(name) < 3:
                raise LengthNotInRange(min=1, max=300)
            return name

    class MyInputObjectType(graphene.InputObjectType):
        email = graphene.String()
        people = graphene.List(PeopleInput)

        @staticmethod
        def validate_email(email, info, **input):
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
        def mutate(parent, info, **kwargs):  # pylint: disable=too-many-locals
            if kwargs:
                # Assume only a single input tree is given as kwarg
                input_key, input_tree = list(kwargs.items())[0]
                input_arg = getattr(cls.Arguments, input_key)
                _do_validation(info, input_tree, input_arg, **kwargs)

            return cls.mutate(parent, info, **kwargs)

    Wrapper._meta.__dict__["name"] = cls._meta.name
    Wrapper._meta.__dict__["description"] = cls._meta.description
    return Wrapper
