import graphene


def _to_camel_case(name):
    return "".join(
        [word.title() if idx > 0 else word for idx, word in enumerate(name.split("_"))]
    )


def _get_path(field, camel_case=True):
    """
    Reconstruct the path to the given field, including list indices.
    """
    name_transform = _to_camel_case if camel_case else lambda text: text
    name, _value, _validator, parent, idx = field
    path = [idx, name_transform(name)] if idx is not None else [name_transform(name)]
    while parent:
        pname, _pvalue, _pvalidator, parent, pidx = parent
        path.insert(0, name_transform(pname))
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
                (name, value, inner_validator, current, None)
                for name, value in value.items()
            )
        elif isinstance(field_type, graphene.List):
            # TODO(mc): better way to check if it's a scalar?
            if isinstance(
                field_type.of_type._meta, graphene.types.scalars.ScalarOptions
            ):
                # List of scalar types, validate
                fields_to_validate.append((name, value, validator, parent, None))
            else:
                # List of complex types, unpack
                inner_validator = _unwrap_validator(field_type)
                for idx, item in enumerate(value):
                    subtrees_to_validate.append((item, inner_validator))
                    fields_to_unpack.extend(
                        (name, value, inner_validator, current, idx)
                        for name, value in item.items()
                    )
        else:
            # Scalar type, we can mark for validation!
            fields_to_validate.append((name, value, validator, parent, idx))
    return fields_to_validate, subtrees_to_validate
