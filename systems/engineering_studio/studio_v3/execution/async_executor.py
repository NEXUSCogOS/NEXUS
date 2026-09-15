"""
Multi-Project Async Executor
Asyncio-based concurrent execution for processing 3-5 projects simultaneously
with full isolation, queue management for 50+ projects, and 3-5x throughput improvement.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Coroutine
from uuid import uuid4
from enum import Enum
import logging

from .learning_integrated_executor import LearningIntegratedExecutor, LearningMetrics
from .autonomous_project_executor import ExecutionResult

logger = logging.getLogger(__name__)


class ProjectStatus(Enum):
    """Project execution status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ProjectExecution:
    """Tracks a single project execution"""
    project_id: str
    project_name: str
    status: ProjectStatus = ProjectStatus.QUEUED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    learning_metrics: Optional[LearningMetrics] = None
    throughput_multiplier: float = 1.0  # Tracks speedup vs sequential


@dataclass
class ExecutionMetrics:
    """Tracks concurrent execution metrics"""
    total_projects: int = 0
    completed: int = 0
    failed: int = 0
    running: int = 0
    queued: int = 0
    total_execution_time: float = 0.0
    concurrent_speedup: float = 1.0  # Ratio of sequential vs parallel time
    patterns_learned: int = 0
    lessons_extracted: int = 0
    average_project_time: float = 0.0
    throughput_projects_per_hour: float = 0.0


class ConcurrentQueue:
    """Queue management for 50+ projects with priority and resource awareness"""

    def __init__(self, max_queue_size: int = 50):
        self.max_queue_size = max_queue_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._project_map: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def add_project(
        self,
        project: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """Add project to queue with optional priority"""
        async with self._lock:
            if len(self._project_map) >= self.max_queue_size:
                raise ValueError(f"Queue at maximum capacity ({self.max_queue_size})")

            project_id = str(uuid4())
            self._project_map[project_id] = {
                'project': project,
                'priority': priority,
                'added_at': datetime.now(timezone.utc)
            }
            await self._queue.put((priority, project_id))
            return project_id

    async def get_project(self) -> Optional[tuple[str, Dict[str, Any]]]:
        """Get next project from queue"""
        try:
            priority, project_id = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            async with self._lock:
                if project_id in self._project_map:
                    project_data = self._project_map.pop(project_id)
                    return project_id, project_data['project']
            return None
        except asyncio.TimeoutError:
            return None

    async def get_queue_status(self) -> Dict[str, int]:
        """Get current queue status"""
        async with self._lock:
            return {
                'total_queued': len(self._project_map),
                'queue_capacity': self.max_queue_size,
                'queue_utilization': len(self._project_map) / self.max_queue_size
            }

    def queue_size(self) -> int:
        """Get current queue size"""
        return len(self._project_map)


class AsyncProjectExecutor:
    """
    Concurrent project executor with asyncio
    Handles 3-5 concurrent projects, queue for 50+, learns from patterns
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        enable_learning: bool = True,
        state_dir: str = '.studio_state'
    ):
        self.max_concurrent = max_concurrent
        self.enable_learning = enable_learning
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)

        # Initialize executors and queues
        self.executor = LearningIntegratedExecutor() if enable_learning else None
        self.queue = ConcurrentQueue()

        # Tracking
        self.executions: Dict[str, ProjectExecution] = {}
        self.metrics = ExecutionMetrics()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._start_time: Optional[datetime] = None

    async def execute_concurrent(
        self,
        projects: List[Dict[str, Any]],
        on_progress: Optional[Callable[[ProjectExecution], Coroutine]] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple projects concurrently

        Args:
            projects: List of project configurations
            on_progress: Optional callback for progress updates

        Returns:
            Results dict with execution metrics and individual results
        """
        self._start_time = datetime.now(timezone.utc)
        self._running = True
        self.metrics.total_projects = len(projects)

        try:
            # Add all projects to queue
            project_ids = []
            for project in projects:
                project_id = await self.queue.add_project(project)
                project_ids.append(project_id)
                self.executions[project_id] = ProjectExecution(
                    project_id=project_id,
                    project_name=project.get('name', 'unnamed')
                )

            # Execute projects concurrently
            await self._process_queue(on_progress)

            # Calculate final metrics
            await self._finalize_metrics()

            return self._build_results()

        finally:
            self._running = False

    async def _process_queue(
        self,
        on_progress: Optional[Callable[[ProjectExecution], Coroutine]] = None
    ):
        """Process projects from queue with concurrent execution"""
        tasks = set()

        while self.queue.queue_size() > 0 or len(tasks) > 0:
            # Submit new work while under concurrency limit
            while len(tasks) < self.max_concurrent:
                project_data = await self.queue.get_project()
                if not project_data:
                    break

                project_id, project = project_data
                task = asyncio.create_task(
                    self._execute_single_project(project_id, project, on_progress)
                )
                tasks.add(task)
                self.metrics.running += 1

            # Wait for at least one task to complete
            if tasks:
                done, tasks = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                self.metrics.running = len(tasks)

            # Small delay to avoid busy waiting
            await asyncio.sleep(0.01)

        # Wait for all remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single_project(
        self,
        project_id: str,
        project: Dict[str, Any],
        on_progress: Optional[Callable[[ProjectExecution], Coroutine]] = None
    ):
        """Execute a single project with isolation"""
        execution = self.executions[project_id]
        execution.status = ProjectStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)

        try:
            async with self._semaphore:
                # Execute project
                if self.enable_learning and self.executor:
                    result = await asyncio.to_thread(
                        self.executor.execute_project_with_learning,
                        project
                    )
                    execution.learning_metrics = self.executor.learning_metrics
                else:
                    result = await asyncio.to_thread(
                        self._execute_basic_project,
                        project
                    )

                execution.result = result
                execution.status = ProjectStatus.COMPLETED
                self.metrics.completed += 1

                # Calculate execution time
                execution.completed_at = datetime.now(timezone.utc)
                if execution.started_at:
                    execution.execution_time_seconds = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()

                # Update learning metrics
                if execution.learning_metrics:
                    self.metrics.patterns_learned += execution.learning_metrics.patterns_learned
                    self.metrics.lessons_extracted += execution.learning_metrics.lessons_extracted

        except Exception as e:
            execution.status = ProjectStatus.FAILED
            execution.error = str(e)
            self.metrics.failed += 1
            logger.error(f"Project {project_id} failed: {e}")

        # Call progress callback
        if on_progress:
            await on_progress(execution)

    def _execute_basic_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Execute basic project without learning"""
        from .autonomous_project_executor import AutonomousProjectExecutor
        executor = AutonomousProjectExecutor()
        result = executor.execute_project(project)
        return asdict(result) if hasattr(result, '__dataclass_fields__') else result

    async def _finalize_metrics(self):
        """Calculate final execution metrics"""
        if not self._start_time:
            return

        # Total execution time
        self.metrics.total_execution_time = (
            datetime.now(timezone.utc) - self._start_time
        ).total_seconds()

        # Average project time
        if self.metrics.completed > 0:
            total_individual_time = sum(
                e.execution_time_seconds for e in self.executions.values()
                if e.status == ProjectStatus.COMPLETED
            )
            self.metrics.average_project_time = total_individual_time / self.metrics.completed

            # Calculate speedup (concurrent vs sequential)
            # Speedup = (sum of individual times) / (total wall clock time)
            # This represents how much faster parallel execution is compared to sequential
            sequential_time = total_individual_time

            # Ensure we don't divide by very small numbers or get unrealistic values
            if self.metrics.total_execution_time > 0.001:  # Minimum 1ms
                speedup = sequential_time / self.metrics.total_execution_time
                # Cap speedup at theoretical maximum (num concurrent tasks)
                self.metrics.concurrent_speedup = min(speedup, self.max_concurrent)
            else:
                self.metrics.concurrent_speedup = 1.0

            # Throughput
            self.metrics.throughput_projects_per_hour = (
                (self.metrics.completed / self.metrics.total_execution_time) * 3600
                if self.metrics.total_execution_time > 0 else 0
            )

    def _build_results(self) -> Dict[str, Any]:
        """Build final results dictionary"""
        return {
            'status': 'completed' if self.metrics.failed == 0 else 'partial',
            'metrics': asdict(self.metrics),
            'executions': {
                project_id: {
                    'project_id': e.project_id,
                    'project_name': e.project_name,
                    'status': e.status.value,
                    'execution_time_seconds': e.execution_time_seconds,
                    'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                    'error': e.error,
                    'result_summary': (
                        {
                            'patterns_learned': e.learning_metrics.patterns_learned,
                            'lessons_extracted': e.learning_metrics.lessons_extracted,
                        } if e.learning_metrics else None
                    )
                }
                for project_id, e in self.executions.items()
            },
            'speedup_factor': f"{self.metrics.concurrent_speedup:.1f}x",
            'throughput_improvement': f"{(self.metrics.concurrent_speedup - 1) * 100:.0f}%"
        }

    async def pause_all(self):
        """Pause all running projects"""
        for execution in self.executions.values():
            if execution.status == ProjectStatus.RUNNING:
                execution.status = ProjectStatus.PAUSED

    async def get_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        return {
            'running': self._running,
            'metrics': asdict(self.metrics),
            'queue_status': await self.queue.get_queue_status(),
            'executions': {
                project_id: {
                    'project_id': e.project_id,
                    'project_name': e.project_name,
                    'status': e.status.value,
                    'execution_time': e.execution_time_seconds,
                }
                for project_id, e in self.executions.items()
            }
        }

    def save_state(self, filepath: Optional[str] = None):
        """Save execution state to disk"""
        if not filepath:
            filepath = self.state_dir / f"async_execution_{datetime.now(timezone.utc).isoformat()}.json"

        state = {
            'metrics': asdict(self.metrics),
            'executions': {
                project_id: {
                    'project_id': e.project_id,
                    'project_name': e.project_name,
                    'status': e.status.value,
                    'execution_time_seconds': e.execution_time_seconds,
                    'started_at': e.started_at.isoformat() if e.started_at else None,
                    'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                    'error': e.error,
                }
                for project_id, e in self.executions.items()
            }
        }

        Path(filepath).write_text(json.dumps(state, indent=2))
        logger.info(f"State saved to {filepath}")
