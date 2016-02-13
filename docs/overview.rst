Overview
========

Yeah, yeah, but whats the point?
--------------------------------
It is quite common to need to load information from other computer systems into your Django 
application. There are also many ways to do this (manually, via a Restful API, through SQL/database
cleverness) and there are a large number of existing tools to do this (see below).

However, often one must obtain and synchronise information about a model object from **multiple 
information sources** (e.g. the HR system, the ERP, that cool new Web API, Dave's spreadsheet), and
**continue to do it** in order to keep one's Django app running properly. This project allows you to do 
just that.


Similar projects
----------------

There are a number of projects that are similar in nature but are (I believe) unsuitable for the
reasons listed;

* `django-synchro`_ - Focussed on the synchonisation between databases (e.g. production &
  fail-over, production & testing)

  - This is quite a 'full on' project, and it is mainly focussed on synchronising two Django
    applications, not disparate systems

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

There are three key model actions (Create, Update, & Delete), and one action modifier (Force).

Create Action
^^^^^^^^^^^^^
This is used to 'create' a model object with the given information. If a matching object is found
is will **NOT** create another one and it will **NOT** modify the existing object.

This action is always considered *'forced'*, so that it will override any non-empty/null defaults.

Update Action
^^^^^^^^^^^^^
This action will look for a model object and, if one is found, update it with the given
information. It will **NOT** create an object.

- If **NOT** forced, the update will only affect fields whose current value is ``None`` or ``''``
- If **forced**, the update will clobber any exiting value for the field

Delete Action
^^^^^^^^^^^^^
This action will look for a model object and, if one is found, attempt to delete it.

- If **forced**, the action will remove the object
- If **NOT** forced, the action will only delete the object if:

  - The target has external key mapping information; AND
  - The key mapping described exists; AND
  - The key mapping points to the corresponding object; AND
  - There are no other key mappings pointing to the object

NB: The *Delete action* will typically also manage the deletion of any corresponding
``ExternalKeyMapping`` objects associated with the object and the particular ``ExternalSystem``
that is performing the sync process (more information will be provided later).

Forced Actions
^^^^^^^^^^^^^^
The option to *force* an action is provided to allow optionality to the synchroniser. It allows
systems that 'might' have useful information but not the 'authoritative' answer to provide
'provisional' information in the sync process.

As mentioned above, the ``force`` option allows the following modifications of behaviour:

 - ``CREATE`` actions - are *always* forced, to ensure they update non-``None`` and non-``''``
   default values
 - For ``UPDATE`` actions - it allows the action to forcibly replace the value in the corresponding
   field, rather than only replacing it if the value is ``None`` or ``''``
 - For ``DELETE`` actions - it allows the action to forcibly delete the model object, even if other
   systems have synchronised links to it

CSV Encodings
^^^^^^^^^^^^^
For use in CSV files (with the built in ``syncfile`` and ``syncfiles`` commands), the CSV file
should include a column with the header ``action_flags``. The values for the field can be:

+-------+-------------------+
| Value | Meaning           |
+=======+===================+
|  c    + Create only       |
+-------+-------------------+
|  u    | Update only       |
+-------+-------------------+
|  d    | Delete only       |
+-------+-------------------+
|  cu   | Create and update |
+-------+-------------------+
|  u*   | Forced update     |
+-------+-------------------+
|  d*   | Forced delete     |
+-------+-------------------+


The following values are pointless / not allowed:

+-------+---------------------+-------------------------------------------+
| Value | Meaning             | Reason                                    |
+=======+=====================+===========================================+
|       | No action           | Pointless, omit the row                   |
+-------+---------------------+-------------------------------------------+
|  c*   + Forced create       | Pointless, all creates are already forced |
+-------+---------------------+-------------------------------------------+
|  cd   | Create and delete   | Illegal, cannot request delete action     |
+-------+---------------------+ with either create or update action.      |
|  ud   | Update and delete   |                                           |
+-------+---------------------+                                           |
|  cud  | Create, update and  |                                           | 
|       | delete              |                                           |
+-------+---------------------+-------------------------------------------+



Which object to act on?
-----------------------
The action uses the provided information to attempt to find (or guarantee the absence of) the
object it should be acting upon. The *'provided information'* is the set of values used to set the
fields in ``CREATE`` or ``UPDATE`` actions (NB: in all three cases it must contain the information
to find the specific object).

Rules / Choices in design
^^^^^^^^^^^^^^^^^^^^^^^^^
The current choices for how this 'selection' behaves are:

 - Always acts on a single object
 - Found by the "``match_on``" value
   
   - Found by looking for an object that has the same 'values' as those provided for the model fields
     specified in the '``match_on``' list of fields. (huh? feeling lost?, it'll make sense in the 
     examples)
   - The '``match_on``' column could be a 'unique' field with which to find your object, OR it could 
     be a list of fields to use to find your object.

- Actions that target mulitple obects "could" be possible, but they are hard and probably not worth
  the trouble

 - This would be trying to address some very general cases, which would be too hard to get logic
   correct for (I feel the risk of doing the wrong thing here accidentally would be too high)
 - Computers are good at doing things quickly, get a computer to write the 'same' thing for the
   multiple targets and to execuse the request against multiple objects

Field Options
-------------
Fields are modified by using the ``setattr()`` built-in Python function. The field to update is
based on the behaviour of this function to set the attribute based on the dictionary of information
provided. **NB:** If the list of values includes 'fields' that are not part of the model object's
definition, they will be ignored (more work to come here)

Referential Fields
^^^^^^^^^^^^^^^^^^
One of the most important features is the ability to update 'referred to' fields, such as
``Person`` object that is assigned a company ``Car`` object.

This is specified by including the field and matchfields in the 'key' side of the values,
concatenated with '``=>``' (you can see the CSV heritage creeping in here). For example, if you had
classes like this::

    class Person(models.Model):
        first_name = models.CharField(
            blank=False,
            max_length=50,
        )
        last_name = models.CharField(
            blank=False,
            max_length=50,
        )
        assigned_car = models.ForeignKey(Car, blank=True, null=True)

    class Car(models.Model):
        rego_number= models.CharField(max_length=10, unique=True)
        name = models.CharField(max_length=50)

You could load the assignment by synchronising with the following file for  ``Person`` model:

.. csv-table:: persons.csv
    :header: "action_flags", "match_on", "first_name", "last_name", "assigned_car=>rego_number"

    "cu","employee_id","Andrew","Dodd","BG29JL"


However, you can also supply multiple inputs to a Referential assignment, which is especially handy
for resolving situations where your models do not have a field that can be used to address them 
uniquely. For example, if you had classes like this instead (which is far more likely)::

    class Person(models.Model):
        first_name = models.CharField(
            blank=False,
            max_length=50,
        )
        last_name = models.CharField(
            blank=False,
            max_length=50,
        )

    class Car(models.Model):
        rego_number= models.CharField(max_length=10, unique=True)
        name = models.CharField(max_length=50)
        assigned_to = models.ForeignKey(Person, blank=True, null=True)

You could load the assignment by synchronising with the following file for  ``Car`` model:

.. csv-table:: cars.csv
    :header: "action_flags", "match_on", "rego_number", "name", "assigned_to=>first_name", "assigned_to=>last_name"

    "cu","rego_number","BG29JL","Herman the Sherman","Andrew","Dodd"


ExternalSystem & ExternalKeyMapping
-----------------------------------
This library also creates some objects to help keep track of the internal model objects modified by
the external systems. With the purpose being to supply a way for users of the library to peform
their own 'reverse' on which internal objects are being touched by which external systems. This is
not particularly interesting, but it is perhaps worth checking out the ``ExternalSystem`` and
``ExternalKeyMapping`` classes.

These classes are also used to decide which 'object' is update if the '``match_on``' fields are 
changed (i.e. by an SQL UPDATE) but the 'external system key' remains the same.


But how?
--------
It is probaby easiest to look at the examples page or have a look at the integration tests for the
two out of the box commands.

