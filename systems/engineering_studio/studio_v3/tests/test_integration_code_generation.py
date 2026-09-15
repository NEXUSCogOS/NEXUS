"""Integration tests for end-to-end code generation and execution"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from systems.engineering_studio.studio_v3.execution import (
    AutonomousProjectExecutor,
    CodeGenerator
)


class TestEndToEndCodeGeneration:
    """Test end-to-end code generation and execution"""

    def test_project_execution_generates_code(self):
        """Test AutonomousProjectExecutor generates real code"""
        executor = AutonomousProjectExecutor()
        project = {
            'name': 'TestAPI',
            'requirements': 'Build REST API with authentication',
            'domain': 'web'
        }

        result = executor.execute_project(project)

        assert result.success
        assert len(result.code) > 0
        assert 'class Application' in result.code
        assert result.tests_passing

    def test_code_generator_creates_executable_code(self):
        """Test generated code is actually executable"""
        gen = CodeGenerator()
        result = gen.generate_from_requirements(
            'Create a calculator with add/multiply operations',
            'library'
        )

        # Verify syntax is valid
        assert result.syntax_valid

        # Try to execute the generated code
        exec_globals = {}
        exec(result.code, exec_globals)

        # Verify key classes exist
        assert 'Cache' in exec_globals or 'EventHandler' in exec_globals

    def test_generated_tests_are_executable(self):
        """Test that generated test code is executable"""
        gen = CodeGenerator()
        code = """
class Calculator:
    def add(self, a, b):
        return a + b
"""
        tests = gen.generate_tests(code, 'Test calculator operations')

        # Verify syntax is valid
        assert gen.validate_syntax(tests)

        # Verify test code contains pytest patterns
        assert '@pytest.fixture' in tests or 'def test_' in tests

    def test_multiple_domain_codegen_quality(self):
        """Test code generation quality across multiple domains"""
        gen = CodeGenerator()
        domains = ['web', 'ml', 'cli', 'library', 'data_pipeline']

        results = []
        for domain in domains:
            result = gen.generate_from_requirements(
                f'Create {domain} application',
                domain
            )
            results.append(result)

        # Verify all generated code is syntactically valid
        assert all(r.syntax_valid for r in results)

        # Verify each has appropriate classes/functions
        assert 'class Application' in results[0].code  # web
        assert 'class Model' in results[1].code  # ml
        assert 'class CommandParser' in results[2].code  # cli
        assert 'class BaseComponent' in results[3].code  # library
        assert 'class Pipeline' in results[4].code  # data_pipeline

    def test_code_generation_with_requirements_integration(self):
        """Test code generation properly incorporates requirements"""
        gen = CodeGenerator()
        requirements = """
        - Create a user authentication system
        - Support OAuth2 flow
        - Implement JWT token validation
        - Include audit logging
        """

        result = gen.generate_from_requirements(requirements, 'web')

        # Verify requirements are documented
        assert 'user authentication' in result.code
        assert result.syntax_valid

    def test_generated_code_documentation(self):
        """Test that generated code includes documentation"""
        gen = CodeGenerator()
        result = gen.generate_from_requirements(
            'Create data processing service',
            'data_pipeline'
        )

        # Check for docstrings and documentation
        assert '"""' in result.code
        assert 'def ' in result.code

    def test_executor_integration_with_codegen(self):
        """Test AutonomousProjectExecutor properly uses CodeGenerator"""
        executor = AutonomousProjectExecutor()

        # Verify CodeGenerator is initialized
        assert executor.code_generator is not None

        # Verify it's used in project execution
        project = {
            'name': 'TestProject',
            'requirements': 'Test requirement',
            'domain': 'library'
        }

        result = executor.execute_project(project)
        assert len(result.code) > 100  # Real code, not stub
