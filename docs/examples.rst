
Examples
========

Example - Plain file
--------------------

.. example-persons-noexternal-txt-begin
::
    first_name,last_name,employee_id,action_flags,match_field_name
    Andrew,Dodd,E1234,cu,employee_id
    Some,Other-Guy,E4321,d,employee_id

.. example-persons-noexternal-txt-end

.. example-persons-external-csv-begin
.. csv-table:: persons.csv
    :header: "external_key", "action_flags", "match_field_name", "first_name", "last_name", "employee_id"

    1221228,"cu","employee_id","Andrew","Dodd","EMP1111"
    4371928,"d","employee_id","Some","Other-Guy","EMP2222"
.. example-persons-external-csv-end

