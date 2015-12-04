
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

