# Few-Shot LLM System

Clean, modular system for generating game JSON content using few-shot learning with Claude.

## 📁 Folder Structure

```
Fewshot_llm/
├── config/                          # Configuration files
│   ├── system_prompts.json          # System prompts for each LLM (13 systems)
│   └── test_inputs.json             # Test inputs for validation (9 systems)
├── examples/                        # Training data
│   └── few_shot_examples.json       # 94 extracted examples across 15 systems
├── src/                             # Source code
│   ├── llm_runner.py                # LLM execution logic
│   └── validator.py                 # JSON validation logic
├── outputs/                         # Generated outputs (organized by date)
│   └── [timestamp]/                 # Each run gets its own folder
├── archive/                         # Old/backup files
├── run.py                           # Main entry point
└── README.md                        # This file
```

## 🚀 Quick Start

### Run the LLM System

```bash
python run.py
```

This will:
1. Load all configuration files
2. Show an interactive menu
3. Let you select which systems to test
4. Run the selected systems
5. Save outputs to `outputs/` folder
6. Validate the results

### Interactive Menu Options

1. **Run ALL systems** - Tests all 9 systems with test inputs
2. **Run a SINGLE system** - Pick one system (e.g., "1" for Smithing)
3. **Run a RANGE** - Test consecutive systems (e.g., "1-6")
4. **Run SPECIFIC systems** - Pick multiple (e.g., "1,3,5")
5. **Exit** - Quit the program

### Example Usage

```bash
$ python run.py

Loading configuration...
✓ Loaded 13 system prompts
✓ Loaded 9 test inputs
✓ Loaded 94 total examples

================================================================================
FEW-SHOT LLM RUNNER - SELECT SYSTEMS TO TEST
================================================================================

Options:
  1. Run ALL systems with test inputs
  2. Run a SINGLE system
  3. Run a RANGE of systems (e.g., 1-6)
  4. Run SPECIFIC systems (e.g., 1,3,5)
  5. Exit

Enter your choice (1-5): 2

Enter system key (1, 2, 3, 5, 6, 7, 8, 10, 11): 1

✓ Selected 1 system(s): 1

================================================================================
Running System 1: Smithing Recipe→Item
================================================================================
...
```

## 📋 Available Systems

### Systems with Test Inputs (Ready to Run)

| System | Name | Description | Examples |
|--------|------|-------------|----------|
| 1 | Smithing Recipe→Item | Generate weapons/armor from recipes | 8 |
| 2 | Refining Recipe→Material | Generate materials (ingots, planks) | 8 |
| 3 | Alchemy Recipe→Potion | Generate potions/consumables | 3 |
| 5 | Enchanting Recipe→Enchantment | Generate enchantments | 8 |
| 6 | Chunk→Hostile Enemy | Generate enemy definitions | 8 |
| 7 | Drop Source→Material | Generate materials from drops | 8 |
| 8 | Chunk→Resource Node | Generate resource nodes | 8 |
| 10 | Requirements→Skill | Generate skill definitions | 8 |
| 11 | Prerequisites→Title | Generate player titles | 8 |

### Placement Systems (No Test Inputs Yet)

| System | Name | Examples |
|--------|------|----------|
| 1x2 | Smithing Placement | 8 |
| 2x2 | Refining Placement | 8 |
| 3x2 | Alchemy Placement | 3 |
| 5x2 | Enchanting Placement | 8 |

### Not Yet Implemented

| System | Name | Examples |
|--------|------|----------|
| 4 | Engineering Recipe→Device | 0 |
| 4x2 | Engineering Placement | 0 |

## 🔧 Configuration

### API Key

Edit `run.py` to set your Anthropic API key:

```python
API_KEY = "your-api-key-here"
```

### Model Parameters

Adjust in `run.py`:

```python
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000
TEMPERATURE = 1.0
TOP_P = 0.999
```

### Adding New Systems

1. **Add system prompt** to `config/system_prompts.json`:
```json
{
  "4": {
    "name": "Engineering Recipe→Device",
    "prompt": "You are an engineering expert for an action fantasy sandbox RPG..."
  }
}
```

2. **Add test input** to `config/test_inputs.json`:
```json
{
  "4": {
    "name": "Engineering Recipe→Device",
    "prompt": "Create a device definition for this recipe: {...}"
  }
}
```

3. **Add examples** to `examples/few_shot_examples.json`:
```json
{
  "4": [
    {"input": {...}, "output": {...}},
    {"input": {...}, "output": {...}}
  ]
}
```

4. Run: `python run.py`

## 📊 Output Format

Each run creates a JSON file in `outputs/` with:

```json
{
  "timestamp": "2026-01-13T22:42:32.123456",
  "system_key": "1",
  "system_name": "Smithing Recipe→Item",
  "model": "claude-sonnet-4-20250514",
  "parameters": {
    "max_tokens": 2000,
    "temperature": 1.0,
    "top_p": 0.999
  },
  "system_prompt": "You are a crafting expert...",
  "few_shot_count": 8,
  "test_prompt": "Create an item definition for...",
  "response": "{...JSON output...}",
  "usage": {
    "input_tokens": 3874,
    "output_tokens": 319
  }
}
```

## ✅ Validation

The validator checks:
- JSON structure validity
- Required fields presence
- Type correctness
- Value ranges (when applicable)

Validation uses templates from: `../../json_templates/`

## 📈 Recent Test Results

**Date**: 2026-01-13
**Model**: claude-sonnet-4-20250514
**Systems Tested**: 9
**Validation Success**: 91.7%
**Total Tokens**: 26,714

See `TEST_RESULTS.md` for detailed analysis.

## 🎯 Use Cases

### Generate Training Data for Fine-Tuning

```bash
# Run all systems multiple times to build dataset
python run.py
# Select option 1 (Run ALL systems)
```

### Test Individual System Quality

```bash
# Test one system
python run.py
# Select option 2 (Run SINGLE system)
```

### Validate New Examples

```bash
# Add examples to examples/few_shot_examples.json
# Run system to test quality
python run.py
```

## 🧹 Maintenance

### Clean Old Outputs

```bash
# Organize outputs by date
mkdir outputs/YYYY-MM-DD_description/
mv outputs/system_*.json outputs/YYYY-MM-DD_description/
```

### Backup Configuration

```bash
# Configuration is in JSON - easy to version control
git add config/ examples/
git commit -m "Update examples and prompts"
```

## 🛠️ Troubleshooting

### No Test Inputs Found

- Check that `config/test_inputs.json` exists
- Verify system keys match between files

### Validation Fails

- Check JSON structure in response
- Verify template exists in `../../json_templates/`
- Review required fields in validator

### API Errors

- Verify API key is correct
- Check API rate limits
- Ensure model name is valid

## 📝 Development

### Project Structure Philosophy

- **config/** - Data files, no code
- **examples/** - Training data, versioned
- **src/** - Clean, modular Python code
- **run.py** - Simple entry point, minimal logic
- **outputs/** - Generated data, not versioned

### Code Organization

- **llm_runner.py** - Handles API calls, no business logic
- **validator.py** - Standalone validation, no API dependencies
- **run.py** - Orchestrates components, handles user interaction

### Adding Features

1. Create new module in `src/`
2. Import in `run.py`
3. Keep concerns separated
4. Configuration in JSON, logic in Python

## 📚 Related Files

- `Few_shot_LLM.py` - Original monolithic script (archived)
- `TEST_RESULTS.md` - Comprehensive test analysis
- `../../json_templates/` - Validation templates

## 🤝 Contributing

When modifying:
1. Keep config in JSON files
2. Keep code modular in `src/`
3. Document changes in README
4. Test all systems before committing
