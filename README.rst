=============================
django-nsync
=============================

.. image:: https://badge.fury.io/py/django-nsync.png
    :target: https://badge.fury.io/py/django-nsync

.. image:: https://travis-ci.org/andrewdodd/django-nsync.png?branch=master
    :target: https://travis-ci.org/andrewdodd/django-nsync

.. image:: https://codecov.io/github/andrewdodd/django-nsync/coverage.svg?branch=master
   :target: https://codecov.io/github/andrewdodd/django-nsync?branch=master
   :alt: Coverage

Django NSync provides a simple way to keep your Django Model data 'n-sync with N external systems.

Features
--------
Includes:

- Synchronise models with data from external systems

  - Create, update or delete model objects
  - Modify relational fields
  - Allow multiple systems to modify the same model object
  
- CSV file support out of the box

  - Ships with commands to process a single CSV file or multiple CSV files

- No need for more code

  - Nsync does not require you to inherit from special classes, add 'model mapping' objects or really define anything in Python

Not-included:

- Export (to CSV or anything else for that matter)

  - There are other packages that can do this
  - Why do you want the data out? Isn't that what your application is for? ;-)

- Admin integration

  - There isn't much to this package, if you want to add the models to your admin pages it is probably better if you do it (that's what I've done in my use case)

Not-yet included:

- Other file formats out of the box

  - Love it or hate it, CSV is ubiquitous and simple (its limitations also force simplicity)
  - The CSV handling part is separated from the true NSync part, so feel free to write your own lyrics-from-wav-file importer.

- Intricate data format handling

  - E.g. parsing date times etc
  - This can be side-stepped by creating ``@property`` annotated handlers though (see the examples from more info)


Documentation
-------------

The full documentation is at https://django-nsync.readthedocs.org.


Credits
---------

Tools used in rendering this package:

*  Cookiecutter_ Used to create the initial repot
*  `cookiecutter-pypackage`_ Used by Cookiecutter_ to create the initial repo

For helping me make sense of the python pacakging world (and the bad practices codified in some of the tools/blogs out there):

* `Hynek Schlawack`_ Whose blog posts on packaging Python apps etc were indispensible
* `Ionel Cristian Maries`_ (sorry, too lazy for unicode) Whose blog post on python packaging was also indispensible

.. _`Hynek Schlawack`: https://hynek.me
.. _`Ionel Cristian Maries`: http://blog.ionelmc.ro/
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-pypackage`: https://github.com/pydanny/cookiecutter-djangopackage

