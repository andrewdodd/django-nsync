
Examples
========

The following are some examples of using the Nsync functionality. The
following Django models will be used as the target models::

    class Person(models.Model):
        first_name = models.CharField(
            blank=False,
            max_length=50,
            verbose_name='First Name'
        )
        last_name = models.CharField(
            blank=False,
            max_length=50,
            verbose_name='Last Name'
        )
        age = models.IntegerField(blank=True, null=True)

        hair_colour = models.CharField(
            blank=False,
            max_length=50,
            default="Unknown")


    class House(models.Model):
        address = models.CharField(max_length=100)
        country = models.CharField(max_length=100, blank=True)
        floors = models.IntegerField(blank=True, null=True)
        owner = models.ForeignKey(TestPerson, blank=True, null=True)


Example - Basic
---------------

Using this file:

.. csv-table:: persons.csv
    :header: "action_flags", "match_on", "first_name", "last_name", "employee_id"

    "cu","employee_id","Andrew","Dodd","EMP1111"
    "d*","employee_id","Some","Other-Guy","EMP2222"
    "cu","employee_id","Captain","Planet","EMP3333"
    "u*","employee_id","C.","Batman","EMP1234"

And running this command::

    > python manage.py syncfile TestSystem myapp Person persons.csv

Would:
 - Create and/or update ``myapp.Person`` objects with Employee Ids EMP1111 & EMP3333. However, it would not update the two name fields if the objects already existed with non-blank fields.
 - Delete any ``myapp.Person`` objects with Employee Id EMP2222.
 - If a person with Employee Id EMP1234 exists, then it will forcibly update the name fields to 'C.' and 'Batman' respectively.

NB it would also:
 - Create an ``nsync.ExternalSystem`` object with the name TestSystem, as the default is to create missing external systems. However, because there are no ``external_key`` values, no ``ExternalKeyMapping`` objects would be created.

Example - Basic with External Ids
---------------------------------

Using this file:

.. csv-table:: persons.csv
    :header: "external_key", "action_flags", "match_on", "first_name", "last_name", "employee_id"

    12212281,"cu","employee_id","Andrew","Dodd","EMP1111"
    43719289,"d*","employee_id","Some","Other-Guy","EMP2222"
    99999999,"cu","employee_id","Captain","Planet","EMP3333"
    11235813,"u*","employee_id","C.","Batman","EMP1234"

And running this command::

    > python manage.py syncfile TestSystem myapp Person persons.csv

Would:
 - Perform all of steps in the 'Plain file' example
 - Delete any ``ExternalKeyMapping`` objects that are for the 'TestSystem' and have the external key '43719289' (i.e. the record for Some Other-Guy).
 - Create or update ``ExternalKeyMapping`` objects for each of the other three ``myapp.Person`` objects, which contain the ``external_key`` value.


Example - Basic with multiple match fields
------------------------------------------

Sometimes you might not have a 'unique' field to find your objects with (like 'Employee Id'). In this instance, you can specify multiple fields for finding your object (separated with a space, ' ').

For example, using this file:

.. csv-table:: persons.csv
    :header: "action_flags", "match_on", "first_name", "last_name", "age"

    "cu*","first_name last_name","Michael","Martin","30"
    "cu*","first_name last_name","Martin","Martin","40"
    "cu*","first_name last_name","Michael","Michael","50"
    "cu*","first_name last_name","Martin","Michael","60"

And running this command::

    > python manage.py syncfile TestSystem myapp Person persons.csv

Would:
 - Create and/or update four persons of various "Michael" and "Martin" name combinations
 - Ensure they are updated/created with the correct age!

Example - Two or more systems
-----------------------------
This is probably the main purpose of this library: the ability to
synchronise from multiple systems.

Perhaps we need to synchronise from two data sources on housing information,
one is the 'when built' information and the other is the 'renovations'
information.

As-built data:

.. csv-table:: AsBuiltDB_myapp_House.csv
    :header: "external_key", "action_flags", "match_on", "address", "country", "floors"

    111,"cu","address","221B Baker Street","England",1
    222,"cu","address","Wayne Manor","Gotham City",2

Renovated data:

.. csv-table:: RenovationsDB_myapp_House.csv
    :header: "external_key", "action_flags", "match_on", "address", "floors"

    ABC123,"u*","address","221B Baker Street",2
    ABC456,"u*","address","Wayne Manor",4
    FOX123,"u*","address","742 Evergreen Terrace",2


And running this command::

    > python manage.py syncfiles AsBuiltDB_myapp_House.csv RenovationsDB_myapp_House.csv

Would:
 - Use the **mutliple file command**, ``syncfiles``, to perform multiple updates in one command
 - Create the two houses from the 'AsBuilt' file
 - Only update the ``country`` values of the two houses from the 'AsBuilt' file IFF the objects already existed but they did not have a value for ``country``
 - Forcibly set the ``floors`` attribute for the first two houses in the 'Renovations' file.
 - Create 4 ``ExternalKeyMapping`` objects:

    +---------------+--------+----------------------+
    | External      | Ext.   |  House Object        |
    | System        | Key    |                      |
    +===============+========+======================+
    | AsBuiltDB     | 111    |                      |
    +---------------+--------+  212B Baker Street   |
    | RenovationsDB | ABC123 |                      |
    +---------------+--------+----------------------+
    | AsBuiltDB     | 222    |                      |
    +---------------+--------+  Wayne Manor         |
    | RenovationsDB | ABC456 |                      |
    +---------------+--------+----------------------+
 - Only update the ``floors`` attribute for "742 Evergreen Terrace" if the house already exists (and would then also create an ``ExternalKeyMapping``)


Example - Referential fields
----------------------------
You can also manage referential fields with Nsync. For example, if you had the following people:

.. csv-table:: Examples_myapp_Person.csv
    :header: "external_key", "action_flags", "match_on", "first_name", "last_name", "employee_id"

    1111,"cu*","employee_id","Homer","Simpson","EMP1"
    2222,"cu*","employee_id","Bruce","Wayne","EMP2"
    3333,"cu*","employee_id","John","Wayne","EMP3"

You could set their houses with a file like this:

.. csv-table:: Examples_myapp_House.csv
    :header: "external_key", "action_flags", "match_on", "address", "owner=>first_name"

    ABC456,"cu*","address","Wayne Manor","Bruce"
    FOX123,"cu*","address","742 Evergreen Terrace","Homer"

The **"=>"** is used by Nsync to follow the the related field on the provided object.

Example - Referential field gotchas
-----------------------------------
The referential field update will ONLY be performed if the referred-to-fields target a single object. For example, if you had the following list of people:

.. csv-table:: Examples_myapp_Person.csv
    :header: "external_key", "action_flags", "match_on", "first_name", "last_name", "employee_id"

    1111,"cu*","employee_id","Homer","Simpson","EMP1"
    2222,"cu*","employee_id","Homer","The Greek","EMP2"
    3333,"cu*","employee_id","Bruce","Wayne","EMP3"
    4444,"cu*","employee_id","Bruce","Lee","EMP4"
    5555,"cu*","employee_id","John","Wayne","EMP5"
    6666,"cu*","employee_id","Marge","Simpson","EMP6"

The ``owner=>first_name`` from the previous example is insufficient to pick out a single person to link a house to (there are 2 Homers and 2 Bruces). Using just the ``employee_id`` field would work, but that piece of information may not be available in the system for houses.

Nsync allows you to specify multiple fields to use in order to 'filter' the correct object to create the link with. In this instance, this file would perform correctly:

.. csv-table:: Examples_myapp_House.csv
    :header: "external_key", "action_flags", "match_on", "address", "owner=>first_name", "owner=>last_name"

    ABC456,"cu*","address","Wayne Manor","Bruce","Wayne"
    FOX123,"cu*","address","742 Evergreen Terrace","Homer","Simpson"


Example - Complex Fields
------------------------
If you want a more complex update you can:
 - Write an extension to Nsync and submit a Pull Request! OR
 - Extend your Django model with a custom setter

If your Person model has a photo ImageField, then you could add a custom handler to update the photo based on a provided file path::

    class Person(models.Model):
        ...
        photo = models.ImageField(
            blank = True,
            null = True,
            max_length = 200,
            upload_to = 'person_photos',
        )
        ...

        @photo_filename.setter
        def photo_filename(self, file_path):
            ...
            Do the processing of the file to update the model

And then supply the photos with a file sync file like:

.. csv-table:: persons.csv
    :header: "action_flags", "match_on", "first_name", "last_name", "employee_id", "photo_filename"

    "cu*","employee_id","Andrew","Dodd","EMP1111","/tmp/photos/ugly_headshot.jpg"


Example - Update uses external key mapping over matched object
--------------------------------------------------------------
This is an example that is to do with the changes for `Issue 1`_

If Nsync is 'updating' objects but their 'match fields' change, Nsync will still update the 'correct' object.

A common occurrence of this is if the sync data is being produced from a database and an in-row update occurs which changes the match fields but leaves the 'external key' (i.e. an SQL 'UPDATE ... WHERE ...' statement).

E.g. A person table might look like this:

================== =============== ====
ID (a DB sequence) Employee Number Name
================== =============== ====
10123              EMP001          Andrew Dodd
================== =============== ====

This could be used to produce an Nsync input CSV like this:

============ ============ =============== =============== ====
external_key action_flags match_on        employee_number name
============ ============ =============== =============== ====
10123        cu*          employee_number EMP001          Andrew Dodd
============ ============ =============== =============== ====

This would result in an "Andrew Dodd, EMP001" Person object being created and/or updated with an `ExternalKeyMapping` object holding the '10123' id and a link to Andrew.

If Andrew became a contractor instead of an employee, perhaps the table could be updated to look like this:

================== =============== ====
ID (a DB sequence) Employee Number Name
================== =============== ====
10123              CONT999         Andrew Dodd
================== =============== ====

This would then produce an Nsync input CSV like this:

============ ============ =============== =============== ====
external_key action_flags match_on        employee_number name
============ ============ =============== =============== ====
10123        cu*          employee_number CONT999         Andrew Dodd
============ ============ =============== =============== ====

Nsync will use the `ExternalKeyMapping` object if it is available instead of relying on the 'match fields'. In this case, the
resulting action will cause the Andrew Dodd object to change its 'employee_number'. This is instead of Nsync using the 
'employee_number' for finding Andrew.

NB: In this instance, Nsync will also delete any objects that have the 'new' match field but are not pointed to by the external key.

.. _`Issue 1`: https://github.com/andrewdodd/django-nsync/issues/1


Example - Delete tricks
-----------------------
This is a list of tricky / gotchas to be aware of when deleting objects.

When syncing from external systems that have external key mappings, it is probably best to use the 'unforced delete'. This ensures that an object is not removed until all of the external systems think it should be removed.

If using 'forced delete', beware that (depending on which sync policy you use) you may end up with different systems fighting over the existence of an object (i.e. one system creating the object, then another deleting it in the same sync).

A system without external key mappings cannot delete objects if it uses an 'unforced delete'. The reason for this is that the 'unforced delete' only removes the model object IF AND ONLY IF it is the last remaining external key mapping. Thus, if a system without external key mappings is the source-of-truth for the removal of an object, you must use the 'forced delete' for it to be able to remove the objects.


Alternative Sync Policies
-------------------------
The out-of-the-box sync policies are pretty straightforward and are probably worth a read (see the ``policies.py`` file). The system is made so that it is pretty easy for you to define your own custom policy and write a command (similar to the ones in Nsync) to use it.

Some examples of alternative policies might be:
 - Run deletes before creates and updates
 - Search and execute certain actions before all others


