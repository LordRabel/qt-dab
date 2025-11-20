#!/usr/bin/env python3
"""
Setup script for Python DAB Receiver
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="python-dab-receiver",
    version="1.0.0",
    author="Based on qt-dab",
    description="DAB Receiver: RTL-SDR to Constellation Diagram in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JvanKatwijk/qt-dab",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Topic :: Communications :: Ham Radio",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pyrtlsdr>=0.2.92",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "matplotlib>=3.4.0",
    ],
    extras_require={
        "dev": ["pytest>=6.0", "black>=21.0", "flake8>=3.9"],
        "performance": ["numba>=0.54.0"],
    },
    entry_points={
        "console_scripts": [
            "dab-constellation=dab_constellation_viewer:main",
        ],
    },
)
