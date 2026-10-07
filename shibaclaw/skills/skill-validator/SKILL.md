---
name: skill-validator
description: Provides tools to validate skill manifests and calculate skill directory sizes.
---

# Skill Validator

This skill offers utilities for maintaining the quality and integrity of other skills.

## `skill-size.sh`

Calculates the disk usage of a given skill directory.

**Usage:**
```bash
skills/skill-validator/skill-size.sh <path_to_skill_directory>
```

**Example:**
```bash
skills/skill-validator/skill-size.sh skills/my-awesome-skill
```

## `validate_manifest.py`

Validates the `SKILL.md` manifest of a given skill directory. It checks for the presence of `SKILL.md` and verifies that its YAML frontmatter contains the required `name` and `description` fields.

**Usage:**
```bash
python skills/skill-validator/validate_manifest.py <path_to_skill_directory>
```

**Example:**
```bash
python skills/skill-validator/validate_manifest.py skills/my-awesome-skill
```
