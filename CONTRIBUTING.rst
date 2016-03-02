
Contributing
============

We welcome and encourage contributions using Github issues to describe
changes and pull requests to make changes to code. We aim for code that
is readable, documented, tested, and reusable.



Steps for contributing to epctk
-------------------------------

We follow the common fork->pull request workflow for accepting contributions.
We require contributions to be accompanied by documentation and unit tests and
for changes to be tracked using github issues.

The process roughly goes like this:


1. Choose a github issue to work on. If none exists which describes the changes 
   you want to make, please write one detailing the problem you aim to solve or
   the feature you want to add.
2. Fork the project
3. Checkout the code from github
4. Create a new branch to work on. This will help with organisation.
5. Make your changes, following the coding guidelines for style and testing described below.
6. Create a pull request. See the Github documentation.

We will review pull requests and aim to ensure that all tests pass.


Important note on tests
-----------------------

Internally, we use test cases provided by BRE. However these cannot
be made public at the moment. Testing against these cases will therefore
be performed in a private repository. Therefore, pull requests may initially
be accepted, to be later rejected if they do not pass internal testing.



Coding guidelines
-----------------

Code should be formatted according to the `Python PEP8 <https://www.python.org/dev/peps/pep-0008/>`_
guidelines, with the exception that lines should merely be of "reasonable" length (80 - 120 characters). 
In general, readability trumps line length.

Documentation is **not optional**! Please follow the 
`Google python documentation <http://google.github.io/styleguide/pyguide.html?showone=Comments#Comments>`_
style for documentation comments in modules, functions, classes, and methods.
In addition, project-wide documentation is created with Sphinx, using 
"narrative" style documentation written in the ``.rst`` format files in the ``doc/`` folder.
 
Code should be covered by **unit tests**, to be added in the ``tests/`` folder. Unit tests
should be written for new functionality and for "public" apis (ones that users of the package
are expected to access). The project aims to run under a continuous integration model - every
change will be tested automatically as new code is uploaded to ensure that no errors are 
introduced which break working code.

Code should be as simple as possible, but no simpler - follow the Python
recommendation that "Simple is better than complex, but complex is better than complicated".
Aim for descriptive variable names, intuitive logic flow, straightforward architecture.

Package dependencies are defined in setup.py and requirements.txt. If you add a dependency,
add it to both theses files - just be name in setup.py and with a recommended version
in requirements.txt. See `here <https://caremad.io/2013/07/setup-vs-requirement/>`_ for
more information on how to do this.



Project Layout
--------------

The important folders are:

- ``epctk`` : the main source folder for the epctk library.
- ``doc`` : the documentation folder
- ``tests`` : containtin all the unit tests
- ``scripts`` : containing command-line style utilites and apps, which use epctk library for their functionality

Please note the distinction between the epctk "library", which should be used
as a python package (imported into other scripts) and the "scripts", which
should contain "app" style code - scripts to be run from the command line
for example.


Building documentation pages
----------------------------

Currently, the documentation is built as a webpage and hosted using github-pages
for simplicity, following the method described `here <http://lucasbardella.com/blog/2010/02/hosting-your-sphinx-docs-in-github>`_.
In summary, you must checkout the gh-pages branch into a new folder separate
from the folder you normally edit epctk in and set Sphinx to output the generated
html pages into that folder by setting the ``BUILDDIR`` option. Generate the page
and commit and push the result to gh-pages.

Notes:

- Do not delete the ``.nojekyll`` file.


Code editors and IDEs
---------------------

This project is developed using PyCharm community edition. Using this editor will make it easier
for us to troubleshoot problems in getting set up.


Contributors
============

Andy Stone (original author)

Jonathan Chambers (current maintainer) jonathan.chambers.13 AT ucl.ac.uk