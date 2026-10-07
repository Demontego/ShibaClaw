import pytest
import subprocess
import os
import yaml
from unittest.mock import patch, mock_open

# Mock data for skill-size.sh tests
MOCK_SKILL_DIR = "mock_skill_dir"
MOCK_SKILL_SIZE = "4.0K"

# Mock data for validate_manifest.py tests
VALID_SKILL_MD_CONTENT = """
---
name: test-skill
description: A test skill.
---
# Test Skill
"""

INVALID_YAML_SKILL_MD_CONTENT = """
---
name: test-skill
description: A test skill.
  invalid_field: [-
---
# Test Skill
"""

MISSING_FIELD_SKILL_MD_CONTENT = """
---
name: test-skill
---
# Test Skill
"""

NO_FRONTMATTER_SKILL_MD_CONTENT = """
# Test Skill
"""


@pytest.fixture(autouse=True)
def mock_skill_dir(tmp_path):
    # Create a mock skill directory for testing skill-size.sh
    mock_dir = tmp_path / MOCK_SKILL_DIR
    mock_dir.mkdir()
    (mock_dir / "test_file.txt").write_text("some content")
    return mock_dir


def test_skill_size_script_success(mock_skill_dir):
    script_path = "skills/skill-validator/skill-size.sh"
    result = subprocess.run([script_path, str(mock_skill_dir)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == MOCK_SKILL_SIZE # du -sh output can vary, so this is a simplified check


def test_skill_size_script_no_arg():
    script_path = "skills/skill-validator/skill-size.sh"
    result = subprocess.run([script_path], capture_output=True, text=True)
    assert "Usage:" in result.stderr
    assert result.returncode == 1


def test_skill_size_script_invalid_path():
    script_path = "skills/skill-validator/skill-size.sh"
    result = subprocess.run([script_path, "/nonexistent/path"], capture_output=True, text=True)
    assert "Error:" in result.stderr
    assert result.returncode == 1


@patch('os.path.exists', return_value=True)
@patch('builtins.open', new_callable=mock_open, read_data=VALID_SKILL_MD_CONTENT)
@patch('yaml.safe_load', return_value={'name': 'test-skill', 'description': 'A test skill.'})
def test_validate_manifest_valid(mock_yaml_load, mock_file_open, mock_exists):
    from skills.skill_validator.validate_manifest import validate_manifest
    is_valid, message = validate_manifest("mock_path")
    assert is_valid is True
    assert "valid" in message


@patch('os.path.exists', return_value=False)
def test_validate_manifest_no_skill_md(mock_exists):
    from skills.skill_validator.validate_manifest import validate_manifest
    is_valid, message = validate_manifest("mock_path")
    assert is_valid is False
    assert "SKILL.md not found" in message


@patch('os.path.exists', return_value=True)
@patch('builtins.open', new_callable=mock_open, read_data=INVALID_YAML_SKILL_MD_CONTENT)
@patch('yaml.safe_load', side_effect=yaml.YAMLError("syntax error"))
def test_validate_manifest_invalid_yaml(mock_yaml_load, mock_file_open, mock_exists):
    from skills.skill_validator.validate_manifest import validate_manifest
    is_valid, message = validate_manifest("mock_path")
    assert is_valid is False
    assert "Error parsing YAML frontmatter" in message


@patch('os.path.exists', return_value=True)
@patch('builtins.open', new_callable=mock_open, read_data=MISSING_FIELD_SKILL_MD_CONTENT)
@patch('yaml.safe_load', return_value={'name': 'test-skill'})
def test_validate_manifest_missing_field(mock_yaml_load, mock_file_open, mock_exists):
    from skills.skill_validator.validate_manifest import validate_manifest
    is_valid, message = validate_manifest("mock_path")
    assert is_valid is False
    assert "Missing required field 'description'" in message


@patch('os.path.exists', return_value=True)
@patch('builtins.open', new_callable=mock_open, read_data=NO_FRONTMATTER_SKILL_MD_CONTENT)
def test_validate_manifest_no_frontmatter(mock_file_open, mock_exists):
    from skills.skill_validator.validate_manifest import validate_manifest
    is_valid, message = validate_manifest("mock_path")
    assert is_valid is False
    assert "does not start with YAML frontmatter" in message
