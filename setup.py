import setuptools

setuptools.setup(
    name="graphene-validator",
    version="1.0.0",
    url="https://github.com/chpmrc/graphene-validator.git",
    author="Marco Chiappetta",
    description="An input validation library for Graphene",
    packages=setuptools.find_packages(),
    install_requires=["graphene<3"],
)
