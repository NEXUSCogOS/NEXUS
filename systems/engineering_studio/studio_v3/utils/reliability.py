"""Reliability and fault tolerance"""
from typing import Dict, Any, Callable
import time
import logging

class ReliabilityManager:
    """Handle failures, retries, timeouts"""

    def __init__(self, max_retries: int = 3, timeout_seconds: int = 300):
        self.max_retries = max_retries
        self.timeout = timeout_seconds
        self.logger = logging.getLogger(__name__)

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt == self.max_retries:
                    self.logger.error(f"All retries exhausted for {func.__name__}")
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def execute_with_timeout(self, func: Callable, timeout: int = None, *args, **kwargs) -> Any:
        """Execute with timeout (simplified for this context)"""
        timeout = timeout or self.timeout
        try:
            return func(*args, **kwargs)
        except TimeoutError:
            self.logger.error(f"Function {func.__name__} timed out after {timeout}s")
            raise

    def circuit_breaker(self, failure_threshold: int = 5):
        """Decorator for circuit breaker pattern"""
        def decorator(func):
            func.failure_count = 0
            func.circuit_open = False

            def wrapper(*args, **kwargs):
                if func.circuit_open:
                    raise RuntimeError(f"Circuit breaker open for {func.__name__}")

                try:
                    result = func(*args, **kwargs)
                    func.failure_count = 0
                    return result
                except Exception as e:
                    func.failure_count += 1
                    if func.failure_count >= failure_threshold:
                        func.circuit_open = True
                        self.logger.error(f"Circuit breaker opened for {func.__name__}")
                    raise
            return wrapper
        return decorator
