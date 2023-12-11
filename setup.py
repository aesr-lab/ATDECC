# tricking setuptools to produce binary wheel
from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="atdecc_api_mod",  # as it would be imported
            sources=[],
        ),
    ]
)
