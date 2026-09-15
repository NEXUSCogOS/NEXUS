"""Test real code generation and validation"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from systems.engineering_studio.studio_v3.execution.code_generator import CodeGenerator, TemplateRegistry


class TestCodeGenerator:
    """Test CodeGenerator functionality"""

    def test_generator_initialization(self):
        """Test CodeGenerator initializes correctly"""
        gen = CodeGenerator()
        assert gen is not None
        assert len(gen.TEMPLATES) > 0

    def test_generate_web_code(self):
        """Test generate web application code"""
        gen = CodeGenerator()
        requirements = "Create a REST API with GET/POST endpoints"

        result = gen.generate_from_requirements(requirements, 'web')

        assert result.syntax_valid
        assert 'class Application' in result.code
        assert 'def register_route' in result.code
        assert result.domain == 'web'
        assert result.template_used == 'Web Framework'

    def test_generate_ml_code(self):
        """Test generate machine learning code"""
        gen = CodeGenerator()
        requirements = "Build classification model with train/test split"

        result = gen.generate_from_requirements(requirements, 'ml')

        assert result.syntax_valid
        assert 'class Model' in result.code
        assert 'def fit' in result.code
        assert 'def predict' in result.code
        assert result.domain == 'ml'

    def test_generate_cli_code(self):
        """Test generate CLI application code"""
        gen = CodeGenerator()
        requirements = "Create command-line tool with argument parsing"

        result = gen.generate_from_requirements(requirements, 'cli')

        assert result.syntax_valid
        assert 'class CommandParser' in result.code
        assert 'def execute' in result.code
        assert result.domain == 'cli'

    def test_generate_library_code(self):
        """Test generate Python library code"""
        gen = CodeGenerator()
        requirements = "Create reusable library with cache support"

        result = gen.generate_from_requirements(requirements, 'library')

        assert result.syntax_valid
        assert 'class Cache' in result.code
        assert 'def get' in result.code
        assert result.domain == 'library'

    def test_generate_data_pipeline_code(self):
        """Test generate data pipeline code"""
        gen = CodeGenerator()
        requirements = "Build ETL pipeline with transforms"

        result = gen.generate_from_requirements(requirements, 'data_pipeline')

        assert result.syntax_valid
        assert 'class Pipeline' in result.code
        assert 'def run' in result.code
        assert result.domain == 'data_pipeline'

    def test_generate_tests(self):
        """Test generate test suite"""
        gen = CodeGenerator()
        code = "class Application:\n    pass"
        requirements = "Test the application"

        tests = gen.generate_tests(code, requirements)

        assert 'def test_' in tests
        assert 'import pytest' in tests
        assert gen.validate_syntax(tests)

    def test_validate_syntax_valid(self):
        """Test syntax validation for valid code"""
        gen = CodeGenerator()
        valid_code = "def hello():\n    return 'world'"

        assert gen.validate_syntax(valid_code)

    def test_validate_syntax_invalid(self):
        """Test syntax validation for invalid code"""
        gen = CodeGenerator()
        invalid_code = "def hello(\n    return 'world'"  # Missing closing paren

        assert not gen.validate_syntax(invalid_code)

    def test_multiple_generation_tracking(self):
        """Test tracking multiple code generations"""
        gen = CodeGenerator()

        gen.generate_from_requirements("Web API", 'web')
        gen.generate_from_requirements("ML Model", 'ml')
        gen.generate_from_requirements("CLI Tool", 'cli')

        assert len(gen.generated_codes) == 3
        assert gen.generated_codes[0].domain == 'web'
        assert gen.generated_codes[1].domain == 'ml'
        assert gen.generated_codes[2].domain == 'cli'

    def test_default_domain_fallback(self):
        """Test fallback to library for unknown domain"""
        gen = CodeGenerator()

        result = gen.generate_from_requirements("Generic code", 'unknown_domain')

        assert result.domain == 'library'
        assert result.syntax_valid


class TestTemplateRegistry:
    """Test TemplateRegistry functionality"""

    def test_registry_initialization(self):
        """Test TemplateRegistry initializes"""
        registry = TemplateRegistry()

        assert registry is not None
        assert len(registry.list_domains()) > 0

    def test_list_domains(self):
        """Test list available domains"""
        registry = TemplateRegistry()
        domains = registry.list_domains()

        assert 'web' in domains
        assert 'ml' in domains
        assert 'cli' in domains
        assert 'library' in domains
        assert 'data_pipeline' in domains

    def test_get_template(self):
        """Test retrieve template by domain"""
        registry = TemplateRegistry()

        web_template = registry.get_template('web')
        assert web_template is not None
        assert 'template' in web_template
        assert 'name' in web_template

    def test_register_custom_template(self):
        """Test register custom template"""
        registry = TemplateRegistry()
        custom_template = "def custom(): pass"

        registry.register_template('custom_domain', custom_template, 'Custom')

        assert 'custom_domain' in registry.list_domains()
        retrieved = registry.get_template('custom_domain')
        assert retrieved['template'] == custom_template
