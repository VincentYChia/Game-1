"""
Convert Crafting Training Data to JSONL Format

Takes output from crafting_training_data.py and converts it to
Together.ai/OpenAI-compatible JSONL format for fine-tuning.

Features:
- Converts JSON training data to JSONL with messages array
- Supports both VLM (image+text) and LLM (text-only) formats
- Removes rarity field from all disciplines EXCEPT refining
- Properly formats system/user/assistant messages

Usage:
    python convert_to_jsonl.py --input ./training_outputs/alchemy_custom_data.json
    python convert_to_jsonl.py --input ./training_outputs/ --all

Author: Claude
Created: 2026-02-05
"""

import json
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional


# =============================================================================
# SYSTEM PROMPTS BY DISCIPLINE
# =============================================================================

SYSTEM_PROMPTS = {
    'smithing': """You are an expert crafting assistant for a fantasy RPG game. Given a smithing recipe with material placements on a crafting grid and an image of the arrangement, generate the resulting item definition as JSON.

The item should reflect the materials used, their qualities, and the crafting arrangement. Consider material tiers (T1-T4), tags, and properties when determining the output item's stats and effects.""",

    'adornment': """You are an expert crafting assistant for a fantasy RPG game. Given an adornment/enchantment recipe with material placements and an image of the arrangement, generate the resulting enchantment or accessory item definition as JSON.

Consider the magical properties of materials, their tiers, and arrangement when determining the enchantment effects.""",

    'refining': """You are an expert crafting assistant for a fantasy RPG game. Given a refining recipe with input materials and processing parameters, generate the resulting refined material definition as JSON.

Refining transforms raw materials into processed forms. The output rarity depends on the refinement process and input material quality. Consider material tiers and processing to determine output properties.""",

    'alchemy': """You are an expert crafting assistant for a fantasy RPG game. Given an alchemy recipe with ingredients, quantities, and slot positions, generate the resulting potion or consumable item definition as JSON.

Consider the magical and chemical properties of ingredients, their tiers, and the brewing process when determining the potion's effects, duration, and potency.""",

    'engineering': """You are an expert crafting assistant for a fantasy RPG game. Given an engineering recipe with component slots (FRAME, CORE, MECHANISM, CASING), generate the resulting device or gadget item definition as JSON.

Consider the mechanical and magical properties of components, their tiers, and assembly configuration when determining the device's functionality and stats.""",
}


# =============================================================================
# ITEM STRUCTURE TEMPLATES
# =============================================================================

def get_item_template(discipline: str) -> Dict[str, Any]:
    """Get the expected item structure template for a discipline."""

    base_template = {
        "metadata": {
            "narrative": "",
            "tags": []
        },
        "itemId": "",
        "name": "",
        "category": "",
        "type": "",
        "subtype": "",
        "tier": 1,
    }

    if discipline == 'alchemy':
        return {
            **base_template,
            "effect": "",
            "duration": 0,
            "stackSize": 1,
            "effectTags": [],
            "effectParams": {},
            "statMultipliers": {},
            "requirements": {},
            "flags": {}
        }

    elif discipline == 'refining':
        # Refining keeps rarity
        return {
            **base_template,
            "rarity": "common",
            "properties": {},
            "refinedFrom": "",
            "processType": "",
            "flags": {}
        }

    elif discipline == 'engineering':
        return {
            **base_template,
            "functionality": "",
            "powerSource": "",
            "durability": 100,
            "effectTags": [],
            "effectParams": {},
            "requirements": {},
            "flags": {}
        }

    elif discipline in ['smithing', 'adornment']:
        return {
            **base_template,
            "slot": "",
            "stats": {},
            "effectTags": [],
            "effectParams": {},
            "requirements": {},
            "durability": 100,
            "flags": {}
        }

    return base_template


# =============================================================================
# DATA PROCESSING
# =============================================================================

def remove_rarity(item: Dict, discipline: str) -> Dict:
    """Remove rarity field from item unless it's refining discipline."""
    if discipline == 'refining':
        return item

    # Recursively remove rarity from item and nested dicts
    if isinstance(item, dict):
        return {k: remove_rarity(v, discipline) for k, v in item.items() if k != 'rarity'}
    elif isinstance(item, list):
        return [remove_rarity(i, discipline) for i in item]
    return item


def format_recipe_for_prompt(entry: Dict, discipline: str) -> str:
    """Format the recipe data as a user prompt."""
    recipe = entry.get('recipe', {})

    if discipline in ['smithing', 'adornment']:
        # VLM format - include placement info
        inputs = recipe.get('inputs', [])
        grid_size = "6x6" if discipline == 'smithing' else "8x7"

        prompt_parts = [
            f"Crafting Recipe ({discipline.title()}):",
            f"Recipe ID: {recipe.get('recipeId', 'unknown')}",
            f"Grid Size: {grid_size}",
            f"Station Tier: {recipe.get('stationTier', 1)}",
            "",
            "Materials placed:"
        ]

        for inp in inputs:
            mat_id = inp.get('materialId', 'unknown')
            pos = inp.get('position', 'unknown')
            meta = inp.get('material_metadata', {})
            tier = meta.get('tier', 1)
            tags = meta.get('tags', [])
            prompt_parts.append(f"  - {mat_id} (Tier {tier}) at position {pos}")
            if tags:
                prompt_parts.append(f"    Tags: {', '.join(tags)}")

        return "\n".join(prompt_parts)

    elif discipline == 'refining':
        inputs = recipe.get('inputs', [])
        prompt_parts = [
            f"Refining Recipe:",
            f"Recipe ID: {recipe.get('recipeId', 'unknown')}",
            f"Station Tier: {recipe.get('stationTier', 1)}",
            f"Output: {recipe.get('outputId', 'unknown')}",
            "",
            "Input materials:"
        ]

        for inp in inputs:
            mat_id = inp.get('materialId', 'unknown')
            qty = inp.get('quantity', 1)
            meta = inp.get('material_metadata', {})
            tier = meta.get('tier', 1)
            tags = meta.get('tags', [])
            prompt_parts.append(f"  - {mat_id} x{qty} (Tier {tier})")
            if tags:
                prompt_parts.append(f"    Tags: {', '.join(tags)}")

        return "\n".join(prompt_parts)

    elif discipline == 'alchemy':
        ingredients = recipe.get('ingredients', [])
        prompt_parts = [
            f"Alchemy Recipe:",
            f"Recipe ID: {recipe.get('recipeId', 'unknown')}",
            f"Station Tier: {recipe.get('stationTier', 1)}",
            f"Output: {recipe.get('outputId', 'unknown')}",
            "",
            "Ingredients:"
        ]

        for ing in ingredients:
            mat_id = ing.get('materialId', 'unknown')
            qty = ing.get('quantity', 1)
            slot = ing.get('slot', 1)
            meta = ing.get('material_metadata', {})
            tier = meta.get('tier', 1)
            tags = meta.get('tags', [])
            prompt_parts.append(f"  - Slot {slot}: {mat_id} x{qty} (Tier {tier})")
            if tags:
                prompt_parts.append(f"    Tags: {', '.join(tags)}")

        return "\n".join(prompt_parts)

    elif discipline == 'engineering':
        slots = recipe.get('slots', [])
        prompt_parts = [
            f"Engineering Recipe:",
            f"Recipe ID: {recipe.get('recipeId', 'unknown')}",
            f"Station Tier: {recipe.get('stationTier', 1)}",
            f"Output: {recipe.get('outputId', 'unknown')}",
            "",
            "Components:"
        ]

        for slot in slots:
            mat_id = slot.get('materialId', 'unknown')
            qty = slot.get('quantity', 1)
            slot_type = slot.get('type', 'COMPONENT')
            meta = slot.get('material_metadata', {})
            tier = meta.get('tier', 1)
            tags = meta.get('tags', [])
            prompt_parts.append(f"  - {slot_type}: {mat_id} x{qty} (Tier {tier})")
            if tags:
                prompt_parts.append(f"    Tags: {', '.join(tags)}")

        return "\n".join(prompt_parts)

    return json.dumps(recipe, indent=2)


def generate_item_response(entry: Dict, discipline: str) -> str:
    """Generate the expected item JSON response."""
    recipe = entry.get('recipe', {})

    # Extract material info for item generation
    materials = []
    if 'inputs' in recipe:
        materials = recipe['inputs']
    elif 'ingredients' in recipe:
        materials = recipe['ingredients']
    elif 'slots' in recipe:
        materials = recipe['slots']

    # Calculate average tier
    tiers = []
    all_tags = []
    for mat in materials:
        meta = mat.get('material_metadata', {})
        tiers.append(meta.get('tier', 1))
        all_tags.extend(meta.get('tags', []))

    avg_tier = round(sum(tiers) / len(tiers)) if tiers else 1
    unique_tags = list(set(all_tags))

    # Build item based on discipline
    output_id = recipe.get('outputId', recipe.get('recipeId', 'unknown_item'))
    recipe_id = recipe.get('recipeId', 'unknown')

    # Create item name from output_id
    item_name = output_id.replace('_', ' ').title()

    item = {
        "metadata": {
            "narrative": f"A crafted {item_name.lower()} made through {discipline}.",
            "tags": unique_tags[:5]  # Limit tags
        },
        "itemId": output_id,
        "name": item_name,
        "category": discipline,
        "type": get_item_type(discipline),
        "subtype": get_item_subtype(recipe, discipline),
        "tier": avg_tier,
    }

    # Add discipline-specific fields
    if discipline == 'alchemy':
        item.update({
            "effect": get_effect_from_tags(unique_tags),
            "duration": 30 * avg_tier,
            "stackSize": 10,
            "effectTags": unique_tags[:3],
            "effectParams": {
                "potency": 10 * avg_tier,
                "duration": 30 * avg_tier
            },
            "statMultipliers": {},
            "requirements": {"level": max(1, (avg_tier - 1) * 5)},
            "flags": {}
        })

    elif discipline == 'refining':
        # Keep rarity for refining
        item.update({
            "rarity": get_rarity_from_tier(avg_tier),
            "properties": {
                "hardness": 5 * avg_tier,
                "purity": 70 + (avg_tier * 5)
            },
            "refinedFrom": materials[0].get('materialId', 'raw_material') if materials else 'raw_material',
            "processType": "standard",
            "flags": {}
        })

    elif discipline == 'engineering':
        item.update({
            "functionality": get_functionality_from_tags(unique_tags),
            "powerSource": "manual" if avg_tier < 3 else "magical",
            "durability": 50 * avg_tier,
            "effectTags": unique_tags[:3],
            "effectParams": {},
            "requirements": {"level": max(1, (avg_tier - 1) * 5)},
            "flags": {}
        })

    elif discipline in ['smithing', 'adornment']:
        item.update({
            "slot": get_slot_from_recipe(recipe, discipline),
            "stats": {
                "damage" if discipline == 'smithing' else "magicPower": 10 * avg_tier,
                "durability": 50 * avg_tier
            },
            "effectTags": unique_tags[:3],
            "effectParams": {},
            "requirements": {"level": max(1, (avg_tier - 1) * 5)},
            "durability": 100,
            "flags": {}
        })

    # Remove rarity unless refining
    item = remove_rarity(item, discipline)

    return json.dumps(item, indent=2)


def get_item_type(discipline: str) -> str:
    """Get item type based on discipline."""
    type_map = {
        'smithing': 'equipment',
        'adornment': 'accessory',
        'refining': 'material',
        'alchemy': 'consumable',
        'engineering': 'device'
    }
    return type_map.get(discipline, 'item')


def get_item_subtype(recipe: Dict, discipline: str) -> str:
    """Get item subtype from recipe."""
    output_id = recipe.get('outputId', '').lower()

    if discipline == 'smithing':
        if 'sword' in output_id:
            return 'sword'
        elif 'axe' in output_id:
            return 'axe'
        elif 'helmet' in output_id or 'helm' in output_id:
            return 'helmet'
        elif 'chest' in output_id or 'armor' in output_id:
            return 'chestplate'
        return 'weapon'

    elif discipline == 'alchemy':
        if 'potion' in output_id:
            return 'potion'
        elif 'elixir' in output_id:
            return 'elixir'
        elif 'oil' in output_id:
            return 'oil'
        return 'potion'

    elif discipline == 'refining':
        if 'ingot' in output_id:
            return 'ingot'
        elif 'plank' in output_id:
            return 'plank'
        elif 'gem' in output_id:
            return 'gem'
        return 'processed'

    elif discipline == 'engineering':
        if 'trap' in output_id:
            return 'trap'
        elif 'turret' in output_id:
            return 'turret'
        return 'gadget'

    return 'misc'


def get_effect_from_tags(tags: List[str]) -> str:
    """Derive effect description from tags."""
    effect_map = {
        'healing': 'Restores health over time',
        'fire': 'Deals fire damage',
        'ice': 'Slows enemies',
        'lightning': 'Deals lightning damage',
        'poison': 'Deals poison damage over time',
        'strength': 'Increases physical damage',
        'defense': 'Increases armor',
        'speed': 'Increases movement speed',
        'magic': 'Increases magical power'
    }

    for tag in tags:
        tag_lower = tag.lower()
        for key, effect in effect_map.items():
            if key in tag_lower:
                return effect

    return 'Provides beneficial effects'


def get_functionality_from_tags(tags: List[str]) -> str:
    """Derive functionality from tags."""
    for tag in tags:
        tag_lower = tag.lower()
        if 'trap' in tag_lower:
            return 'Damages and immobilizes enemies'
        elif 'turret' in tag_lower:
            return 'Automatically attacks nearby enemies'
        elif 'light' in tag_lower:
            return 'Provides illumination'

    return 'Mechanical utility device'


def get_rarity_from_tier(tier: int) -> str:
    """Get rarity based on tier."""
    rarity_map = {1: 'common', 2: 'uncommon', 3: 'rare', 4: 'legendary'}
    return rarity_map.get(tier, 'common')


def get_slot_from_recipe(recipe: Dict, discipline: str) -> str:
    """Get equipment slot from recipe."""
    output_id = recipe.get('outputId', '').lower()

    if 'sword' in output_id or 'axe' in output_id or 'mace' in output_id:
        return 'mainhand'
    elif 'shield' in output_id:
        return 'offhand'
    elif 'helmet' in output_id or 'helm' in output_id:
        return 'head'
    elif 'chest' in output_id or 'armor' in output_id:
        return 'chest'
    elif 'legs' in output_id or 'pants' in output_id:
        return 'legs'
    elif 'boots' in output_id:
        return 'feet'
    elif 'gloves' in output_id or 'gauntlet' in output_id:
        return 'hands'
    elif 'ring' in output_id:
        return 'ring'
    elif 'amulet' in output_id or 'necklace' in output_id:
        return 'neck'

    return 'mainhand' if discipline == 'smithing' else 'accessory'


def convert_entry_to_jsonl(entry: Dict, discipline: str, include_image: bool = False) -> Dict:
    """Convert a single training entry to JSONL format."""

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS.get(discipline, SYSTEM_PROMPTS['smithing'])
        }
    ]

    # User message with recipe
    user_content = format_recipe_for_prompt(entry, discipline)

    # For VLM disciplines, include image reference if available
    if include_image and discipline in ['smithing', 'adornment']:
        image_base64 = entry.get('image_base64')
        if image_base64:
            # Format for VLM with image
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_content
                    }
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": user_content
            })
    else:
        messages.append({
            "role": "user",
            "content": user_content
        })

    # Assistant response with item JSON
    assistant_content = generate_item_response(entry, discipline)
    messages.append({
        "role": "assistant",
        "content": assistant_content
    })

    return {"messages": messages}


# =============================================================================
# MAIN CONVERSION
# =============================================================================

def convert_file(input_path: str, output_path: str = None, include_images: bool = False) -> int:
    """Convert a single JSON file to JSONL format."""

    with open(input_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    discipline = metadata.get('discipline', 'unknown')
    training_data = data.get('training_data', [])

    if not training_data:
        print(f"  No training data found in {input_path}")
        return 0

    # Generate output path if not provided
    if not output_path:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}.jsonl")

    # Convert each entry
    converted = []
    for entry in training_data:
        jsonl_entry = convert_entry_to_jsonl(entry, discipline, include_images)
        converted.append(jsonl_entry)

    # Write JSONL
    with open(output_path, 'w') as f:
        for entry in converted:
            f.write(json.dumps(entry) + '\n')

    print(f"  Converted {len(converted)} entries -> {output_path}")
    return len(converted)


def main():
    parser = argparse.ArgumentParser(
        description='Convert crafting training data to JSONL format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_to_jsonl.py --input ./training_outputs/alchemy_custom_data.json
  python convert_to_jsonl.py --input ./training_outputs/ --all
  python convert_to_jsonl.py --input ./training_outputs/ --all --include-images
        """
    )

    parser.add_argument('--input', '-i', required=True,
                        help='Input JSON file or directory')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSONL file (default: same name with .jsonl)')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Convert all JSON files in directory')
    parser.add_argument('--include-images', action='store_true',
                        help='Include base64 images for VLM disciplines')
    parser.add_argument('--merge', '-m', action='store_true',
                        help='Merge all outputs into single JSONL file')
    parser.add_argument('--merge-output', default='crafting_training_data.jsonl',
                        help='Output filename for merged JSONL (default: crafting_training_data.jsonl)')

    args = parser.parse_args()

    input_path = Path(args.input)

    print("=" * 60)
    print("JSONL Converter for Crafting Training Data")
    print("=" * 60)

    total_entries = 0
    all_entries = []

    if args.all and input_path.is_dir():
        # Convert all JSON files in directory
        json_files = list(input_path.glob('*_data.json'))

        if not json_files:
            print(f"\nNo *_data.json files found in {input_path}")
            return

        print(f"\nFound {len(json_files)} files to convert:")
        for f in json_files:
            print(f"  - {f.name}")
        print()

        for json_file in json_files:
            count = convert_file(str(json_file), include_images=args.include_images)
            total_entries += count

            # For merge, read the converted JSONL
            if args.merge:
                jsonl_path = json_file.parent / f"{json_file.stem}.jsonl"
                if jsonl_path.exists():
                    with open(jsonl_path, 'r') as f:
                        for line in f:
                            all_entries.append(json.loads(line))

        # Merge if requested
        if args.merge and all_entries:
            merge_path = input_path / args.merge_output
            with open(merge_path, 'w') as f:
                for entry in all_entries:
                    f.write(json.dumps(entry) + '\n')
            print(f"\n  Merged {len(all_entries)} entries -> {merge_path}")

    elif input_path.is_file():
        # Convert single file
        total_entries = convert_file(str(input_path), args.output, args.include_images)

    else:
        print(f"\nError: {input_path} not found or invalid")
        return

    print("\n" + "=" * 60)
    print(f"CONVERSION COMPLETE: {total_entries} total entries")
    print("=" * 60)


if __name__ == "__main__":
    main()
