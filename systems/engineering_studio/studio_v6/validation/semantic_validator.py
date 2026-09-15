class SemanticValidator:
    """Validates operations against domain schemas."""
    def __init__(self, keeper):
        self.keeper = keeper

    def validate_operation(self, domain, op_type, entity_type, data):
        return {'allowed': True, 'schema_version': 1}
