=============================
django-nsync
=============================

.. image:: https://badge.fury.io/py/django-nsync.png
    :target: https://badge.fury.io/py/django-nsync

.. image:: https://travis-ci.org/andrewdodd/django-nsync.png?branch=master
    :target: https://travis-ci.org/andrewdodd/django-nsync

Django NSync provides a simple way to keep your Django Model data 'n-sync with N external systems.

.. include:: ./docs/features.rst

Quickstart
----------

.. include:: ./docs/installation.rst
    :start-after: installation-begin
    :end-before: installation-result

Create your CSV file(s) with the data you need to synchronise with
.. include:: ./docs/examples.rst
    :start-after: example-persons-noexternal-txt-begin
    :end-before: example-persons-noexternal-txt-end

Run one of the built in commands::

    > python manage.py syncfile 'HRSystem' 'prizes' 'Winner' /tmp/the/file.csv

Check your application to see that Andrew Dodd is now a Winner and that other guy was deleted.

    

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
.. _'Ionel Cristian Maries': http://blog.ionelmc.ro/
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-pypackage`: https://github.com/pydanny/cookiecutter-djangopackage

