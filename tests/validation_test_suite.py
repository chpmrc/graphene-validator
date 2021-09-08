import graphene

from graphene_validator.errors import (
    EmptyString,
    InvalidEmailFormat,
    LengthNotInRange,
    NegativeValue,
    NotInRange,
    SingleValidationError,
)


# Some dummy errors

class NameEqualsAge(SingleValidationError):
    def __init__(self, path):
        self.path = path

    @property
    def error_details(self):
        details = super().error_details
        for detail in details:
            detail["path"] = self.path
        return details


class NameAndAgeInEmail(SingleValidationError):
    pass


class PersonalDataInput(graphene.InputObjectType):
    # Check camelCasing too
    the_name = graphene.String()
    the_age = graphene.Int()
    email = graphene.String()

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
        if inpt.get("the_name") == str(inpt.get("the_age")):
            raise NameEqualsAge(path=["name"])
        return inpt


class InputForTests(graphene.InputObjectType):
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


class OutputForTests(graphene.ObjectType):
    email = graphene.String()
    the_person = graphene.Field(PersonalData)


class ValidationTestSuite:
    def _execute_query(self, input):
        return self.schema.execute(
            request_string=self.request,
            variable_values=input,
        )

    def test_simple_validation(self):
        result = self._execute_query({"input": {"email": "invalid_email"}})
        assert result.errors[0].message == "ValidationError"

    def test_nested_validation(self):
        result = self._execute_query({
            "input": {
                "email": "invalid_email",
                "people": [{"theName": "", "theAge": "-1"}],
            }
        })
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert result.errors[0].message == "ValidationError"
        assert validation_errors[0]["path"] == ["email"]
        assert validation_errors[1]["path"] == ["people", 0, "theName"]
        assert validation_errors[2]["path"] == ["people", 0, "theAge"]

    def test_valid_input(self):
        result = self._execute_query({
            "input": {
                "email": "a0@b.c",
                "people": [{"theName": "a", "theAge": "0"}],
            }
        })
        assert not result.errors
        assert result.data["testMutation"]["email"] == "a0@b.c"

    def test_transform(self):
        result = self._execute_query({
            "input": {
                "email": " a0@b.c ",
                "thePerson": {"theName": " a ", "theAge": "0"},
            }
        })
        assert not result.errors
        assert result.data["testMutation"]["email"] == "a0@b.c"
        assert result.data["testMutation"]["thePerson"]["theName"] == "a"

    def test_sub_trees_are_independent(self):
        result = self._execute_query({
            "input": {
                "email": "top.level@email",
                "thePerson": {"email": "sub.tree@email"},
            }
        })
        assert not result.errors
        assert result.data["testMutation"]["email"] == "top.level@email"

    def test_root_validate(self):
        input = {
            "input": {
                "email": "a1@b.c",
                "people": [{"theName": "a", "theAge": "0"}],
            }
        }

        result = self._execute_query(input)
        assert result.errors[0].message == "ValidationError"

        input["input"]["email"] = "a0@b.c"
        result = self._execute_query(input)
        assert not result.errors

    def test_list_of_scalars_validation(self):
        input = {"input": {"numbers": [1]}}

        result = self._execute_query(input)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["numbers"]

        input["input"]["numbers"] = [1, 2]
        result = self._execute_query(input)
        assert not result.errors

    def test_nested_high_level_validate(self):
        input = {"input": {"people": [{"theName": "0", "theAge": 0}]}}

        result = self._execute_query(input)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["name"]

        input = {"input": {"thePerson": {"theName": "0", "theAge": 0}}}
        result = self._execute_query(input)
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["path"] == ["name"]

    def test_error_codes(self):
        result = self._execute_query({"input": {"email": "asd"}})
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["code"] == InvalidEmailFormat.__name__

    def test_range(self):
        result = self._execute_query({"input": {"numbers": [-1, 0]}})
        validation_errors = result.errors[0].extensions["validationErrors"]
        assert validation_errors[0]["code"] == NotInRange.__name__
        assert validation_errors[0]["meta"]["min"] == 0
        assert validation_errors[0]["meta"]["max"] == 9

    def test_handling_top_level_null_input_object(self):
        result = self._execute_query({"input": None})
        assert not result.errors

    def test_handling_inner_null_input_object(self):
        result = self._execute_query({
            "input": {
                "thePerson": None,
            }
        })
        assert not result.errors

    def test_handling_null_input_object_in_a_list(self):
        result = self._execute_query({"input": {"people": [None]}})
        assert not result.errors
