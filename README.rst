=============================
django-nsync
=============================

.. image:: https://badge.fury.io/py/django-nsync.png
    :target: https://badge.fury.io/py/django-nsync

.. image:: https://travis-ci.org/andrewdodd/django-nsync.png?branch=master
    :target: https://travis-ci.org/andrewdodd/django-nsync

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

Not-included:

- Export (to CSV or anything else for that matter)

  - There are other packages that can do this
  - Why do you want the data out? Isn't that what your application is for? :-p

- Admin integration

  - There isn't much to this package, if you want to add the models to your admin pages it is probably better if you do it (that's what I've done in my use case)

Not-yet included:

- Other file formats out of the box

  - Love it or hate it, CSV is ubiquitous and simple (its limitations also force simplicity)
  - The CSV handling part is separated from the true NSync part, so feel free to write your own lyrics-from-wav-file importer.

- Intricate data format handling

  - E.g. parsing date times etc
  - This can be side-stepped by creating ``@property`` annotated handlers though (see the examples from more info)

Installation
------------
To get started using ``django-nsync``, install it with ``pip``::

    $ pip install django-nsync

Add ``"nsync"`` to your project's ``INSTALLED_APPS`` setting. E.g.::

    INSTALLED_APPS += (
        'nsync',
    )

Run ``python manage.py migrate`` to create the Django-Nsync models.

You will now have in your application:

- An ``ExternalSystem`` model, used to represent 'where' information is synchronising from
- An ``ExternalKeyMapping`` model, used to record the mappings from an ``ExternalSystem``'s key for a model object, to the actual model object internally
- Two 'built-in' commands for synchronising data with:

  - `syncfile` - Which synchronises a single file, but allows the user to specify the ``ExternalSystem``, the ``Model`` and the ``application`` explicity
  - `syncfiles` - Which synchronises multiple files, but uses a Regular Expression to find the required information about the ``ExternalSystem``, the ``Model`` and the ``application``.

Create your CSV file(s) with the data you need to synchronise with::

    first_name,last_name,employee_id,action_flags,match_field_name
    Andrew,Dodd,E1234,cu,employee_id
    Some,Other-Guy,E4321,d,employee_id


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
.. _`Ionel Cristian Maries`: http://blog.ionelmc.ro/
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-pypackage`: https://github.com/pydanny/cookiecutter-djangopackage

