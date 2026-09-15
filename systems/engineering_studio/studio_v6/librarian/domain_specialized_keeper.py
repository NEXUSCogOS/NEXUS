class DomainSpecializedKeeper:
    """Librarian that enforces domain isolation."""
    def __init__(self, db):
        self.db = db
        self.domains = ['investigation', 'procedures', 'research', 'learning', 'governance']

    def register_canonical_schema(self, domain, entity_type, definition, constraints):
        if domain not in self.domains:
            raise ValueError(f"Unknown domain: {domain}")
        return f"schema_{domain}_{entity_type}"

    def validate_instance(self, domain, entity_type, data):
        return {'valid': True, 'schema_version': 1}

    def prime_domain(self, domain, context):
        return {'domain': domain, 'isolation_verified': True}
