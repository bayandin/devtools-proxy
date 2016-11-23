import os
import re

from pip.req import parse_requirements
from setuptools import setup, find_packages


def requirements_from_file(filename):
    requirements = []
    for r in parse_requirements(filename, session='fake'):
        if r.match_markers():
            requirements.append(str(r.req))
    return requirements


here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'devtools', '__init__.py'), encoding='utf-8') as f:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$", f.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version')

setup(
    name='devtools-proxy',

    version=version,

    description='DevTools Proxy',
    long_description='DevTools Proxy',

    url='https://github.com/bayandin/devtools-proxy',

    author='Alexander Bayandin',
    author_email='a.bayandin@gmail.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        # 'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python',
        'Topic :: Software Development :: Testing',
    ],

    keywords='selenium chrome chromedriver devtools',

    packages=find_packages(exclude=['tests', 'tests.*']),

    install_requires=requirements_from_file('requirements.txt'),

    package_data={
        'devtools': [
            'chrome-wrapper.sh',
        ],
    },

    entry_points={
        'console_scripts': [
            'devtools-proxy=devtools.proxy:main',
        ],
    },
)
