import graphene

from graphene_validator.validation import validate
from .validation_test_suite import InputForTests, PersonalData, ValidationTestSuite


class ValidatingClientIdMutation(graphene.relay.ClientIDMutation):
    class Input:
        data = InputForTests()

    email = graphene.String()
    the_person = graphene.Field(PersonalData)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **_input):
        validate(cls, root, info, **_input)

        data = _input["data"] or {}

        return ValidatingClientIdMutation(
            email=data.get("email"),
            the_person=data.get("the_person"),
         )


class Mutations(graphene.ObjectType):
    test_mutation = ValidatingClientIdMutation.Field()


class TestClientIdMutationValidation(ValidationTestSuite):
    def build_input(self, input):
        return {
            "clientMutationId": "test-id",
            "input": {
                "data": input["input"]
            },
        }

    request = """
        mutation Test($input: ValidatingClientIdMutationInput!) {
            testMutation(input: $input) {
                email
                thePerson {
                    theName
                }
            }
        }"""
    schema = graphene.Schema(mutation=Mutations)
