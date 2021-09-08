import graphene

from graphene_validator.validation import validate
from .validation_test_suite import InputForTests, OutputForTests, ValidationTestSuite


class ValidatingMutation(graphene.Mutation):
    class Arguments:
        _input = graphene.Argument(InputForTests, name="input")

    Output = OutputForTests

    @classmethod
    def mutate(cls, root, info, _input=None):
        validate(cls, root, info, _input=_input)

        if _input is None:
            _input = {}

        return OutputForTests(
            email=_input.get("email"),
            the_person=_input.get("the_person"),
        )


class Mutations(graphene.ObjectType):
    test_mutation = ValidatingMutation.Field()


class TestMutationValidation(ValidationTestSuite):
    request = """
        mutation Test($input: InputForTests) {
            testMutation(input: $input) {
                email
                thePerson {
                    theName
                }
            }
        }"""
    schema = graphene.Schema(mutation=Mutations)
