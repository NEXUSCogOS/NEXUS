"""Autonomous project execution and testing subsystem"""
from .autonomous_project_executor import AutonomousProjectExecutor, ExecutionResult
from .approval_queue import ApprovalQueue
from .autonomous_recorder import AutonomousRecorder
from .test_runner import TestRunner, TestResult
from .repairs import RepairGenerator
from .patch_generator import PatchGenerator
from .sandbox_manager import SandboxManager
from .code_generator import CodeGenerator, TemplateRegistry
from .async_executor import (
    AsyncProjectExecutor,
    ConcurrentQueue,
    ProjectExecution,
    ProjectStatus,
    ExecutionMetrics,
)
from .sentinel_connector import SentinelConnector, TrendData, MarketTrend
from .datai_connector import DatAiConnector, PropertyPrice, LocationTrend
from .market_connector import MarketConnector, StockQuote, MarketSnapshot

__all__ = [
    'AutonomousProjectExecutor',
    'ExecutionResult',
    'ApprovalQueue',
    'AutonomousRecorder',
    'TestRunner',
    'TestResult',
    'RepairGenerator',
    'PatchGenerator',
    'SandboxManager',
    'CodeGenerator',
    'TemplateRegistry',
    'AsyncProjectExecutor',
    'ConcurrentQueue',
    'ProjectExecution',
    'ProjectStatus',
    'ExecutionMetrics',
    'SentinelConnector',
    'TrendData',
    'MarketTrend',
    'DatAiConnector',
    'PropertyPrice',
    'LocationTrend',
    'MarketConnector',
    'StockQuote',
    'MarketSnapshot',
]
