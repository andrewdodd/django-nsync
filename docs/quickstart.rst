Quickstart
----------

Installation
^^^^^^^^^^^^

.. installation-begin
To get started using ``django-nsync``, install it with ``pip``::

    $ pip install django-nsync

Add ``"nsync"`` to your project's ``INSTALLED_APPS`` setting. E.g.::

    INSTALLED_APPS += (
        'nsync',
    )

Run ``python manage.py migrate`` to create the Django-Nsync models.

.. installation-result

You will now have in your application:

- An ``ExternalSystem`` model, used to represent 'where' information is synchronising from
- An ``ExternalKeyMapping`` model, used to record the mappings from an ``ExternalSystem``'s key for a model object, to the actual model object internally
- Two 'built-in' commands for synchronising data with:

  - `syncfile` - Which synchronises a single file, but allows the user to specify the ``ExternalSystem``, the ``Model`` and the ``application`` explicity
  - `syncfiles` - Which synchronises multiple files, but uses a Regular Expression to find the required information about the ``ExternalSystem``, the ``Model`` and the ``application``.

Usage
^^^^^

Create your CSV file(s) with the data you need to synchronise with::

    first_name,last_name,employee_id,action_flags,match_on
    Andrew,Dodd,E1234,cu,employee_id
    Some,Other-Guy,E4321,d,employee_id


Run one of the built in command (i.e. if you have a "Winner" Django model)s::

    > python manage.py syncfile 'HRSystem' 'prizes' 'Winner' /tmp/the/file.csv

Check your application to see that Andrew Dodd is now a Winner and that other guy was deleted.

**NOTE WELL:** There is no need to write any Python to make this work!
