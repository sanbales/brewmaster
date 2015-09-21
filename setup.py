#!/usr/bin/env python
from pip.req import parse_requirements
from pip.download import PipSession
from setuptools import setup, find_packages


install_reqs = parse_requirements('requirements.txt', session=PipSession())
requirements = [str(ir.req) for ir in install_reqs]

setup(name='brewmaster',
      version='0.0.2',
      description='A model-based framework to assist breweries in optimizing their processes.',
      long_description=open('README.md').read(),
      download_url='https://github.com/sanbales/brewmaster',
      keywords='brewing beer process optimization',
      author='Santiago Balestrini-Robinson',
      author_email='sanbales@gmail.com',
      url='https://github.com/sanbales/brewmaster',
      license='MIT',
      packages=find_packages(),
      install_requires=requirements,
      classifiers=['Development Status :: 2 - Pre-Alpha',
                   'License :: OSI Approved :: MIT License',
                   'Natural Language :: English',
                   'Framework :: IPython',
                   'Intended Audience :: Other Audience',
                   'Operating System :: MacOS :: MacOS X',
                   'Operating System :: POSIX :: Linux',
                   'Operating System :: Microsoft :: Windows',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3.4',
                   'Topic :: Office/Business'
                   ],
      py_modules=['brewmaster'])
