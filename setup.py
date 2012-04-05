#!/usr/bin/python

from setuptools import setup

setup(
    name="push",
    version="",
    packages=["push"],
    install_requires=[
        "wessex",
        "paramiko",
    ],
    entry_points={
        "console_scripts": [
            "push = push.main:main",
        ]
    }
)
