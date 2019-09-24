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
        "boto3==1.9.220",
        "botocore==1.12.220",
        "certifi==2019.6.16",
        "chardet==3.0.4",
        "docutils==0.15.2",
        "idna==2.8",
        "jmespath==0.9.4",
        "python-dateutil==2.8.0",
        "requests==2.22.0",
        "s3transfer==0.2.1",
        "six==1.12.0",
        "urllib3==1.25.3",
    ],
    entry_points={},
)
