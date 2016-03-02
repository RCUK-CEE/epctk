.. image:: https://travis-ci.org/RCUK-CEE/epctk.svg?branch=master
    :target: https://travis-ci.org/RCUK-CEE/epctk


The UK EPC Toolkit: epctk
=========================

This project aims to be a free and open source implementation of
the UK Energy Performance Certificate and underlying RdSAP and SAP
models for domestic energy consumption in the UK.

The target spec implementation is currently SAP 2009, with the intention
of adding newer versions in the future.

It is written in Python (version 3.4+) for easy integration with other
data processing code, with the aim of enabling a variety of workflows.
Particular attention will be given enabling highly automated workflows
with large datasets. To acheive this goal a number of features are required
(which are currently at various stages of completion)

- Implementation of SAP and RdSAP models
- Implementation of model-based EPC outputs
- Standardised data input with well defined input schema
- Adapter code for common data sources
- Reusable, documented and unit-tested code


Installation
============

This project requires the `numpy` and `yaml` libraries, optionally the `pyparsing` library.
It does not yet support installation as a Python library, instead clone, fork, or download the project
and work in the source code folder.


Usage
=====

General data loading and validation is work in progress. Currently, epctk is able
to load SAP dwelling definitions from Yaml files. For example code, see the
 `sapcli.py` script in the `scripts` folder.



Example Yaml files exist but are not yet authorised to be shared publicly.
Contact the authors for details.


License
=======

This code is published under the Educational Community License, Version 2.0.
This is a modified version of the popular Apache Public License 2.0 with
clauses related to educational institution-specific IP issues.