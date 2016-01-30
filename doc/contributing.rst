Contributing
============





PCDF Files
----------


The PCDF data files are downloaded from BRE. These are regularly updated, however since
they can introduce new categories which are not implemeted in `epctk`, avoid updating them
unnecessarily.
You must also take care with the file encoding: The PCDF files as downloaded from the BRE
site have a non-standard text encoding which
doesn't work nicely with the python data import. They must therefore be re-saved with
correct UTF8 encoding. This can be done by opening the file in a plain-text editor such
as SublimeText and using 'save with encoding' set to UTF8.
