"""
Tests for SchemaValidator (Week 7)

Tests schema validation against SPEC v7.0 requirements.
"""

import pytest
import yaml
from pathlib import Path
from src.validation.schema_validator import SchemaValidator, ValidationError


@pytest.fixture
def valid_schema_path():
    """Path to valid memory schema."""
    return "config/memory-schema.yaml"


@pytest.fixture
def validator():
    """Schema validator instance."""
    return SchemaValidator()


def test_validate_valid_schema(validator, valid_schema_path):
    """Test validating a valid schema."""
    result = validator.validate(valid_schema_path)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.schema is not None
    assert result.schema["version"] == "1.0"


def test_validate_missing_file(validator, tmp_path):
    """Test validation with missing schema file."""
    missing_path = tmp_path / "missing.yaml"

    result = validator.validate(str(missing_path))

    assert result.valid is False
    assert len(result.errors) == 1
    assert result.errors[0].field == "file"
    assert "not found" in result.errors[0].message.lower()


def test_validate_invalid_yaml(validator, tmp_path):
    """Test validation with invalid YAML syntax."""
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("{ invalid yaml: [unclosed")

    result = validator.validate(str(invalid_yaml))

    assert result.valid is False
    assert len(result.errors) == 1
    assert result.errors[0].field == "yaml"
    assert "syntax" in result.errors[0].message.lower()


def test_validate_missing_required_root_field(validator, tmp_path):
    """Test validation with missing required root field."""
    schema = {
        "version": "1.0",
        "storage_tiers": {},
        "lifecycle": {}
        # Missing "query_processing"
    }

    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(yaml.dump(schema))

    result = validator.validate(str(schema_file))

    assert result.valid is False
    assert any("query_processing" in err.message for err in result.errors)


def test_validate_storage_tiers(validator, valid_schema_path):
    """Test validation of storage tier definitions."""
    result = validator.validate(valid_schema_path)

    assert result.valid is True
    assert "storage_tiers" in result.schema
    assert "kv" in result.schema["storage_tiers"]
    assert "vector" in result.schema["storage_tiers"]


def test_validate_lifecycle_stages(validator, valid_schema_path):
    """Test validation of lifecycle stages."""
    result = validator.validate(valid_schema_path)

    assert result.valid is True
    lifecycle = result.schema["lifecycle"]
    assert "stages" in lifecycle
    assert "rekindling" in lifecycle

    stage_names = [s["name"] for s in lifecycle["stages"]]
    assert "active" in stage_names
    assert "archived" in stage_names
