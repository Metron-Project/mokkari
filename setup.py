"""Setup file for mokkari"""
from setuptools import find_packages, setup

import mokkari


setup(
    name="mokkari",
    version=mokkari.VERSION,
    description="Python wrapper for Metron API ",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author="Brian Pepple",
    author_email="bdpepple@gmail.com",
    url="https://github.com/bpepple/mokkari",
    license="GPLv3",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
    install_requires=["marshmallow", "requests", "ratelimit"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Topic :: Internet",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    keywords=["comics", "comic", "metadata"],
)
