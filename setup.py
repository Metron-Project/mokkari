"""Setup file for mokkari"""
from setuptools import find_packages, setup


setup(
    name="mokkari",
    version="0.0.1",
    description="Python wrapper for Metron API ",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Brian Pepple",
    author_email="bdpepple@gmail.com",
    url="https://github.com/bpepple/mokkari",
    license="GPLv3",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
    install_requires=[],
    entry_points={},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    keywords=["comics", "comic", "metadata"],
)
