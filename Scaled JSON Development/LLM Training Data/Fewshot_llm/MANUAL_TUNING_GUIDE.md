# Manual Prompt Tuning Guide
**For**: Few-Shot LLM Training System
**Date**: 2026-01-14

---

## Quick Start

### Where to Edit Prompts

All system prompts are in: **`prompts/system_prompts/`**

Each system has ONE complete file:
```
prompts/system_prompts/
├── system_1.txt    ← Edit this to change System 1 (Smithing Items)
├── system_2.txt    ← System 2 (Refining Materials)
├── system_3.txt    ← System 3 (Alchemy Potions)
...
└── system_11.txt   ← System 11 (Titles)
```

**These are the EXACT prompts the LLM receives.**
Open in any text editor to see/edit exactly what the LLM sees.

---

## System Overview

| File | System | What it Generates |
|------|--------|-------------------|
| `system_1.txt` | Smithing Recipe→Item | Weapons, armor, tools from recipes |
| `system_2.txt` | Refining Recipe→Material | Ingots, planks from raw materials |
| `system_3.txt` | Alchemy Recipe→Potion | Potions and consumables |
| `system_4.txt` | Engineering Recipe→Device | Turrets, traps, bombs |
| `system_5.txt` | Enchanting Recipe→Enchantment | Enchantments for items |
| `system_6.txt` | Chunk→Hostile Enemy | Enemy definitions |
| `system_7.txt` | Drop Source→Material | Loot drops |
| `system_8.txt` | Chunk→Resource Node | Gatherable resource nodes |
| `system_10.txt` | Requirements→Skill | Player skills |
| `system_11.txt` | Prerequisites→Title | Achievement titles |
| `system_1x2.txt` | Smithing Placement | Grid placements for smithing |
| `system_2x2.txt` | Refining Placement | Grid placements for refining |
| `system_3x2.txt` | Alchemy Placement | Sequence placements for alchemy |
| `system_4x2.txt` | Engineering Placement | Slot placements for engineering |
| `system_5x2.txt` | Enchanting Placement | Pattern placements for enchanting |

---

## Prompt Structure

Each prompt file has two parts:

### 1. Base Prompt (Human-Written)
The opening instruction:
```
You are a crafting expert for an action fantasy sandbox RPG. Given smithing recipes
with materials and metadata, generate complete item definitions with stats, tags, and
properties. Return ONLY valid JSON matching the expected schema.
```

### 2. Enhanced Guidance (Auto-Generated)
Detailed field-by-field guidance with:
- Valid enum options
- Stat ranges by tier
- Tag libraries
- Example structure

**Example** (from system_1.txt):
```
# Smithing Items - Field Guidelines

{
  "tier": 1,  // 1-4 (affects stat ranges below)
  "effectParams": {
    "baseDamage": 0,  // T1: 10.0-30.0, T2: 18.0-50.0, T3: 37.0-45.0
  },
  "effectTags": ["Pick 2-5 from: burn, crushing, fire, physical, ..."]
}
```

---

## How to Edit Prompts

### Option 1: Edit Complete Prompt Directly

**Best for**: Quick tweaks, adding instructions

1. Open: `prompts/system_prompts/system_X.txt`
2. Edit the text
3. Save
4. Test with: `python run.py`

**Example Changes**:
- Add emphasis: "IMPORTANT: Always include weight stat"
- Change tone: "Be creative with narratives"
- Add constraints: "Never use damage values below 10"

### Option 2: Edit Base + Regenerate

**Best for**: Changing core instructions while keeping auto-generated guidance

1. Edit: `prompts/components/base/system_X_base.txt`
2. Run: `python src/update_system_prompts.py`
3. Result: `prompts/system_prompts/system_X.txt` updated

**When to use**:
- Changing the overall task description
- Modifying the base instructions
- Keeping auto-generated stat ranges/tags

### Option 3: Regenerate Everything

**Best for**: After training data changes

1. Run: `python src/library_analyzer.py`
2. Run: `python src/prompt_generator.py`
3. Run: `python src/update_system_prompts.py`

**This will**:
- Re-analyze training data
- Update stat ranges
- Update tag libraries
- Regenerate all enhanced guidance

---

## Testing Your Changes

### Test a Single System

```bash
python run.py
# Select option 2 (Run a SINGLE system)
# Enter system key (e.g., 1)
# Check the output in outputs/
```

### Test All Systems

```bash
python run.py
# Select option 1 (Run ALL systems)
# Wait for completion
# Check outputs/ directory
```

### Validate Outputs

```bash
python src/comprehensive_validation_test.py
```

This checks:
- ✓ Stat ranges (±33% tolerance)
- ✓ Tag validity
- ✓ Enum values
- ✓ JSON structure

---

## Common Tuning Scenarios

### Scenario 1: LLM Using Wrong Tags

**Problem**: Output has tags not in the library

**Solution**: Make tags more explicit in prompt

Edit `prompts/system_prompts/system_1.txt`:
```
CRITICAL: Only use tags from this list:
["1H", "2H", "axe", "bow", "sword", ...]

DO NOT create new tags. Pick ONLY from the list above.
```

### Scenario 2: Stats Out of Range

**Problem**: Stats too high/low for tier

**Solution**: Emphasize range constraints

Add to prompt:
```
STRICT REQUIREMENT: All stats MUST be within tier ranges.
Example: T1 baseDamage must be 10.0-30.0, NO EXCEPTIONS.
```

### Scenario 3: Poor Narratives

**Problem**: Narratives are generic or boring

**Solution**: Add narrative guidelines

Add to prompt:
```
Narrative Guidelines:
- Be specific (not "a good sword" but "a blade forged in dragon fire")
- Include sensory details (how it feels, sounds, looks)
- Keep it 2-3 sentences
- Match the tier (T1: simple, T4: legendary)
```

### Scenario 4: Wrong Item Types

**Problem**: Generating wrong item types for recipes

**Solution**: Add explicit type mapping

Add to prompt:
```
Material Type Rules:
- Iron ingot → weapons, armor
- Wood planks → handles, bows
- Cloth → light armor, accessories
```

### Scenario 5: Inconsistent Tier Scaling

**Problem**: T3 items not much better than T1

**Solution**: Emphasize tier differences

Add to prompt:
```
Tier Scaling MUST be dramatic:
- T1: Basic, common, starter
- T2: Improved, reliable, uncommon
- T3: Advanced, rare, powerful
- T4: Legendary, unique, game-changing
```

---

## Validation Rules

The validator checks these automatically:

### Range Validation
- Stats must be within ±33% of observed ranges
- Example: T2 level is 5-10, so 3.35-13.3 is acceptable

### Tag Validation
- All tags must exist in template-specific library
- No new tags unless explicitly allowed

### Enum Validation
- Fields like category, type, rarity must use known values
- Validator shows valid options if wrong

---

## File Organization

```
Fewshot_llm/
├── prompts/
│   ├── components/           # Components (not used directly)
│   │   ├── base/             # Base prompts you can edit
│   │   └── enhanced/         # Auto-generated guidance
│   ├── system_prompts/       # ⭐ EDIT THESE - LLM uses these
│   └── README.txt            # Detailed prompt system docs
├── config/
│   ├── system_metadata.json  # System names and templates
│   ├── test_inputs.json      # Test inputs for each system
│   └── validation_libraries.json  # Auto-generated validation data
├── examples/
│   └── few_shot_examples.json  # Training examples
├── src/
│   ├── library_analyzer.py   # Extracts validation data
│   ├── prompt_generator.py   # Generates enhanced prompts
│   ├── update_system_prompts.py  # Combines base + enhanced
│   ├── validator.py          # Multi-layer validation
│   └── ...
├── outputs/                  # Generated outputs go here
└── run.py                    # Main runner
```

---

## Workflow

### Daily Tuning Workflow

1. **Edit prompts**: Open `prompts/system_prompts/system_X.txt`
2. **Test**: `python run.py` → select system
3. **Check output**: Look in `outputs/`
4. **Validate**: `python src/comprehensive_validation_test.py`
5. **Iterate**: Repeat until satisfied

### After Training Data Changes

1. **Re-analyze**: `python src/library_analyzer.py`
2. **Regenerate**: `python src/prompt_generator.py`
3. **Update**: `python src/update_system_prompts.py`
4. **Test**: Run a few systems to verify

### Before Production Use

1. **Test all systems**: `python run.py` → option 1
2. **Validate**: `python src/comprehensive_validation_test.py`
3. **Review outputs**: Check `outputs/` directory
4. **Fix issues**: Edit prompts as needed
5. **Retest**: Repeat until clean

---

## Tips for Effective Prompt Tuning

### Be Specific
❌ "Generate good items"
✅ "Generate items with damage 10-30 for T1, 18-50 for T2"

### Use Examples
❌ "Make it thematic"
✅ "Example: 'Forged in dragon fire, this blade hungers for battle'"

### Emphasize Critical Rules
```
⚠️ CRITICAL: Never exceed tier stat ranges
✓ REQUIRED: Always include weight stat
❌ FORBIDDEN: Do not create new tags
```

### Test Incrementally
- Change one thing at a time
- Test after each change
- Keep notes on what works

### Use Validation Output
The validator tells you exactly what's wrong:
- Range warnings → adjust emphasis on ranges
- Tag warnings → make tag list more explicit
- Enum warnings → clarify valid options

---

## Troubleshooting

### "LLM ignores my instructions"

**Try**:
1. Move instruction to TOP of prompt
2. Use stronger language (CRITICAL, REQUIRED)
3. Repeat instruction in multiple places
4. Add examples showing correct behavior

### "Validation always fails"

**Check**:
1. Are your ranges too strict? (±33% tolerance exists)
2. Are tags up to date? (Re-run library_analyzer.py)
3. Is training data clean? (Check examples/few_shot_examples.json)

### "Outputs are inconsistent"

**Solutions**:
1. Add more structure to prompt
2. Provide more examples
3. Be more explicit about edge cases
4. Use temperature=0.7 for less variation

### "Can't find where to edit"

**Remember**:
- System prompts: `prompts/system_prompts/system_X.txt`
- Base prompts: `prompts/components/base/system_X_base.txt`
- Enhanced prompts: Auto-generated, don't edit directly

---

## Advanced: Custom Validation Rules

To add custom validation rules:

1. Edit: `src/validator.py`
2. Add method: `def _validate_custom(self, data, library, errors)`
3. Call in: `validate_structure()`
4. Test: `python src/comprehensive_validation_test.py`

---

## Quick Reference

### Most Common Files to Edit
```
prompts/system_prompts/system_1.txt   # Smithing items
prompts/system_prompts/system_6.txt   # Enemies
prompts/system_prompts/system_10.txt  # Skills
```

### Most Common Commands
```bash
python run.py                          # Generate content
python src/update_system_prompts.py    # Update prompts
python src/comprehensive_validation_test.py  # Validate outputs
```

### Most Common Issues
1. Tags not in library → Edit prompt to be more explicit
2. Stats out of range → Add emphasis on tier ranges
3. Poor quality → Add more examples/guidelines

---

## Next Steps

1. ✅ Open a prompt file: `prompts/system_prompts/system_1.txt`
2. ✅ Read through it to understand structure
3. ✅ Make a small change (e.g., add "Be creative")
4. ✅ Test: `python run.py` → select system 1
5. ✅ Check output in `outputs/`
6. ✅ Iterate and improve!

---

**Happy Tuning! 🎯**
