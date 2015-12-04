Installation
------------

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

