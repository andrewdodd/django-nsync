#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re


# Start of section from Hynek
# https://github.com/hynek/attrs/blob/master/setup.py
import codecs
from setuptools import setup, find_packages

###############################################################################

PACKAGES = find_packages(where="src")
META_PATH = os.path.join("src", "nsync", "__init__.py")
KEYWORDS = []
CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Framework :: Django',
    'Framework :: Django :: 1.7',
    'Framework :: Django :: 1.8',
    'Framework :: Django :: 2.0',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Natural Language :: English',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
]
INSTALL_REQUIRES = ['Django>=1.8']
TEST_SUITE = 'runtests.run_tests'
TESTS_REQUIRE = ['Django>=1.8']

###############################################################################

HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    """
    Build an absolute path from *parts* and and return the contents of the
    resulting file.  Assume UTF-8 encoding.
    """
    with codecs.open(os.path.join(HERE, *parts), "rb", "utf-8") as f:
        return f.read()


META_FILE = read(META_PATH)


def find_meta(meta):
    """
    Extract __*meta*__ from META_FILE.
    """
    meta_match = re.search(
        r"^__{meta}__ = ['\"]([^'\"]*)['\"]".format(meta=meta),
        META_FILE, re.M
    )
    if meta_match:
        return meta_match.group(1)
    raise RuntimeError("Unable to find __{meta}__ string.".format(meta=meta))

# End of section from Hynek

readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name=find_meta("title"),
    description=find_meta("description"),
    license=find_meta("license"),
    url=find_meta("uri"),
    version=find_meta("version"),
    author=find_meta("author"),
    author_email=find_meta("email"),
    maintainer=find_meta("author"),
    maintainer_email=find_meta("email"),
    keywords=KEYWORDS,
    long_description=read("README.rst"),
    packages=PACKAGES,
    package_dir={"": "src"},
    zip_safe=False,
    classifiers=CLASSIFIERS,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    test_suite=TEST_SUITE,
)
