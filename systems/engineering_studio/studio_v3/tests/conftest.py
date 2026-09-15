"""Pytest configuration and fixtures - includes test caching plugin"""
import pytest
from pathlib import Path
import sys

# Add project root to path for absolute imports
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from systems.engineering_studio.studio_v3.utils.test_cache_manager import CacheManager

# Global cache manager
_cache_instance = None


def get_cache():
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


def pytest_configure(config):
    """Configure pytest with markers and cache"""
    config.addinivalue_line(
        "markers", "cache: mark test for caching"
    )


def pytest_sessionfinish(session, exitstatus):
    """Print cache statistics at session end"""
    cache = get_cache()
    stats = cache.get_cache_stats()
    print("\n" + "="*70)
    print("TEST CACHE STATISTICS")
    print("="*70)
    print(f"Cache Hits: {stats['cache_hits']}")
    print(f"Cache Misses: {stats['cache_misses']}")
    print(f"Tests Run: {stats['tests_run']}")
    print(f"Tests Skipped: {stats['tests_skipped']}")
    print(f"Hit Rate: {stats['hit_rate_percent']:.1f}%")
    print(f"Speedup Factor: {stats['speedup_factor']:.2f}x (up to 70%)")
    print(f"Cache Database: {stats['cache_file']}")
    print("="*70 + "\n")
    cache.close()


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def cache_manager():
    """Provide access to cache manager in tests"""
    return get_cache()


@pytest.fixture(autouse=True)
def reset_cache_for_test():
    """Reset cache stats before each test if needed"""
    yield
