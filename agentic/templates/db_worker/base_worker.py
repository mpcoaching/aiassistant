# Base class for all data-driven microservices
class BaseDataWorker:
    def __init__(self, db_connection):
        self.db = db_connection

    def call_procedure(self, proc_name, params):
        # Deterministic execution of stored procedures
        # This ensures consistency and security
        return self.db.execute(f"CALL {proc_name}({params})")

# Future services will inherit from this
# This ensures separation of concerns and maintainability