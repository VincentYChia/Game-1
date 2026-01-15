# Prompts Directory - Structure and Workflow

This directory contains all system prompts used by the Few-Shot LLM runner. The structure is designed to maintain automatic generation of enhanced prompts while keeping each system's complete prompt in a single, readable file.

## Directory Structure

```
prompts/
├── components/               # Prompt components (not used directly by LLM)
│   ├── base/                 # Base prompts for each system
│   │   ├── system_1_base.md  # "You are a crafting expert..."
│   │   ├── system_2_base.md
│   │   └── ...
│   └── enhanced/             # Auto-generated field guidance (from training data)
│       ├── smithing_items_prompt.md
│       ├── refining_items_prompt.md
│       └── ...
└── system_prompts/           # FINAL COMPLETE PROMPTS (LLM uses these)
    ├── system_1.md           # Base + Enhanced combined
    ├── system_2.md
    └── ...
```

## Workflow

### 1. **Auto-Generation Pipeline**

When training data changes, run this pipeline to update prompts:

```bash
# Step 1: Analyze training data and extract validation libraries
python src/library_analyzer.py

# Step 2: Generate enhanced prompts with inline field guidance
python src/prompt_generator.py

# Step 3: Combine base + enhanced into final prompts
python src/update_system_prompts.py
```

**What happens:**
- `library_analyzer.py` → `config/validation_libraries.json`
- `prompt_generator.py` → `prompts/enhanced/*.md`
- `update_system_prompts.py` → `prompts/system_prompts/*.md`

### 2. **Manual Prompt Changes**

To change a system's base prompt:

1. Edit: `prompts/components/base/system_X_base.md`
2. Run: `python src/update_system_prompts.py`
3. Result: `prompts/system_prompts/system_X.md` updated

### 3. **LLM Runner Usage**

`run.py` loads prompts from `prompts/system_prompts/*.md`:

```python
# Each system gets its complete prompt from its own file
prompt_file = f"prompts/system_prompts/system_1.md"
system_prompt = open(prompt_file).read()
```

**Benefits:**
- Each system's complete prompt in ONE file
- Easy to read, edit, and version control
- Auto-generation maintained
- No JSON duplication

## System Types

### Generation Systems (1-11)

These generate game content (items, skills, enemies, etc.):

| System | Name | Template |
|--------|------|----------|
| 1 | Smithing Recipe→Item | smithing_items |
| 2 | Refining Recipe→Material | refining_items |
| 3 | Alchemy Recipe→Potion | alchemy_items |
| 4 | Engineering Recipe→Device | engineering_items |
| 5 | Enchanting Recipe→Enchantment | enchanting_recipes |
| 6 | Chunk→Hostile Enemy | hostiles |
| 7 | Drop Source→Material | refining_items |
| 8 | Chunk→Resource Node | node_types |
| 10 | Requirements→Skill | skills |
| 11 | Prerequisites→Title | titles |

### Placement Systems (1x2-5x2)

These determine optimal material placement on crafting grids:

| System | Name | Template |
|--------|------|----------|
| 1x2 | Smithing Placement | None |
| 2x2 | Refining Placement | None |
| 3x2 | Alchemy Placement | None |
| 4x2 | Engineering Placement | None |
| 5x2 | Enchanting Placement | None |

**Note:** Placement systems have no enhanced guidance (no template).

## Example: System 1 (Smithing)

### Base Prompt (`components/base/system_1_base.md`)
```
You are a crafting expert for an action fantasy sandbox RPG. Given smithing
recipes with materials and metadata, generate complete item definitions with
stats, tags, and properties. Return ONLY valid JSON matching the expected schema.
```

### Enhanced Prompt (`enhanced/smithing_items_prompt.md`)
```markdown
# Smithing Items - Field Guidelines

Generate a JSON object following this structure with inline guidance:

{
  "tier": 1,  // 1-4 (affects stat ranges below)
  "effectParams": {
    "baseDamage": 0,  // T1: 10.0-30.0, T2: 18.0-50.0, T3: 37.0-45.0
  },
  ...
}
```

### Final Prompt (`system_prompts/system_1.md`)
```
[Base prompt]

[Enhanced prompt]
```

**Total:** ~3,340 characters - complete, no duplication

## Maintenance

### When to Regenerate

Run the auto-generation pipeline when:
- Training data changes (new examples added)
- Validation libraries need updating
- Stat ranges change
- New tags/enums discovered

### Testing Changes

After updating prompts, test with:

```bash
# Test loading
python -c "import run; run.load_config()"

# Test generation
python run.py
# Select a single system to test
```

### Validation

Check generated content with:

```bash
python src/comprehensive_validation_test.py
```

## Benefits of This Structure

✅ **Each system has ONE complete prompt file**
✅ **Auto-generation maintained** (library_analyzer → prompt_generator → update_system_prompts)
✅ **No duplication** (old system_prompts.json had 3x duplication)
✅ **Easy to read** (markdown, not JSON)
✅ **Easy to edit** (edit base, run update script)
✅ **Version control friendly** (one file per system)
✅ **Modular** (base + enhanced components)

## Migration from Old System

**Old:** `config/system_prompts.json` (single JSON with massive duplication)
**New:** `prompts/system_prompts/system_X.md` (individual files, no duplication)

The old system_prompts.json has been archived to `archive/system_prompts.json.old`.

---

**Last Updated:** 2026-01-14
**Maintained By:** LLM Training System
