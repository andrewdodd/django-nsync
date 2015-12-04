Overview
========

.. include:: ./features.rst

Yeah, yeah, but whats the point?
--------------------------------
It is quite common to need to load information from other computer systems into your Django 
application. There are also many ways to do this (manually, via a Restful API, through SQL/database
cleverness) and there are a large number of existing tools to do this (see below).

However, often one must obtain and synchronise information about a model object from multiple 
information sources (e.g. the HR system, the ERP, that cool new Web API, Dave's spreadsheet), and
continue to do it in order to keep one's Django app running properly. This project allows you to do 
just that.


Similar projects
----------------

There are a number of projects that are similar in nature but are (I believe) unsuitable for the
reasons listed;

* `django-synchro`_ - Focussed on the synchonisation between databases (e.g. production &
  fail-over, production & testing)
  - This is quite a 'full on' project, and it is mainly focussed on synchronising two Django
    applications, not dispirate systems
* `django-external-data-sync`_ - This is quite close in purpose (I think, I didn't look at it too
  closely yet) to ``django-nsync``, which is periodically synchronising with external data
  - Focusses on the infrastructure surrounding the 'synchronisation'
  - Does not provide any synchronisation functions (you must subclass `Synchronizer`)
  - Not packaged on PyPI
* `django-mapped-fields`_ - Provides form fields to map structured data to models
  - Seems ok (I didn't really look too closely)
  - Not designed for automated operation (i.e. it is about a Django Form workflow)
* `django-csvimport`_ - A generic importer tool for uploading CSV files to populate data
  - Extends the Admin Interface functionality, not really automated
* `django-import-export`_ - Application and library for importing and exporting 
  - Looks to be excellent, certainly close in concept to ``django-nsync``
  - Requires the creation of `ModelResource` subtypes to marshall the importing (i.e. requires code
    changes)
  - Focussed more on the 'Admin interface' interactions
  - (NB: Now that I'm writing up these docs and looking at this project it seems that they are
    quite similar)

.. _`django-synchro`: https://github.com/zlorf/django-synchro
.. _`django-external-data-sync`: https://github.com/596acres/django-external-data-sync
.. _`django-mapped-fields`: https://github.com/mypebble/mapped-fields
.. _`django-csvimport`: https://github.com/edcrewe/django-csvimport
.. _`django-import-export`: https://django-import-export.readthedocs.org/en/latest/

Concepts
========

Model Actions
-------------
- Create
- Update
- Delete
- Force


Field Options
-------------
- Matches field names (for create & update actions)
- Referential fields
  - ``=>`` used to indicate
  - Need multiple fields to deal with ambiguity


ExternalSystem & ExternalKeyMapping
-----------------------------------
 - If supplied, the "key" will create a key mapping for the system that points to the 'app' object


Which object to act on?
-----------------------
 - Always acts on a single object
   - Multi-object actions "could" be possible, but they are hard and probably not worth the trouble
     - i.e. some very general cases
     - computers are good at doing things quickly, get a computer to write the 'same' thing for the
       multiple targets and to execuse the request against multiple objects
 - Found by the "match_field" value
   - Found by looking for an object with the value for the 'match_field_name' in the 'values'
     provided (huh? right, it'll make sense in the examples)
   - NB: No multi-value lookup at the moment, hence you need a 'unique' field to find your objects

But how?
--------
Easiest with a CSV (because there is already a CSV management command).

For example, you might have the following dumped from the HR system.

.. include:: ./examples.rst
    :start-after: example-persons-external-csv-begin
    :end-before: example-persons-external-csv-end


