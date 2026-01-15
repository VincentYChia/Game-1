# Archive Folder

This folder contains the original implementation files before the reorganization into a modular structure.

## Files

### Few_shot_LLM.py (18KB)
Original monolithic script that contained:
- All system prompts (hardcoded)
- Example loading logic
- API calling logic
- Interactive menu
- Output saving

**Replaced by**: Modular structure with `run.py`, `src/llm_runner.py`, and JSON config files

### extracted_examples.py (115KB)
Giant Python file with hardcoded few-shot examples for all systems.
- 94 examples across 15 systems
- Each example as Python dict

**Replaced by**: `examples/few_shot_examples.json` (clean JSON format)

### batch_runner.py (8.2KB)
Utility script for running multiple systems in batch mode.
- Automated testing
- Validation
- Summary reports

**Replaced by**: Interactive menu in `run.py` with options for all/single/range/specific systems

### example_extractor.py (8.5KB)
Utility script for extracting examples from training data.
- Reads from `../system*/train.json`
- Extracts 8 examples per system (2 per tier)
- Generates `extracted_examples.py`

**Purpose**: One-time extraction tool (already run)

## Why Archived?

These files represent the "old way" of doing things:
- Hardcoded configuration in Python files
- Monolithic scripts mixing concerns
- Large data files as Python code

The new structure separates:
- **Configuration** → JSON files in `config/`
- **Training data** → JSON files in `examples/`
- **Code logic** → Modular Python in `src/`
- **Entry point** → Simple `run.py`

## Should You Use These?

**No.** Use the new modular structure instead:

```bash
# Old way (don't use)
python archive/Few_shot_LLM.py

# New way (use this)
python run.py
```

The new structure is:
- Easier to understand
- Easier to modify (edit JSON, not code)
- Easier to maintain
- Better organized

## Preservation

These files are kept for:
1. **Historical reference** - shows evolution of the system
2. **Backup** - in case something breaks
3. **Learning** - shows what NOT to do

If you need to restore something, these files contain all the original logic.
