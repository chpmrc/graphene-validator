# Graphene input validator

**Important**: this is a proof of concept and most likely not ready for production use.

The GraphQL Python ecosystem (i.e. `graphene`) lacks a proper way of validating input and returning meaningful errors to the client. This PoC aims at solving that. The client will know it needs to look into `extensions` for validation errors because of the error message `ValidationError`.

This library provides a class decorator `@validated`, for mutations, that allows for field level and input level validation similarly to [DRF](https://www.django-rest-framework.org/) serializers' `validate` methods. To validate a field you'll need to declare a static method named `validate_{field_name}`. Input wide validation (e.g. for fields that depend on other fields) can be performed in the `validate` method. `validate` will only be called if all field level validation methods succeed.

It also supports recursive validation so that you can use nested `InputField`s and validation will be performed all the way down to the scalars.

To indicate an invalid value the corresponding validation method should raise an instance of a subclass of `ValidationError`. Validation methods also allow to manipulate the value on the fly (for example to minimize DB queries by swapping an ID for the corresponding object) which will then replace the corresponding value in the main input (to be used in `validate` and the mutation itself).

A `ValidationError` subclass can report one or more validation errors. Its `error_details` attribute must be an iterable of dictionaries, providing the details for the validation errors. The error detail mappings can contain any members, but as a convention `code` member is encouraged to be included.

For field level errors the error details will be amended with a `path` member that helps the client determine which slice of input is invalid, useful for rich forms and field highlighting on the UI.

A `SingleValidationError` class is provided for validation errors that only contain a single error detail. This class also supports a `meta` error detail property, to inform the clients of potential constraints on the input itself.

Note that verbose messages aren't supported because I strongly believe those should be handled on the client (together with localization).

## Usage

### Validating a mutation's input

Here is an example usage (which you can find in [tests.py](tests.py) as well):

```python
import graphene
from graphene_validator.decorators import validated

class TestInput(graphene.InputObjectType):
    email = graphene.String()
    people = graphene.List(PersonalDataInput)
    numbers = graphene.List(graphene.Int)
    person = graphene.InputField(PersonalDataInput)

    @staticmethod
    def validate_email(email, info, **input):
        if "@" not in email:
            raise InvalidEmailFormat
        return email.strip(" ")

    @staticmethod
    def validate_numbers(numbers, info, **input):
        if len(numbers) < 2:
            raise LengthNotInRange(min=2)
        for n in numbers:
            if n < 0 or n > 9:
                raise NotInRange(min=0, max=9)
        return numbers

    @staticmethod
    def validate(input, info):
        if input.get("people") and input.get("email"):
            first_person_name_and_age = (
                f"{input['people'][0]['the_name']}{input['people'][0]['the_age']}"
            )
            if input["email"].split("@")[0] != first_person_name_and_age:
                raise NameAndAgeInEmail
        return input


@validated
class TestMutation(graphene.Mutation):
    class Arguments:
        input = TestInput()

    result = graphene.String()

    def mutate(self, _info, input):
        return TestMutation(result="ok"))
```

And this is an example output:

```json
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
```

### Validating a field that depends on other fields or the request's context

```python
class TestInput(graphene.InputObjectType):
    first_field = graphene.String()
    second_field = graphene.String()

    @staticmethod
    def validate_first_field(first_field, info, **input):
        second_field = input.get("second_field")
        if second_field != "desired value":
            raise InvalidSecondField
        if info.context.user.role != "admin":
            raise Unauthorized
        return first_field

    ...
```

## Running tests

`pip install -e .`

`pytest tests.py`

## Limitations

Since errors are listed in the `extensions` field of a generic `GraphQLError`, instead of using the typical [union based errors](https://blog.logrocket.com/handling-graphql-errors-like-a-champ-with-unions-and-interfaces/), errors aren't automatically discoverable. The ideal solution would be a hybrid that allows to decorate the mutation and obtain a union that can be used by the client for autodiscovery of the error types and metadata.

An example graphene-django query is added to [schema.py](graphene_validator/schema.py) to allow the client to discover error types and their metadata (the latter is a TODO).
