#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py
========
Установщик пакета для распространения через PyPI / GitHub.

Использование:
    pip install -e .          # установить в режиме разработки
    python setup.py sdist     # создать дистрибутив
    python setup.py install   # установить локально

Author: abral syndicate
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="majiro-script-converter",
    version="1.0.0",
    author="abral syndicate",
    description="Bidirectional converter for Majiro engine .mjo script files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/majiro-script-converter",
    py_modules=["mjo_converter"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Disassemblers",
        "Topic :: Games/Entertainment",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "mjo-convert=mjo_converter:main",
        ],
    },
)
