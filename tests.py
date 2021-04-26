import graphene

from graphene_validator.decorators import validated
from graphene_validator.errors import (
    EmptyString,
    InvalidEmailFormat,
    LengthNotInRange,
    NegativeValue,
    NotInRange,
    ValidationError,
)

# Some dummy errors


class NameEqualsAge(ValidationError):
    pass


class NameAndAgeInEmail(ValidationError):
    pass


class PersonalDataInput(graphene.InputObjectType):
    # Check camelCasing too
    the_name = graphene.String()
    the_age = graphene.Int()

    @staticmethod
    def validate_the_name(name, info, **input):
        if len(name) == 0:
            raise EmptyString
        return name.strip()

    @staticmethod
    def validate_the_age(age, info, **input):
        if age < 0:
            raise NegativeValue
        return age

    @staticmethod
    def validate(inpt, info):
        if inpt["the_name"] == str(inpt["the_age"]):
            raise NameEqualsAge(path=["name"])
        return inpt


class TestInput(graphene.InputObjectType):
    email = graphene.String()
    people = graphene.List(PersonalDataInput)
    numbers = graphene.List(graphene.Int)
    # Check camelCasing too
    the_person = graphene.InputField(PersonalDataInput)

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
    def validate(inpt, info):
        if inpt.get("people") and inpt.get("email"):
            first_person_name_and_age = (
                f"{inpt['people'][0]['the_name']}{inpt['people'][0]['the_age']}"
            )
            if inpt["email"].split("@")[0] != first_person_name_and_age:
                raise NameAndAgeInEmail
        return inpt


class PersonalData(graphene.ObjectType):
    the_name = graphene.String()


class TestMutationOutput(graphene.ObjectType):
    email = graphene.String()
    the_person = graphene.Field(PersonalData)


@validated
class TestMutation(graphene.Mutation):
    class Arguments:
        _inpt = graphene.Argument(TestInput, name="input")

    Output = TestMutationOutput

    def mutate(self, _info, _inpt):
        return TestMutationOutput(
            email=_inpt.get("email"),
            the_person=_inpt.get("the_person"),
        )


class Mutations(graphene.ObjectType):
    test_mutation = TestMutation.Field()


schema = graphene.Schema(mutation=Mutations)


class TestValidation:

    REQUEST_TEMPLATE = dict(
        request_string="""
        mutation Test($input: TestInput!) {
            testMutation(input: $input) {
                email
                thePerson {
                    theName
                }
            }
        }"""
    )

    def test_simple_validation(self):
        result = schema.execute(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={"input": {"email": "invalid_email"}},
        )
        assert result.errors[0].message == "ValidationError"

    def test_nested_validation(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={
                "input": {
                    "email": "invalid_email",
                    "people": [{"theName": "", "theAge": "-1"}],
                }
            },
        )
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert result.errors[0].message == "ValidationError"
        assert validation_errors[0]["path"] == ["email"]
        assert validation_errors[1]["path"] == ["people", 0, "theName"]
        assert validation_errors[2]["path"] == ["people", 0, "theAge"]

    def test_valid_input(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={
                "input": {
                    "email": "a0@b.c",
                    "people": [{"theName": "a", "theAge": "0"}],
                }
            },
        )
        result = schema.execute(**request)
        assert not result.errors
        assert result.data["testMutation"]["email"] == "a0@b.c"

    def test_transform(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={
                "input": {
                    "email": " a0@b.c ",
                    "thePerson": {"theName": " a ", "theAge": "0"},
                }
            },
        )
        result = schema.execute(**request)
        assert not result.errors
        assert result.data["testMutation"]["email"] == "a0@b.c"
        assert result.data["testMutation"]["thePerson"]["theName"] == "a"

    def test_root_validate(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={
                "input": {
                    "email": "a1@b.c",
                    "people": [{"theName": "a", "theAge": "0"}],
                }
            },
        )
        result = schema.execute(**request)
        assert result.errors[0].message == "ValidationError"
        request["variable_values"]["input"]["email"] = "a0@b.c"
        result = schema.execute(**request)
        assert not result.errors

    def test_list_of_scalars_validation(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={"input": {"numbers": [1]}},
        )
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["numbers"]
        request["variable_values"]["input"]["numbers"] = [1, 2]
        result = schema.execute(**request)
        assert not result.errors

    def test_nested_high_level_validate(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={"input": {"people": [{"theName": "0", "theAge": 0}]}},
        )
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["name"]
        request["variable_values"] = {
            "input": {"thePerson": {"theName": "0", "theAge": 0}}
        }
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["name"]

    def test_error_codes(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={"input": {"email": "asd"}},
        )
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["code"] == InvalidEmailFormat.__name__

    def test_range(self):
        request = dict(
            **TestValidation.REQUEST_TEMPLATE,
            variable_values={"input": {"numbers": [-1, 0]}},
        )
        result = schema.execute(**request)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["code"] == NotInRange.__name__
        assert validation_errors[0]["meta"]["min"] == 0
        assert validation_errors[0]["meta"]["max"] == 9
