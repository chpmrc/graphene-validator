# Graphene input validator

**Important**: this is a proof of concept and most likely not ready for production use.

The GraphQL Python ecosystem (i.e. `graphene`) lacks a proper way of validating input and returning meaningful errors to the client. This PoC aims at solving that. The client will know it needs to look into `extensions` for validation errors because of the error message `ValidationError`.

This library provides a class decorator `validate`, for mutations, that allows for field level and input level validation similarly to [DRF](https://www.django-rest-framework.org/) serializers' `validate` methods.

Field level errors also provide a `path` field that helps the client determine which slice of input is invalid, useful for rich forms and field highlighting on the UI.

Custom errors can be defined (e.g. `NotInRange` with `min` and `max`) to inform the clients of potential constraints on the input itself. It also supports recursive validation so that you can use nested `InputField`s and validation will be run all the way down to the scalars.

Note that verbose messages aren't supported because I strongly believe those should be handled on the client (together with localization).

## Usage

Here is an example usage (which you can find in [tests.py](tests.py) as well):

```python
class TestInput(graphene.InputObjectType):
    email = graphene.String()
    people = graphene.List(PersonalDataInput)
    numbers = graphene.List(graphene.Int)
    person = graphene.InputField(PersonalDataInput)

    @staticmethod
    def validate_email(email):
        if "@" not in email:
            raise InvalidEmailFormat
        return email.strip(" ")

    @staticmethod
    def validate_numbers(numbers):
        if len(numbers) < 2:
            raise LengthNotInRange(min=2)
        for n in numbers:
            if n < 0 or n > 9:
                raise NotInRange(min=0, max=9)
        return numbers

    @staticmethod
    def validate(inpt):
        if inpt.get("people") and inpt.get("email"):
            first_person_name_and_age = (
                f"{inpt['people'][0]['the_name']}{inpt['people'][0]['the_age']}"
            )
            if inpt["email"].split("@")[0] != first_person_name_and_age:
                raise NameAndAgeInEmail
        return inpt


@validated
class TestMutation(graphene.Mutation):
    class Arguments:
        inpt = graphene.Argument(TestInput, name="input")

    result = graphene.String()

    def mutate(self, _info, inpt):
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

## Running tests

`pip install -r requirements.txt`

`pytest tests.py`

## Limitations

Since errors are listed in the `extensions` field of a generic `GraphQLError`, instead of using the typical [union based errors](https://blog.logrocket.com/handling-graphql-errors-like-a-champ-with-unions-and-interfaces/), errors aren't automatically discoverable. The ideal solution would be a hybrid that allows to decorate the mutation and obtain a union that can be used by the client for autodiscovery of the error types and metadata.

An example query is added to [schema.py](input_validator/schema.py) to allow the client to discover error types and their metadata (TODO).
