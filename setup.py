"""Sets up the utopya package, test dependencies, and command line scripts"""

from setuptools import setup, find_packages

# Dependency lists
INSTALL_DEPS = ['numpy>=1.13',
                'PyYAML>=3.12,<4.0',
                'coloredlogs>=10.0',
                # only required for testing
                'pytest>=3.4.0',
                'pytest-cov>=2.5.1',
                # From private repositories:
                # NOTE Versions need also be set in python/CMakeLists.txt
                'paramspace>=1.1.1,<2.0',  # TODO migrate to >=2.0
                'dantro>=0.3.2,<0.4'       # TODO migrate to >=0.4
                ]

setup(name='utopya',
      #
      # Package information
      version='0.1.0-pre.1',
      # NOTE This needs to correspond to utopya.__init__.__version__
      description='The Utopia frontend package.',
      url='https://ts-gitlab.iup.uni-heidelberg.de/utopia/utopia',
      classifiers=[
          'Programming Language :: Python :: 3.6',
          'Topic :: Utilities'
      ],
      #
      # Package content and dependencies
      packages=find_packages(exclude=["*.test", "*.test.*", "test.*", "test"]),
      package_data=dict(utopya=["cfg/*.yml"]),
      install_requires=INSTALL_DEPS,
      test_suite='py.test',
      #
      # Command line scripts, installed into the virtual environment
      scripts=['bin/utopia']
      )
