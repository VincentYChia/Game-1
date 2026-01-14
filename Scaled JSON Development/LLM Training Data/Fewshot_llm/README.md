# Few-Shot LLM Training System
**Production-Ready Content Generation System**

Clean, modular system for generating game JSON content using few-shot learning with Claude.

---

## 🚀 Quick Start

### Run the System
```bash
python run.py
```

Interactive menu lets you:
1. Generate content for all systems
2. Test a single system
3. Run a range of systems
4. Select specific systems

### Manual Prompt Tuning
**See**: [`MANUAL_TUNING_GUIDE.md`](MANUAL_TUNING_GUIDE.md) - Complete guide to editing prompts

**Quick**: Edit any file in `prompts/system_prompts/` and run `python run.py`

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **[MANUAL_TUNING_GUIDE.md](MANUAL_TUNING_GUIDE.md)** | ⭐ **START HERE** - How to edit prompts |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | Complete system overview and file organization |
| **[VALIDATION_ENHANCEMENT_SUMMARY.md](VALIDATION_ENHANCEMENT_SUMMARY.md)** | How validation works |
| **[PROMPT_REFACTORING_SUMMARY.md](PROMPT_REFACTORING_SUMMARY.md)** | Prompt system architecture |
| [`prompts/README.txt`](prompts/README.txt) | Detailed prompt documentation |

---

## 📁 System Overview

### 15 Generation Systems

**Content Generation (10)**:
- System 1: Smithing Items (weapons, armor, tools)
- System 2: Refining Materials (ingots, planks)
- System 3: Alchemy Items (potions, consumables)
- System 4: Engineering Devices (turrets, traps, bombs)
- System 5: Enchantments
- System 6: Enemies
- System 7: Loot Drops
- System 8: Resource Nodes
- System 10: Skills
- System 11: Titles

**Placement Generation (5)**:
- Systems 1x2, 2x2, 3x2, 4x2, 5x2 for each crafting discipline

---

## 🎯 Key Features

✅ **One prompt per system** - Each system has its own `.txt` file
✅ **Data-driven validation** - Checks ranges, tags, enums
✅ **Auto-generated guidance** - Prompts include field-by-field help
✅ **Manual tuning ready** - Edit prompts directly in text editor
✅ **Comprehensive testing** - Built-in validation test suite
✅ **Production ready** - Clean, organized, documented

---

## 🔧 Common Tasks

### Edit Prompts
```bash
# Open in text editor:
prompts/system_prompts/system_1.txt

# Test your changes:
python run.py
```

### Generate Content
```bash
python run.py
# Select system(s) to run
# Check outputs/ directory
```

### Validate Outputs
```bash
python src/comprehensive_validation_test.py
# Results: outputs/validation_test_results.json
```

### Update Enhanced Prompts (after training data changes)
```bash
python src/library_analyzer.py
python src/prompt_generator.py
python src/update_system_prompts.py
```

---

## 📂 Directory Structure

```
Fewshot_llm/
├── run.py                        # ⭐ Main entry point
├── prompts/
│   ├── system_prompts/           # ⭐ Edit these files
│   │   ├── system_1.txt          # Complete prompt for System 1
│   │   ├── system_2.txt
│   │   └── ...
│   ├── components/               # Prompt components
│   │   ├── base/                 # Base prompts
│   │   └── enhanced/             # Auto-generated guidance
│   └── README.txt
├── config/
│   ├── system_metadata.json      # System names and templates
│   ├── test_inputs.json          # Test inputs
│   └── validation_libraries.json # Validation data
├── examples/
│   └── few_shot_examples.json    # 83 training examples
├── src/
│   ├── llm_runner.py             # LLM API integration
│   ├── validator.py              # Multi-layer validation
│   ├── library_analyzer.py       # Extract validation data
│   ├── prompt_generator.py       # Generate enhanced prompts
│   └── ...
├── outputs/                      # Generated content
└── archive/                      # Archived files
```

**Full details**: See [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)

---

## ⚙️ Configuration

### API Key
Edit `run.py`:
```python
API_KEY = "your-api-key-here"
MODEL = "claude-sonnet-4-20250514"
```

### Parameters
```python
MAX_TOKENS = 2000
TEMPERATURE = 1.0
TOP_P = 0.999
```

---

## ✅ Validation System

### Three-Layer Validation

1. **Structure**: JSON format, required fields, data types
2. **Ranges**: Stats within ±33% of tier-based ranges
3. **Content**: Tags and enums match libraries

### Example Warnings
```
⚠️  Range warning: baseDamage=35 outside T1 range [10-30] by >33%
⚠️  Tag warning: tag 'fire' not found in template library
⚠️  Enum warning: rarity='epic' not valid. Options: common, uncommon, rare
```

---

## 📊 Statistics

- **15 systems** (10 content + 5 placement)
- **83 training examples** across all systems
- **118 stat ranges** extracted from training data
- **269 metadata tags** identified
- **38 enum fields** detected
- **~2,500 lines** of source code
- **81% size reduction** vs previous system

---

## 🔄 Workflows

### Daily Tuning
1. Edit `prompts/system_prompts/system_X.txt`
2. Run `python run.py` → select system
3. Check `outputs/` directory
4. Validate with `python src/comprehensive_validation_test.py`
5. Iterate

### After Training Data Changes
1. `python src/library_analyzer.py`
2. `python src/prompt_generator.py`
3. `python src/update_system_prompts.py`
4. Test a few systems

### Comprehensive Testing
1. `python run.py` → option 1 (all systems)
2. `python src/comprehensive_validation_test.py`
3. Review results
4. Fix issues
5. Retest

---

## 🎓 Getting Started

1. ✅ **Read**: [`MANUAL_TUNING_GUIDE.md`](MANUAL_TUNING_GUIDE.md)
2. ✅ **Open**: `prompts/system_prompts/system_1.txt`
3. ✅ **Run**: `python run.py` → select system 1
4. ✅ **Check**: `outputs/` directory
5. ✅ **Experiment**: Edit prompts and iterate!

---

## 🛠️ Troubleshooting

### Can't find prompts
- They're in `prompts/system_prompts/system_X.txt`
- Not in `config/` anymore (that's old)

### Validation fails
- Check ±33% tolerance exists for ranges
- Re-run `library_analyzer.py` if training data changed
- Review `outputs/validation_test_results.json`

### LLM ignores instructions
- Move important instructions to TOP of prompt
- Use stronger language (CRITICAL, REQUIRED)
- Add examples showing correct behavior

**More troubleshooting**: See [`MANUAL_TUNING_GUIDE.md`](MANUAL_TUNING_GUIDE.md#troubleshooting)

---

## 📝 Recent Changes

### 2026-01-14: Major Refactoring
- ✅ Eliminated 81% prompt duplication
- ✅ One `.txt` file per system
- ✅ Enhanced validation (ranges, tags, enums)
- ✅ Auto-generated field guidance
- ✅ Complete documentation suite
- ✅ Production-ready organization

**Details**: See [`PROMPT_REFACTORING_SUMMARY.md`](PROMPT_REFACTORING_SUMMARY.md)

---

## 🎯 Use Cases

- **Generate game content** at scale
- **Train fine-tuned models** with consistent data
- **Test prompt variations** quickly
- **Validate game definitions** automatically
- **Iterate on content generation** strategies

---

## 🤝 Contributing

When modifying:
1. Edit prompts in `prompts/system_prompts/`
2. Keep config in JSON files
3. Keep code modular in `src/`
4. Document changes
5. Test before committing

---

## 📚 Additional Resources

- **Training Data**: `examples/few_shot_examples.json`
- **Templates**: `../../json_templates/`
- **Game Integration**: `Game-1-modular/` (material database)
- **Archived Files**: `archive/` (old versions)

---

**System is ready for production use! 🚀**

For detailed guidance, see [`MANUAL_TUNING_GUIDE.md`](MANUAL_TUNING_GUIDE.md)
