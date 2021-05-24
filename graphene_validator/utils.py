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
    fields_to_unpack = []

    def add_subtree_to_validate(tree, validator):
        if tree is not None:
            subtrees_to_validate.append((tree, validator))

    def add_fields_to_unpack(tree, validator_cls, parent=None, index=None):
        if tree is not None:
            fields_to_unpack.extend(
                (name, value, validator_cls, parent, index)
                for name, value in tree.items()
            )

    add_fields_to_unpack(input_tree, validator_cls)

    while fields_to_unpack:
        current = fields_to_unpack.pop(0)
        name, value, validator, parent, idx = current
        validator = _unwrap_validator(validator)
        # Look up whether corresponding field is a complex type (list/input field)
        field_type = getattr(validator, name)
        if isinstance(field_type, graphene.types.inputfield.InputField):
            inner_validator = _unwrap_validator(field_type.type)
            add_subtree_to_validate(value, inner_validator)
            # Unpack nested input fields
            add_fields_to_unpack(value, inner_validator, current)
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
                    add_subtree_to_validate(item, inner_validator)
                    add_fields_to_unpack(item, inner_validator, current, idx)
        else:
            # Scalar type, we can mark for validation!
            fields_to_validate.append((name, value, validator, parent, idx))
    return fields_to_validate, subtrees_to_validate
