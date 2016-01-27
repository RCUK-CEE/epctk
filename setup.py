from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='epc_tk',
      version='0.1',
      description='Tools for running EPC/SAP tests on dwellings',
      long_description='Tools for running EPC/SAP tests on dwellings',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
      ],
      keywords='epc energy uk',
      # url='http://github.com/storborg/funniest',
      author='Jonathan Chambesr',
      author_email='jonathan.chambers.13@ucl.ac.uk',
      license='MIT',
      packages=['sap'],
      install_requires=[
          'yaml',
          'numpy', 'pyparsing'
      ],
      include_package_data=True,
      zip_safe=False)