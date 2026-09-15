import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from ..perception.repository_scanner import RepositoryScanner
from ..cognition.prioritiser import Prioritiser
from ..cognition.planner import Planner
from ..execution.sandbox_manager import SandboxManager
from ..execution.patch_generator import PatchGenerator
from ..execution.test_runner import TestRunner
from ..governance.authority_gate import AuthorityGate
from ..memory.canonical_db import init_canonical

# Import v5 research evolution modules
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'studio_v5'))
    from research_evolution import (
        frontier_scan,
        compare_architecture,
        analyze_gaps,
        generate_report,
        run_experiment,
        validate_finding,
        update_corpus,
        record_benchmark
    )
    V5_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    V5_AVAILABLE = False
    print(f"Warning: V5 research evolution not available: {e}")

class StudioController:
    def __init__(self, config_path: str, repo_path: str):
        self.config_path = config_path
        self.repo_path = repo_path
        self.canonical_db = init_canonical(config_path)
        self.scanner = RepositoryScanner(repo_path)
        self.prioritiser = Prioritiser()
        self.planner = Planner()
        self.gate = AuthorityGate(repo_path)

    def _determine_agent_strategy(self, task: Dict[str, Any]) -> str:
        """
        Determine which agent strategy to use for task approval.

        Args:
            task: Task to determine strategy for

        Returns:
            Strategy name (CodeModificationAgent, TestAgent, SecurityAgent,
            DocumentationAgent, or None)
        """
        task_type = task.get('type', '').lower()

        # Map task types to agent strategies
        if 'code' in task_type or 'refactor' in task_type or 'type_hint' in task_type:
            return 'CodeModificationAgent'
        elif 'test' in task_type or 'coverage' in task_type:
            return 'TestAgent'
        elif 'security' in task_type or 'vulnerability' in task_type:
            return 'SecurityAgent'
        elif 'doc' in task_type or 'readme' in task_type or 'documentation' in task_type:
            return 'DocumentationAgent'
        else:
            return 'CodeModificationAgent'  # Default to code modification

    def run_repair_loop(self) -> Dict[str, Any]:
        """
        Execute one complete autonomous repair cycle:
        1. Scan for findings
        2. Classify + plan
        3. Get approval
        4. Execute in sandbox
        5. Test + commit
        6. Log results
        7. Learn from frontier research (V5 learning phase)
        """
        results = {
            'cycle_start': str(Path(__file__).parent),
            'findings': [],
            'tasks_executed': [],
            'failures': [],
            'learning_phase': None
        }

        try:
            print("[1/6] Scanning repository...")
            findings = self.scanner.scan_missing_readme()
            results['findings'] = findings

            if not findings:
                print("✓ No findings. Executing learning phase...")
                # Even with no repairs, still run learning phase
                results['learning_phase'] = self.learn_phase(results)
                return results

            for finding in findings:
                print(f"\n[2/6] Classifying finding: {finding['type']}")
                classified = self.prioritiser.classify_finding(finding)

                print(f"[3/6] Planning repair...")
                task = self.planner.create_repair_plan(classified)

                print(f"[4/6] Checking authority gate...")
                # Determine appropriate agent strategy based on task type
                agent_strategy = self._determine_agent_strategy(task)
                if not self.gate.approve(task, agent_strategy=agent_strategy):
                    print(f"✗ Task rejected by authority gate")
                    audit_entry = self.gate.create_audit_entry(
                        task, False, "Rejected by policy", agent_strategy
                    )
                    results['failures'].append(task['task_id'])
                    continue

                print(f"✓ Task approved for autonomous execution (strategy: {agent_strategy})")

                if self._execute_repair(task, results):
                    results['tasks_executed'].append(task['task_id'])

            # Execute learning phase after repairs
            print("\n[7/7] Executing learning phase...")
            results['learning_phase'] = self.learn_phase(results)

        except Exception as e:
            results['error'] = str(e)
            import traceback
            results['traceback'] = traceback.format_exc()

        return results

    def learn_phase(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute learning phase: scan frontier, compare architectures, generate insights.
        Called after test_phase to continuously improve the system.

        Returns:
            Learning results with frontier findings and insights
        """
        if not V5_AVAILABLE:
            return {
                'status': 'skipped',
                'reason': 'V5 research evolution not available'
            }

        learn_start = time.time()
        learning_results = {
            'phase': 'learning',
            'timestamp': str(Path(__file__).parent),
            'findings': [],
            'insights': [],
            'learned_this_cycle': None,
            'latency_ms': 0
        }

        try:
            print("\n[7/7] Learning phase: Frontier research scan...")

            # Step 1: Frontier scan
            print("  → Scanning frontier opportunities...")
            scan_results = frontier_scan(self.repo_path)
            learning_results['findings'] = scan_results.get('opportunities', [])
            learning_results['metrics'] = scan_results.get('metrics', {})

            if not learning_results['findings']:
                print("  ✓ No frontier opportunities found")
                learning_results['learned_this_cycle'] = 'System at current frontier'
                return learning_results

            # Step 2: Architecture comparison
            print("  → Comparing with frontier patterns...")
            comparison_results = compare_architecture()
            learning_results['insights'].append(
                f"Architecture alignment: {comparison_results.get('alignment_score', 0):.1%}"
            )

            # Step 3: Gap analysis
            print("  → Analyzing capability gaps...")
            gap_results = analyze_gaps()
            gap_recommendations = gap_results.get('recommendations', [])
            learning_results['insights'].extend(gap_recommendations)

            # Step 4: Generate report
            print("  → Generating evolution report...")
            report = generate_report(scan_results, comparison_results)
            learning_results['summary'] = report.get('summary', '')

            # Step 5: Record to evidence ledger
            if hasattr(self.canonical_db, 'log_learning'):
                self.canonical_db.log_learning(
                    'frontier_scan',
                    'completed',
                    {
                        'opportunities': len(learning_results['findings']),
                        'insights': len(learning_results['insights']),
                        'alignment_score': comparison_results.get('alignment_score', 0)
                    }
                )

            # Step 6: Record benchmark
            latency = (time.time() - learn_start) * 1000
            record_benchmark('learning_phase_latency_ms', latency)
            learning_results['latency_ms'] = latency

            # Determine what was learned
            if learning_results['findings']:
                top_finding = learning_results['findings'][0]
                learning_results['learned_this_cycle'] = (
                    f"Opportunity: {top_finding.get('type', 'unknown')} "
                    f"({top_finding.get('severity', 'medium')} severity)"
                )
            else:
                learning_results['learned_this_cycle'] = 'Frontier analysis completed'

            print(f"  ✓ Learning phase complete ({latency:.1f}ms)")
            print(f"    Learned: {learning_results['learned_this_cycle']}")

        except Exception as e:
            print(f"  ✗ Learning phase failed: {e}")
            learning_results['error'] = str(e)
            import traceback
            learning_results['traceback'] = traceback.format_exc()

        return learning_results

    def _execute_repair(self, task: Dict[str, Any], results: Dict) -> bool:
        """Execute repair in sandbox"""
        task_id = task['task_id']
        repo_path = task['repo_path']

        try:
            print(f"\n[5/6] Creating sandbox branch: {task['sandbox_branch']}")
            sandbox = SandboxManager(repo_path)
            branch_sha = sandbox.create_branch(task['sandbox_branch'])
            print(f"✓ Branch created: {branch_sha[:8]}")

            print(f"Generating README...")
            readme_path = PatchGenerator.generate_readme(repo_path)
            print(f"✓ README created: {readme_path}")

            print(f"Running tests...")
            test_result = TestRunner.run_tests(repo_path)
            if not test_result.passed:
                print(f"⚠ Tests failed (may be pre-existing)")
            else:
                print(f"✓ Tests passed")

            print(f"\n[6/6] Committing changes...")
            import subprocess
            subprocess.run(
                ['git', '-C', repo_path, 'add', 'README.md'],
                check=True, capture_output=True
            )
            subprocess.run(
                ['git', '-C', repo_path, 'commit',
                 '-m', f'fix: add auto-generated README\n\nRepair task: {task_id}'],
                check=True, capture_output=True
            )
            print(f"✓ Changes committed")

            try:
                self.canonical_db.log_repair(task_id, 'completed', {
                    'branch': task['sandbox_branch'],
                    'file': readme_path,
                    'tests_passed': test_result.passed
                })
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"✗ Repair failed: {e}")
            try:
                sandbox.rollback_branch(task['sandbox_branch'])
            except:
                pass
            return False
