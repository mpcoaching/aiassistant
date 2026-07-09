Pattern: Data Mapper.
Definition: Decouples the in-memory domain objects from the database schema.
Implementation Rule: All logic involving the translation between the object and the stored procedure must reside in a Mapper class. The business layer must NEVER know about stored procedures or DB parameters.