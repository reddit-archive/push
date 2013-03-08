#!/usr/bin/python

from setuptools import setup

setup(
    name="push",
    version="",
    packages=["push"],
    install_requires=[
        "wessex>=1.5",
        "paramiko",
    ],
    extras_require={
        "DNS": [
            "dnspython",
        ],
        "ZooKeeper": [
            "kazoo",
        ],
    },
    entry_points={
        "console_scripts": [
            "push = push.main:main",
        ]
    }
)
