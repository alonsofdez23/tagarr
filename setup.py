import pathlib
from setuptools import setup, find_packages
from tagarr import __version__

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="tagarr",
    version=__version__,
    description="Tagarr tags movies and series in Radarr and Sonarr with their streaming provider names",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/haijeploeg/excludarr",
    author="Haije Ploeg",
    author_email="ploeg.haije@gmail.com",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    license="MIT",
    keywords="tagarr, radarr, sonarr, streaming, tags, netflix, management, library",
    packages=find_packages(exclude=["ez_setup", "tests*"]),
    python_requires=">=3.6, <4",
    install_requires=[
        "typer>=0.4.1",
        "loguru>=0.6.0",
        "rich>=12.4.1",
        "requests>=2.27.1",
        "PyYAML>=6.0",
        "pyarr>=3.1.3",
    ],
    entry_points={
        "console_scripts": [
            "tagarr=tagarr.main:cli",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/haijeploeg/excludarr/issues",
        "Source": "https://github.com/haijeploeg/excludarr",
    },
)
