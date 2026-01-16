# LLM Training Scripts

This directory contains utility scripts for maintaining and updating the LLM training data validation libraries.

## Scripts

### update_validation_library.py

Updates the validation library with new schema definitions after refactoring.

**Usage:**
```bash
cd "Scaled JSON Development/LLM Training Data/Fewshot_llm/scripts"
python update_validation_library.py
```

**What it does:**
- Adds new field validation for refactored systems
- Updates statistical ranges for numeric fields
- Adds enumeration validation for new field types
- Creates automatic backup before updating
- Validates JSON after update

**Current Updates:**
- **Alchemy**: Added effectTags/effectParams validation
- **Skills**: Changed cost.mana/cooldown to numeric ranges (20-150, 20-600)

**Files Modified:**
- `../config/validation_libraries.json` (updated)
- `../config/validation_libraries.json.backup` (created automatically)

## When to Use

Run `update_validation_library.py` after:
- Refactoring JSON schemas
- Adding new field types
- Changing from string enums to numeric ranges
- Adding new tag systems

The script is idempotent - safe to run multiple times.
