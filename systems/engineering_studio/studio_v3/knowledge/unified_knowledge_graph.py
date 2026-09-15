"""Unified Knowledge Graph: Single-source-of-truth for all decision + outcome + learning data"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class UnifiedKnowledgeGraph:
    """Normalize all memory systems into single SQLite knowledge base"""

    def __init__(self, db_path: str = '.nexus_knowledge.db'):
        self.db_path = Path(db_path)
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize normalized schema"""
        cursor = self.db.cursor()

        # Core decisions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decision_type TEXT NOT NULL,
                affected_capability TEXT,
                description TEXT,
                current_metrics JSON,
                projected_metrics JSON,
                decision_rationale TEXT,
                approved BOOLEAN DEFAULT 0,
                implementation_timestamp DATETIME,
                UNIQUE(timestamp, decision_type, affected_capability)
            )
        ''')

        # Manifest alignment (links to OptimalStructureManifest)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manifest_alignment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER UNIQUE NOT NULL,
                capability TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                current_value REAL,
                optimal_value REAL,
                gap REAL,
                priority TEXT,
                alignment_score REAL,
                recommendation TEXT,
                FOREIGN KEY(decision_id) REFERENCES decisions(id),
                UNIQUE(decision_id, metric_name)
            )
        ''')

        # Experimental validation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER NOT NULL,
                hypothesis TEXT NOT NULL,
                treatment_effect_size REAL,
                control_effect_size REAL,
                statistical_significance REAL,
                confidence REAL,
                recommendation TEXT,
                experiment_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(decision_id) REFERENCES decisions(id)
            )
        ''')

        # Frontier comparison
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS frontier_comparison (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER NOT NULL,
                frontier_study TEXT NOT NULL,
                capability TEXT NOT NULL,
                frontier_metric_value REAL,
                studio_metric_value REAL,
                exceeds_frontier BOOLEAN,
                gap REAL,
                FOREIGN KEY(decision_id) REFERENCES decisions(id),
                UNIQUE(decision_id, frontier_study, capability)
            )
        ''')

        # Outcomes and results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER UNIQUE NOT NULL,
                actual_metrics JSON,
                vs_projected JSON,
                side_effects JSON,
                success BOOLEAN,
                recorded_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(decision_id) REFERENCES decisions(id)
            )
        ''')

        # Lessons learned
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outcome_id INTEGER UNIQUE NOT NULL,
                hypothesis_validity TEXT,
                unexpected_findings JSON,
                improvements_to_approach JSON,
                procedural_recommendation TEXT,
                generalization_confidence REAL,
                FOREIGN KEY(outcome_id) REFERENCES outcomes(id)
            )
        ''')

        # Cross-session procedures (extracted patterns)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                procedure_name TEXT UNIQUE NOT NULL,
                decision_type_pattern TEXT NOT NULL,
                capability TEXT NOT NULL,
                effectiveness_score REAL,
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                extracted_from_lessons INTEGER,
                FOREIGN KEY(extracted_from_lessons) REFERENCES lessons(id)
            )
        ''')

        # Context cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS context_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_key TEXT UNIQUE NOT NULL,
                cached_value JSON,
                expires_at DATETIME,
                hit_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_manifest_capability ON manifest_alignment(capability)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_frontier_study ON frontier_comparison(frontier_study)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_procedures_pattern ON procedures(decision_type_pattern)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_outcomes_decision ON outcomes(decision_id)')

        self.db.commit()

    def record_decision(self, decision_type: str, affected_capability: str,
                       description: str, current_metrics: Dict[str, Any],
                       projected_metrics: Dict[str, Any],
                       decision_rationale: str) -> Optional[int]:
        """Record a decision proposal"""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO decisions
            (decision_type, affected_capability, description, current_metrics,
             projected_metrics, decision_rationale)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            decision_type, affected_capability, description,
            json.dumps(current_metrics), json.dumps(projected_metrics),
            decision_rationale
        ))
        self.db.commit()
        return cursor.lastrowid

    def record_manifest_alignment(self, decision_id: int, capability: str,
                                 manifest_evaluation: Dict[str, Any]) -> Optional[int]:
        """Record manifest alignment evaluation"""
        cursor = self.db.cursor()
        weighted = manifest_evaluation.get('weighted_assessment', {})

        cursor.execute('''
            INSERT INTO manifest_alignment
            (decision_id, capability, metric_name, current_value, optimal_value,
             gap, priority, alignment_score, recommendation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            decision_id, capability, 'overall',
            0,  # Would aggregate current metrics
            0,  # Would aggregate optimal metrics
            0,  # Would calculate gap
            'HIGH',
            weighted.get('net_score', 0),
            manifest_evaluation.get('recommendation', 'PENDING')
        ))
        self.db.commit()
        return cursor.lastrowid

    def record_experiment(self, decision_id: int, hypothesis: str,
                         treatment_effect_size: float, control_effect_size: float,
                         statistical_significance: float, confidence: float,
                         recommendation: str) -> Optional[int]:
        """Record controlled experiment results"""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO experiments
            (decision_id, hypothesis, treatment_effect_size, control_effect_size,
             statistical_significance, confidence, recommendation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            decision_id, hypothesis, treatment_effect_size, control_effect_size,
            statistical_significance, confidence, recommendation
        ))
        self.db.commit()
        return cursor.lastrowid

    def record_frontier_comparison(self, decision_id: int, frontier_study: str,
                                  capability: str, frontier_metric: float,
                                  studio_metric: float) -> Optional[int]:
        """Record frontier research comparison"""
        cursor = self.db.cursor()
        exceeds = studio_metric > frontier_metric
        gap = studio_metric - frontier_metric

        cursor.execute('''
            INSERT INTO frontier_comparison
            (decision_id, frontier_study, capability, frontier_metric_value,
             studio_metric_value, exceeds_frontier, gap)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            decision_id, frontier_study, capability,
            frontier_metric, studio_metric, exceeds, gap
        ))
        self.db.commit()
        return cursor.lastrowid

    def record_outcome(self, decision_id: int, actual_metrics: Dict[str, Any],
                      vs_projected: Dict[str, Any], side_effects: List[str],
                      success: bool) -> Optional[int]:
        """Record decision outcome after implementation"""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO outcomes
            (decision_id, actual_metrics, vs_projected, side_effects, success)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            decision_id, json.dumps(actual_metrics), json.dumps(vs_projected),
            json.dumps(side_effects), success
        ))
        self.db.commit()

        # Auto-approve decision when outcome recorded
        cursor.execute('UPDATE decisions SET approved = 1 WHERE id = ?', (decision_id,))
        self.db.commit()

        return cursor.lastrowid

    def extract_lessons(self, outcome_id: int, hypothesis_validity: str,
                       unexpected_findings: List[str],
                       improvements: List[str],
                       procedural_recommendation: str,
                       confidence: float) -> Optional[int]:
        """Extract lessons learned from outcome"""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO lessons
            (outcome_id, hypothesis_validity, unexpected_findings,
             improvements_to_approach, procedural_recommendation,
             generalization_confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            outcome_id, hypothesis_validity, json.dumps(unexpected_findings),
            json.dumps(improvements), procedural_recommendation, confidence
        ))
        self.db.commit()
        return cursor.lastrowid

    def register_procedure(self, procedure_name: str, decision_type_pattern: str,
                          capability: str, effectiveness_score: float,
                          extracted_from_lessons_id: Optional[int] = None) -> Optional[int]:
        """Register learned procedure for future decisions"""
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT INTO procedures
            (procedure_name, decision_type_pattern, capability, effectiveness_score,
             extracted_from_lessons)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(procedure_name) DO UPDATE SET
            effectiveness_score = MAX(effectiveness_score, excluded.effectiveness_score),
            usage_count = usage_count + 1
        ''', (
            procedure_name, decision_type_pattern, capability,
            effectiveness_score, extracted_from_lessons_id
        ))
        self.db.commit()
        return cursor.lastrowid

    def get_procedural_recommendation(self, decision_type: str,
                                     capability: str) -> Optional[Dict[str, Any]]:
        """Get learned procedure recommendation for similar decisions"""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT * FROM procedures
            WHERE decision_type_pattern LIKE ? AND capability = ?
            ORDER BY effectiveness_score DESC, usage_count DESC
            LIMIT 1
        ''', (f'%{decision_type}%', capability))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_decision_history(self, decision_type: str,
                            capability: Optional[str] = None,
                            limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent decisions of a type"""
        cursor = self.db.cursor()
        if capability:
            cursor.execute('''
                SELECT d.*, o.success
                FROM decisions d
                LEFT JOIN outcomes o ON d.id = o.decision_id
                WHERE d.decision_type = ? AND d.affected_capability = ?
                ORDER BY d.timestamp DESC
                LIMIT ?
            ''', (decision_type, capability, limit))
        else:
            cursor.execute('''
                SELECT d.*, o.success
                FROM decisions d
                LEFT JOIN outcomes o ON d.id = o.decision_id
                WHERE d.decision_type = ?
                ORDER BY d.timestamp DESC
                LIMIT ?
            ''', (decision_type, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_learning_trajectory(self) -> Dict[str, Any]:
        """Get cross-session learning metrics"""
        cursor = self.db.cursor()

        # Get recent decisions with outcomes
        cursor.execute('''
            SELECT COUNT(*) as total_decisions,
                   SUM(CASE WHEN d.approved = 1 THEN 1 ELSE 0 END) as approved_count,
                   SUM(CASE WHEN o.success = 1 THEN 1 ELSE 0 END) as successful_outcomes
            FROM decisions d
            LEFT JOIN outcomes o ON d.id = o.decision_id
            WHERE d.timestamp > datetime('now', '-7 days')
        ''')

        row = cursor.fetchone()
        metrics = dict(row) if row else {}

        # Get procedure effectiveness
        cursor.execute('''
            SELECT AVG(effectiveness_score) as avg_effectiveness,
                   COUNT(*) as total_procedures,
                   SUM(usage_count) as total_applications
            FROM procedures
        ''')

        proc_row = cursor.fetchone()
        if proc_row:
            metrics.update(dict(proc_row))

        return metrics

    def get_decision_stats(self) -> Dict[str, Any]:
        """Comprehensive decision and outcome statistics"""
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT
            COUNT(*) as total_decisions,
            SUM(CASE WHEN approved = 1 THEN 1 ELSE 0 END) as approved_decisions,
            COUNT(DISTINCT decision_type) as decision_types,
            COUNT(DISTINCT affected_capability) as capabilities_affected
            FROM decisions
        ''')
        decisions = dict(cursor.fetchone())

        cursor.execute('''
            SELECT
            COUNT(*) as total_outcomes,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_outcomes
            FROM outcomes
        ''')
        outcomes = dict(cursor.fetchone())

        cursor.execute('''
            SELECT COUNT(*) as total_lessons FROM lessons
        ''')
        lessons = dict(cursor.fetchone())

        cursor.execute('''
            SELECT COUNT(*) as total_procedures FROM procedures
        ''')
        procedures = dict(cursor.fetchone())

        return {
            'decisions': decisions,
            'outcomes': outcomes,
            'lessons': lessons,
            'procedures': procedures
        }

    def get_capability_health(self, capability: str) -> Dict[str, Any]:
        """Health metrics for a specific capability"""
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT
            COUNT(*) as total_decisions,
            SUM(CASE WHEN d.approved = 1 THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN o.success = 1 THEN 1 ELSE 0 END) as successful_outcomes,
            AVG(CASE WHEN o.success = 1 THEN 1.0 ELSE 0.0 END) as success_rate
            FROM decisions d
            LEFT JOIN outcomes o ON d.id = o.decision_id
            WHERE d.affected_capability = ?
        ''', (capability,))

        health = dict(cursor.fetchone())

        # Get frontier performance
        cursor.execute('''
            SELECT
            COUNT(CASE WHEN exceeds_frontier = 1 THEN 1 END) as exceeds_frontier_count,
            COUNT(*) as total_comparisons
            FROM frontier_comparison
            WHERE capability = ?
        ''', (capability,))

        frontier = dict(cursor.fetchone())
        health.update(frontier)
        health['frontier_exceeds_rate'] = (
            frontier['exceeds_frontier_count'] / frontier['total_comparisons']
            if frontier['total_comparisons'] > 0 else 0
        )

        return health

    def close(self):
        """Close database connection"""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
