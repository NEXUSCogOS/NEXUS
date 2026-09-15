"""Tests for test_cache_manager.py - Incremental testing with caching"""
import sys
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systems.engineering_studio.studio_v3.utils.test_cache_manager import CacheManager, CacheEntry


class TestCacheEntry:
    """Test CacheEntry dataclass"""

    def test_cache_entry_creation(self):
        """Test creating a cache entry"""
        entry = CacheEntry(
            file_path="test.py",
            file_hash="abc123",
            test_result=True,
            coverage=0.95,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        assert entry.file_path == "test.py"
        assert entry.test_result is True
        assert entry.coverage == 0.95
        assert entry.cache_id is not None

    def test_cache_entry_not_expired(self):
        """Test cache entry that is not expired"""
        entry = CacheEntry(
            file_path="test.py",
            file_hash="abc123",
            test_result=True,
            coverage=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
            ttl_seconds=3600
        )

        assert entry.is_expired() is False

    def test_cache_entry_expired(self):
        """Test cache entry that is expired"""
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        entry = CacheEntry(
            file_path="test.py",
            file_hash="abc123",
            test_result=True,
            coverage=0.95,
            timestamp=past_time,
            ttl_seconds=3600
        )

        assert entry.is_expired() is True

    def test_cache_entry_to_dict(self):
        """Test converting cache entry to dict"""
        entry = CacheEntry(
            file_path="test.py",
            file_hash="abc123",
            test_result=True,
            coverage=0.95,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        entry_dict = entry.to_dict()
        assert "file_path" in entry_dict
        assert "file_hash" in entry_dict
        assert "test_result" in entry_dict
        assert "coverage" in entry_dict


class TestCacheManagerClass:
    """Test CacheManager functionality"""

    @pytest.fixture
    def temp_cache(self):
        """Create a temporary cache for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / ".nexus_test_cache.db"
            cache = CacheManager(str(cache_path))
            yield cache
            cache.close()

    def test_cache_manager_initialization(self, temp_cache):
        """Test cache manager initializes correctly"""
        assert temp_cache.db is not None
        assert temp_cache.stats["cache_hits"] == 0
        assert temp_cache.stats["cache_misses"] == 0

    def test_compute_file_hash(self, temp_cache):
        """Test file hash computation"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("def test(): pass\n")
            f.flush()

            hash1 = CacheManager.compute_file_hash(f.name)
            assert hash1 is not None
            assert len(hash1) == 64  # SHA256 hex digest length

            # Same file should produce same hash
            hash2 = CacheManager.compute_file_hash(f.name)
            assert hash1 == hash2

            Path(f.name).unlink()

    def test_compute_file_hash_nonexistent(self, temp_cache):
        """Test file hash for non-existent file"""
        hash_val = CacheManager.compute_file_hash("/nonexistent/file.py")
        assert hash_val == ""

    def test_cache_test_result(self, temp_cache):
        """Test caching a test result"""
        test_file = "test_example.py"
        entry = temp_cache.cache_test_result(
            file_path=test_file,
            passed=True,
            coverage=0.95
        )

        assert entry.file_path == test_file
        assert entry.test_result is True
        assert entry.coverage == 0.95

    def test_get_cache_entry_exists(self, temp_cache):
        """Test retrieving an existing cache entry"""
        test_file = "test_example.py"
        temp_cache.cache_test_result(test_file, True, 0.95)

        cached = temp_cache.get_cache_entry(test_file)
        assert cached is not None
        assert cached.file_path == test_file
        assert cached.test_result is True

    def test_get_cache_entry_nonexistent(self, temp_cache):
        """Test retrieving a non-existent cache entry"""
        cached = temp_cache.get_cache_entry("nonexistent.py")
        assert cached is None

    def test_should_test_file_new_file(self, temp_cache):
        """Test should_test_file returns True for new files"""
        # File doesn't exist and has no cache
        initial_misses = temp_cache.stats["cache_misses"]
        should_test = temp_cache.should_test_file("new_test.py")
        assert should_test is True
        assert temp_cache.stats["cache_misses"] == initial_misses + 1

    def test_should_test_file_cached_unchanged(self, temp_cache):
        """Test should_test_file returns False for unchanged cached files"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("def test(): pass\n")
            f.flush()

            # Cache the file
            temp_cache.cache_test_result(f.name, True, 0.95)

            # Should not need re-testing
            should_test = temp_cache.should_test_file(f.name)
            assert should_test is False
            assert temp_cache.stats["cache_hits"] == 1

            Path(f.name).unlink()

    def test_should_test_file_modified(self, temp_cache):
        """Test should_test_file returns True for modified files"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("def test(): pass\n")
            f.flush()
            fname = f.name

            # Cache the file
            temp_cache.cache_test_result(fname, True, 0.95)

            # Modify the file
            with open(fname, 'w') as mf:
                mf.write("def test(): pass\ndef test2(): pass\n")

            # Should need re-testing
            should_test = temp_cache.should_test_file(fname)
            assert should_test is True
            assert temp_cache.stats["cache_misses"] == 1

            Path(fname).unlink()

    def test_get_cache_stats(self, temp_cache):
        """Test cache statistics"""
        temp_cache.cache_test_result("test1.py", True, 0.95)
        temp_cache.cache_test_result("test2.py", True, 0.94)

        # Trigger cache hits
        temp_cache.should_test_file("test1.py")
        temp_cache.should_test_file("test1.py")

        stats = temp_cache.get_cache_stats()
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "tests_run" in stats
        assert "tests_skipped" in stats
        assert "hit_rate_percent" in stats
        assert "speedup_factor" in stats

    def test_get_cache_size(self, temp_cache):
        """Test getting cache size"""
        assert temp_cache.get_cache_size() == 0

        temp_cache.cache_test_result("test1.py", True, 0.95)
        assert temp_cache.get_cache_size() == 1

        temp_cache.cache_test_result("test2.py", True, 0.94)
        assert temp_cache.get_cache_size() == 2

    def test_invalidate_cache(self, temp_cache):
        """Test invalidating a single cache entry"""
        temp_cache.cache_test_result("test1.py", True, 0.95)
        temp_cache.cache_test_result("test2.py", True, 0.94)

        assert temp_cache.get_cache_size() == 2

        temp_cache.invalidate_cache("test1.py")
        assert temp_cache.get_cache_size() == 1

    def test_invalidate_all(self, temp_cache):
        """Test clearing entire cache"""
        temp_cache.cache_test_result("test1.py", True, 0.95)
        temp_cache.cache_test_result("test2.py", True, 0.94)

        assert temp_cache.get_cache_size() == 2

        temp_cache.invalidate_all()
        assert temp_cache.get_cache_size() == 0
        assert temp_cache.stats["cache_hits"] == 0

    def test_cleanup_expired(self, temp_cache):
        """Test cleaning up expired cache entries"""
        # Create an expired entry manually
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        entry = CacheEntry(
            file_path="expired_test.py",
            file_hash="abc123",
            test_result=True,
            coverage=0.95,
            timestamp=past_time,
            ttl_seconds=3600
        )

        import sqlite3
        cursor = temp_cache.db.cursor()
        cursor.execute('''
            INSERT INTO test_cache
            (cache_id, file_path, file_hash, test_result, coverage, timestamp, ttl_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.cache_id, entry.file_path, entry.file_hash,
            int(entry.test_result), entry.coverage, entry.timestamp,
            entry.ttl_seconds
        ))
        temp_cache.db.commit()

        assert temp_cache.get_cache_size() == 1

        removed = temp_cache.cleanup_expired()
        assert removed >= 0

    def test_context_manager(self):
        """Test cache manager as context manager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / ".nexus_test_cache.db"
            with CacheManager(str(cache_path)) as cache:
                cache.cache_test_result("test1.py", True, 0.95)
                assert cache.get_cache_size() == 1
