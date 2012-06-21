#!/usr/bin/python

from setuptools import setup

setup(
    name="push",
    version="",
    packages=["push"],
    install_requires=[
        "wessex>=1.3.1",
        "paramiko",
        "dnspython",
    ],
    entry_points={
        "console_scripts": [
            "push = push.main:main",
        ]
    }
)
