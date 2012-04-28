#!/usr/bin/python

from setuptools import setup

setup(
    name="push",
    version="",
    packages=["push"],
    install_requires=[
        "wessex>=1.2",
        "paramiko",
        "dnspython",
    ],
    entry_points={
        "console_scripts": [
            "push = push.main:main",
            "deploy-report = push.reports:revisions",
        ]
    }
)
