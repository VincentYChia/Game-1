# Project Structure - Few-Shot LLM Training System
**Date**: 2026-01-14
**Status**: Production Ready

---

## Overview

This is a complete few-shot learning system for generating game content (items, skills, enemies, etc.) using Claude with training data. The system features:

- ✅ 15 generation systems (10 content + 5 placement)
- ✅ Data-driven validation (ranges, tags, enums)
- ✅ Auto-generated enhanced prompts
- ✅ One prompt file per system
- ✅ Complete test suite
- ✅ Manual tuning ready

---

## Directory Structure

```
Fewshot_llm/
│
├── 📄 run.py                        # ⭐ MAIN ENTRY POINT
│   └── Interactive menu to generate content
│
├── 📁 prompts/                      # ⭐ PROMPT FILES (EDIT HERE)
│   ├── system_prompts/              # Complete prompts LLM uses
│   │   ├── system_1.txt             # Smithing items
│   │   ├── system_2.txt             # Refining materials
│   │   ├── system_3.txt             # Alchemy potions
│   │   ├── system_4.txt             # Engineering devices
│   │   ├── system_5.txt             # Enchantments
│   │   ├── system_6.txt             # Enemies
│   │   ├── system_7.txt             # Loot drops
│   │   ├── system_8.txt             # Resource nodes
│   │   ├── system_10.txt            # Skills
│   │   ├── system_11.txt            # Titles
│   │   ├── system_1x2.txt           # Smithing placement
│   │   ├── system_2x2.txt           # Refining placement
│   │   ├── system_3x2.txt           # Alchemy placement
│   │   ├── system_4x2.txt           # Engineering placement
│   │   └── system_5x2.txt           # Enchanting placement
│   ├── components/                  # Prompt components
│   │   ├── base/                    # Base prompts (human-written)
│   │   └── enhanced/                # Auto-generated guidance
│   └── README.txt                   # Detailed prompt docs
│
├── 📁 config/                       # Configuration files
│   ├── system_metadata.json         # System names and templates
│   ├── test_inputs.json             # Test inputs for each system
│   └── validation_libraries.json   # Auto-generated validation data
│
├── 📁 examples/                     # Training data
│   └── few_shot_examples.json       # 83 examples across all systems
│
├── 📁 src/                          # Source code
│   ├── llm_runner.py                # LLM API integration
│   ├── validator.py                 # Multi-layer validation
│   ├── library_analyzer.py          # Extracts validation data
│   ├── prompt_generator.py          # Generates enhanced prompts
│   ├── update_system_prompts.py     # Combines base + enhanced
│   ├── material_enricher.py         # Enriches inputs with material data
│   ├── comprehensive_validation_test.py  # Test suite
│   ├── visualize_placement.py       # ASCII placement visualizer
│   ├── ui_visualizer.py             # Game UI visualizer (needs pygame)
│   └── refactor_prompts.py          # Prompt refactoring script
│
├── 📁 outputs/                      # Generated outputs
│   ├── validation_test_results.json # Latest validation results
│   └── (timestamped output files)
│
├── 📁 archive/                      # Archived files
│   ├── old_outputs/                 # Old test outputs
│   ├── system_prompts.json.old      # Old monolithic prompts
│   └── (other archived files)
│
├── 📄 MANUAL_TUNING_GUIDE.md        # ⭐ HOW TO EDIT PROMPTS
├── 📄 VALIDATION_ENHANCEMENT_SUMMARY.md  # Validation system docs
├── 📄 PROMPT_REFACTORING_SUMMARY.md      # Prompt refactoring details
├── 📄 PROJECT_STRUCTURE.md          # This file
└── 📄 README.md                     # Project overview
```

---

## Key Files Quick Reference

### For Manual Tuning
| File | Purpose |
|------|---------|
| `MANUAL_TUNING_GUIDE.md` | **START HERE** - Complete guide to editing prompts |
| `prompts/system_prompts/*.txt` | Edit these files to change what LLM sees |
| `run.py` | Run this to test your changes |

### For Understanding the System
| File | Purpose |
|------|---------|
| `PROJECT_STRUCTURE.md` | This file - system overview |
| `VALIDATION_ENHANCEMENT_SUMMARY.md` | How validation works |
| `PROMPT_REFACTORING_SUMMARY.md` | How prompts are organized |
| `prompts/README.txt` | Detailed prompt system documentation |

### For Development
| File | Purpose |
|------|---------|
| `src/library_analyzer.py` | Re-analyze training data |
| `src/prompt_generator.py` | Regenerate enhanced prompts |
| `src/update_system_prompts.py` | Update final prompts |
| `src/validator.py` | Modify validation rules |

---

## Workflows

### 🎯 Manual Prompt Tuning (Most Common)

1. **Edit prompt**: Open `prompts/system_prompts/system_X.txt`
2. **Test**: `python run.py` → select system
3. **Check**: Look in `outputs/` directory
4. **Validate**: `python src/comprehensive_validation_test.py`
5. **Iterate**: Repeat until satisfied

**Time**: 5-15 minutes per iteration

### 🔄 Update Enhanced Prompts (After Training Data Changes)

1. **Analyze**: `python src/library_analyzer.py`
2. **Generate**: `python src/prompt_generator.py`
3. **Update**: `python src/update_system_prompts.py`
4. **Test**: Run a few systems to verify

**Time**: 2-3 minutes

### ✅ Comprehensive Testing

1. **Generate**: `python run.py` → option 1 (all systems)
2. **Validate**: `python src/comprehensive_validation_test.py`
3. **Review**: Check `outputs/validation_test_results.json`
4. **Fix**: Edit prompts for any issues
5. **Retest**: Repeat until clean

**Time**: 10-20 minutes

---

## System Mapping

### Content Generation Systems

| System | File | Template | Generates |
|--------|------|----------|-----------|
| 1 | `system_1.txt` | smithing_items | Weapons, armor, tools |
| 2 | `system_2.txt` | refining_items | Ingots, planks, materials |
| 3 | `system_3.txt` | alchemy_items | Potions, consumables |
| 4 | `system_4.txt` | engineering_items | Turrets, traps, bombs |
| 5 | `system_5.txt` | enchanting_recipes | Enchantments |
| 6 | `system_6.txt` | hostiles | Enemy definitions |
| 7 | `system_7.txt` | refining_items | Loot drops |
| 8 | `system_8.txt` | node_types | Resource nodes |
| 10 | `system_10.txt` | skills | Player skills |
| 11 | `system_11.txt` | titles | Achievement titles |

### Placement Systems

| System | File | Generates |
|--------|------|-----------|
| 1x2 | `system_1x2.txt` | Smithing grid placements |
| 2x2 | `system_2x2.txt` | Refining hub placements |
| 3x2 | `system_3x2.txt` | Alchemy sequence placements |
| 4x2 | `system_4x2.txt` | Engineering slot placements |
| 5x2 | `system_5x2.txt` | Enchanting pattern placements |

---

## Validation System

### Three-Layer Validation

1. **Structure Validation**
   - Checks JSON structure against template
   - Validates data types
   - Ensures required fields present

2. **Range Validation**
   - Checks numeric values against tier-based ranges
   - ±33% tolerance allowed
   - Example: T1 damage 10-30, acceptable: 6.7-40

3. **Content Validation**
   - **Tags**: Must exist in template-specific library
   - **Enums**: Must use known values (category, type, etc.)
   - Shows valid options when mismatch found

### Validation Libraries

Auto-generated from training data:
- **Stat ranges**: Min/max/mean/median by tier
- **Tag libraries**: Valid tags per template
- **Enum values**: Valid options for constrained fields

**File**: `config/validation_libraries.json`

---

## Prompt System

### How Prompts Work

Each system has **one complete prompt file**:
```
prompts/system_prompts/system_1.txt
```

This file contains:
1. **Base prompt** (human-written)
   - Core task description
   - Basic instructions
2. **Enhanced guidance** (auto-generated)
   - Field-by-field guidance
   - Stat ranges by tier
   - Valid tag lists
   - Enum options

### Prompt Generation Pipeline

```
Training Data
    ↓
library_analyzer.py → validation_libraries.json
    ↓
prompt_generator.py → prompts/enhanced/*.txt
    ↓
update_system_prompts.py → prompts/system_prompts/*.txt
    ↓
run.py → Uses final prompts
```

### Where to Edit

| Goal | Edit This | Then Run |
|------|-----------|----------|
| Quick tweaks | `prompts/system_prompts/system_X.txt` | `python run.py` |
| Change base instructions | `prompts/components/base/system_X_base.txt` | `python src/update_system_prompts.py` |
| Update after training data change | N/A | Full pipeline (3 commands) |

---

## Statistics

### Training Data
- **83 total examples** across all systems
- **35 smithing items** (most complete)
- **25 hostiles** (enemies)
- **30 skills**
- **10 titles**

### Validation Libraries
- **118 stat ranges** extracted
- **269 metadata tags** identified
- **38 enum fields** detected
- **9 templates** analyzed

### Code
- **~2,500 lines** of source code
- **10 Python modules** in src/
- **15 system prompts** (one per system)
- **81% size reduction** vs old system

---

## Recent Changes

### 2026-01-14: Major Refactoring

1. **Prompt Consolidation**
   - Eliminated 81% duplication
   - One file per system
   - Changed .md → .txt for clarity

2. **Validation Enhancement**
   - Added range checking (±33% tolerance)
   - Added tag validation
   - Added enum validation
   - Improved enum detection

3. **System Organization**
   - Created components structure
   - Separated base from enhanced prompts
   - Archived old files
   - Created comprehensive docs

### Commits
- `REFACTOR: Consolidate system prompts` (51 files)
- `CHANGE: Rename .md to .txt` (44 files)
- `FEAT: Enhanced validator + Library-driven prompts` (11 files)

---

## Common Tasks

### Generate Content for One System
```bash
python run.py
# Select: 2 (Run a SINGLE system)
# Enter: 1 (for system 1, smithing)
# Output: outputs/system_1_TIMESTAMP.json
```

### Test All Systems
```bash
python run.py
# Select: 1 (Run ALL systems)
# Wait for completion
# Check: outputs/ directory
```

### Validate Outputs
```bash
python src/comprehensive_validation_test.py
# Results: outputs/validation_test_results.json
```

### Update Prompts
```bash
# After editing base prompts:
python src/update_system_prompts.py

# After training data changes:
python src/library_analyzer.py
python src/prompt_generator.py
python src/update_system_prompts.py
```

### Visualize Placements
```bash
python src/visualize_placement.py
# Shows ASCII visualization of placement outputs
```

---

## Dependencies

### Python Packages
- `anthropic` - Claude API
- `json`, `pathlib` - Built-in
- `dataclasses` - Built-in

### Optional
- `pygame` - For UI visualizer (not required)

### External
- Game codebase (`Game-1-modular`) - For material database lookups

---

## API Configuration

Edit `run.py` to change:
```python
API_KEY = "sk-ant-api03-..."  # Your API key
MODEL = "claude-sonnet-4-20250514"  # Model to use
MAX_TOKENS = 2000
TEMPERATURE = 1.0
TOP_P = 0.999
```

---

## Troubleshooting

### "No such file or directory"
- Run from: `Fewshot_llm/` directory
- Command: `python run.py` (not `python src/run.py`)

### "Template not found"
- Check: `config/system_metadata.json`
- Verify: Template names match directories

### "Validation always fails"
- Check: `±33%` tolerance exists for ranges
- Update: Re-run `library_analyzer.py` if training data changed
- Review: `outputs/validation_test_results.json` for details

### "Outputs are empty"
- Check: API key is valid
- Check: Model name is correct
- Check: Test inputs exist in `config/test_inputs.json`

---

## Next Steps

1. ✅ **Read**: `MANUAL_TUNING_GUIDE.md`
2. ✅ **Open**: `prompts/system_prompts/system_1.txt`
3. ✅ **Run**: `python run.py` → select system 1
4. ✅ **Check**: `outputs/` directory
5. ✅ **Edit**: Prompts based on results
6. ✅ **Iterate**: Repeat until satisfied

---

**System is ready for manual tuning! 🚀**
