import subprocess

class TestResult:
    def __init__(self, passed: bool, output: str, returncode: int):
        self.passed = passed
        self.output = output
        self.returncode = returncode

class TestRunner:
    @staticmethod
    def run_tests(repo_path: str, timeout: int = 60) -> TestResult:
        """
        Run pytest in repository
        Returns pass/fail + output
        """
        try:
            result = subprocess.run(
                ['pytest', str(repo_path), '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(repo_path)
            )
            passed = result.returncode == 0
            return TestResult(passed, result.stdout + result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            return TestResult(False, "Test run timed out", -1)
        except Exception as e:
            return TestResult(False, f"Test run error: {str(e)}", -1)
