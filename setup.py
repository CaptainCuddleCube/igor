#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="igor",
    version="0.0.1",
    description="Igor is your friendly automation slackbot",
    author="Ashton Hudson",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "boto3>=1.0.0",
        "botocore>=1.0.0",
        "certifi>=2019.6.16",
        "chardet>=3.0.0",
        "docutils>=0.15.0",
        "idna>=2.0",
        "jmespath>=0.9.0",
        "python-dateutil>=2.0.0",
        "requests>=2.0.0",
        "s3transfer>=0.2.0",
        "six>=1.0.0",
        "urllib3>=1.0.0",
    ],
    entry_points={},
)
