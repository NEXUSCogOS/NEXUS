"""Test cache manager: File hash-based incremental testing with TTL support"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4


@dataclass
class CacheEntry:
    """Cached test result for a file"""
    file_path: str
    file_hash: str
    test_result: bool
    coverage: float
    timestamp: str
    cache_id: str = field(default_factory=lambda: str(uuid4()))
    ttl_seconds: int = 86400  # 24 hours default

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        entry_time = datetime.fromisoformat(self.timestamp)
        expiry_time = entry_time + timedelta(seconds=self.ttl_seconds)
        return datetime.now(timezone.utc) > expiry_time

    def to_dict(self) -> Dict:
        """Convert to dict for storage"""
        return asdict(self)


class CacheManager:
    """Manages incremental test caching based on file hashes"""

    def __init__(self, cache_db_path: str = ".nexus_test_cache.db"):
        """Initialize cache manager with SQLite backend"""
        self.cache_db_path = cache_db_path
        self.db = sqlite3.connect(cache_db_path, check_same_thread=False)
        self._init_schema()
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tests_skipped": 0,
            "tests_run": 0,
            "avg_speedup": 1.0
        }

    def _init_schema(self) -> None:
        """Initialize SQLite schema for cache storage"""
        cursor = self.db.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_cache (
                cache_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                test_result INTEGER NOT NULL,
                coverage REAL NOT NULL,
                timestamp TEXT NOT NULL,
                ttl_seconds INTEGER DEFAULT 86400
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_file_dependencies (
                file_path TEXT PRIMARY KEY,
                depends_on TEXT NOT NULL,
                last_checked TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_path ON test_cache(file_path)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON test_cache(timestamp)
        ''')

        self.db.commit()

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hash of file contents"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except FileNotFoundError:
            return ""

    def get_cache_entry(self, file_path: str) -> Optional[CacheEntry]:
        """Retrieve cached result for a file"""
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT * FROM test_cache WHERE file_path = ?',
            (file_path,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        entry = CacheEntry(
            file_path=row[1],
            file_hash=row[2],
            test_result=bool(row[3]),
            coverage=row[4],
            timestamp=row[5],
            cache_id=row[0],
            ttl_seconds=row[6] if len(row) > 6 else 86400
        )

        if entry.is_expired():
            self.invalidate_cache(file_path)
            return None

        return entry

    def should_test_file(self, file_path: str) -> bool:
        """Determine if a file needs re-testing"""
        current_hash = self.compute_file_hash(file_path)

        if not current_hash:
            self.stats["cache_misses"] += 1
            return True  # File not found, mark for testing

        cached = self.get_cache_entry(file_path)

        if cached is None:
            self.stats["cache_misses"] += 1
            return True

        if cached.file_hash != current_hash:
            self.stats["cache_misses"] += 1
            return True

        self.stats["cache_hits"] += 1
        return False

    def cache_test_result(
        self,
        file_path: str,
        passed: bool,
        coverage: float,
        ttl_seconds: int = 86400
    ) -> CacheEntry:
        """Cache test result for a file"""
        file_hash = self.compute_file_hash(file_path)
        cache_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = CacheEntry(
            file_path=file_path,
            file_hash=file_hash,
            test_result=passed,
            coverage=coverage,
            timestamp=timestamp,
            cache_id=cache_id,
            ttl_seconds=ttl_seconds
        )

        cursor = self.db.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO test_cache
            (cache_id, file_path, file_hash, test_result, coverage, timestamp, ttl_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.cache_id, entry.file_path, entry.file_hash,
            int(entry.test_result), entry.coverage, entry.timestamp,
            entry.ttl_seconds
        ))
        self.db.commit()

        self.stats["tests_run"] += 1
        return entry

    def get_modified_files(
        self,
        test_files: List[str],
        base_path: Optional[str] = None
    ) -> Set[str]:
        """Get list of test files that need to be run (have been modified)"""
        modified = set()

        for test_file in test_files:
            if self.should_test_file(test_file):
                modified.add(test_file)
            else:
                self.stats["tests_skipped"] += 1

        return modified

    def invalidate_cache(self, file_path: str) -> None:
        """Invalidate cache for a specific file"""
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM test_cache WHERE file_path = ?', (file_path,))
        self.db.commit()

    def invalidate_all(self) -> None:
        """Clear entire cache"""
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM test_cache')
        cursor.execute('DELETE FROM test_file_dependencies')
        self.db.commit()
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tests_skipped": 0,
            "tests_run": 0,
            "avg_speedup": 1.0
        }

    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        total_lookups = self.stats["cache_hits"] + self.stats["cache_misses"]
        if total_lookups > 0:
            hit_rate = (self.stats["cache_hits"] / total_lookups) * 100
            speedup = (
                (self.stats["tests_skipped"] / (self.stats["tests_run"] + 1))
                if self.stats["tests_run"] > 0 else 1.0
            )
            self.stats["avg_speedup"] = min(speedup, 0.7)  # Cap at 70% speedup
        else:
            hit_rate = 0.0

        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "tests_run": self.stats["tests_run"],
            "tests_skipped": self.stats["tests_skipped"],
            "hit_rate_percent": hit_rate,
            "speedup_factor": self.stats["avg_speedup"],
            "cache_file": self.cache_db_path
        }

    def get_cache_size(self) -> int:
        """Get number of cached entries"""
        cursor = self.db.cursor()
        cursor.execute('SELECT COUNT(*) FROM test_cache')
        return cursor.fetchone()[0]

    def cleanup_expired(self) -> int:
        """Remove expired cache entries, return count of removed entries"""
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT file_path FROM test_cache WHERE timestamp < ?',
            (
                (datetime.now(timezone.utc) - timedelta(seconds=86400)).isoformat(),
            )
        )
        expired_files = [row[0] for row in cursor.fetchall()]

        for file_path in expired_files:
            self.invalidate_cache(file_path)

        return len(expired_files)

    def close(self) -> None:
        """Close database connection"""
        if self.db:
            self.db.close()

    def __enter__(self) -> CacheManager:
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()
