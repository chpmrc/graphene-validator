from .validation import _do_validation


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
