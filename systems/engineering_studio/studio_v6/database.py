"""V6 Database Layer - Real Schema Execution"""
import sqlite3
from pathlib import Path

class V6Database:
    def __init__(self):
        db_path = Path(__file__).parent.parent / "runtime" / "v6_canonical.db"
        self.conn = sqlite3.connect(db_path)
        self.init_schemas()

    def init_schemas(self):
        """Initialize all domain-specialized schema tables"""
        c = self.conn.cursor()

        # Investigation Domain
        c.execute('''CREATE TABLE IF NOT EXISTS investigation_schemas (
            schema_id TEXT PRIMARY KEY,
            entity_type TEXT UNIQUE,
            definition TEXT,
            constraints TEXT,
            domain TEXT DEFAULT 'investigation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Procedure Domain
        c.execute('''CREATE TABLE IF NOT EXISTS procedure_schemas (
            schema_id TEXT PRIMARY KEY,
            entity_type TEXT UNIQUE,
            definition TEXT,
            constraints TEXT,
            domain TEXT DEFAULT 'procedures',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Research Domain
        c.execute('''CREATE TABLE IF NOT EXISTS research_schemas (
            schema_id TEXT PRIMARY KEY,
            entity_type TEXT UNIQUE,
            definition TEXT,
            domain TEXT DEFAULT 'research',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Learning Domain
        c.execute('''CREATE TABLE IF NOT EXISTS learning_schemas (
            schema_id TEXT PRIMARY KEY,
            entity_type TEXT UNIQUE,
            definition TEXT,
            domain TEXT DEFAULT 'learning',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Procedure Outcomes (Real Execution Results)
        c.execute('''CREATE TABLE IF NOT EXISTS procedure_outcomes (
            outcome_id TEXT PRIMARY KEY,
            procedure_name TEXT,
            domain TEXT,
            success BOOLEAN,
            execution_time_ms INT,
            output TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Learned Constraints
        c.execute('''CREATE TABLE IF NOT EXISTS learned_constraints (
            constraint_id TEXT PRIMARY KEY,
            domain TEXT,
            field_name TEXT,
            confidence REAL,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        self.conn.commit()

    def register_schema(self, domain, entity_type, definition, schema_id):
        """Register actual schema"""
        c = self.conn.cursor()
        # Map domain names to table names
        domain_map = {'investigation': 'investigation', 'procedures': 'procedure',
                      'research': 'research', 'learning': 'learning'}
        table_domain = domain_map.get(domain, domain)
        c.execute(f'''INSERT INTO {table_domain}_schemas
                      (schema_id, entity_type, definition)
                      VALUES (?, ?, ?)''',
                  (schema_id, entity_type, definition))
        self.conn.commit()

    def record_outcome(self, procedure_name, domain, success, execution_time_ms, output):
        """Record actual procedure execution outcome"""
        import uuid
        c = self.conn.cursor()
        c.execute('''INSERT INTO procedure_outcomes
                     (outcome_id, procedure_name, domain, success, execution_time_ms, output)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (str(uuid.uuid4()), procedure_name, domain, success, execution_time_ms, output))
        self.conn.commit()

    def discover_constraint(self, domain, field_name, confidence):
        """Learn and record constraint"""
        import uuid
        c = self.conn.cursor()
        c.execute('''INSERT INTO learned_constraints
                     (constraint_id, domain, field_name, confidence)
                     VALUES (?, ?, ?, ?)''',
                  (str(uuid.uuid4()), domain, field_name, confidence))
        self.conn.commit()

    def get_stats(self):
        """Get database statistics"""
        c = self.conn.cursor()
        stats = {}
        for domain in ['investigation', 'procedure', 'research', 'learning']:
            c.execute(f"SELECT COUNT(*) FROM {domain}_schemas")
            stats[f'{domain}_schemas'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM procedure_outcomes")
        stats['outcomes_recorded'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM learned_constraints")
        stats['constraints_learned'] = c.fetchone()[0]

        return stats

    def close(self):
        self.conn.close()
