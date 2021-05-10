import graphene

try:
    from django.apps import apps

    from .errors import ValidationError

    class ValidationErrorObjectType(graphene.ObjectType):
        code = graphene.String()

    class Query(graphene.ObjectType):
        """
        This query discovers all validation errors in every Django app and builds a list of error
        codes to return to the client for inspection.

        TODO(mc): extend this to include all possible runtime errors.
        TODO(mc): find a way to include metadata with the code (graphene doesn't support dicts)
        """

        all_errors = graphene.List(of_type=ValidationErrorObjectType)

        @classmethod
        def resolve_all_errors(cls, _instance, _info):
            errors = set()
            for app_name in apps.app_configs.keys():
                try:
                    app_module = __import__(app_name)
                except ModuleNotFoundError:
                    # Not all apps have a corresponding module
                    continue
                if hasattr(app_module, "errors"):
                    for symbol in dir(app_module.errors):
                        error_class = getattr(app_module.errors, symbol)
                        try:
                            if issubclass(error_class, ValidationError):
                                error = error_class()
                                errors.add((error.code,))
                        except (TypeError, AttributeError):
                            # Not a real class...
                            continue
            return ({"code": error[0]} for error in errors)


except ImportError:
    pass
