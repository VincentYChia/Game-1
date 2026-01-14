"""
Material Metadata Enricher - Enhances recipe inputs with tier and narrative information
"""
import json
import os


class MaterialEnricher:
    """Enriches recipe materials with metadata from items-materials-1.JSON"""

    def __init__(self, materials_file: str):
        """Initialize with path to materials file."""
        self.materials = {}
        self.load_materials(materials_file)

    def load_materials(self, materials_file: str):
        """Load materials from JSON file."""
        with open(materials_file, 'r') as f:
            data = json.load(f)

        # Build lookup dictionary
        for material in data['materials']:
            material_id = material['materialId']
            self.materials[material_id] = {
                'name': material['name'],
                'tier': material['tier'],
                'rarity': material.get('rarity', 'common'),
                'category': material['category'],
                'narrative': material['metadata'].get('narrative', ''),
                'tags': material['metadata'].get('tags', [])
            }

        print(f"✓ Loaded {len(self.materials)} materials from {materials_file}")

    def enrich_recipe(self, recipe_data: dict) -> dict:
        """
        Enrich a recipe with material metadata.

        Args:
            recipe_data: Recipe dict with 'inputs' list containing materialId entries

        Returns:
            Enriched recipe dict with material metadata added
        """
        enriched = recipe_data.copy()

        if 'inputs' in enriched:
            enriched_inputs = []
            for input_item in enriched['inputs']:
                material_id = input_item.get('materialId')
                enriched_input = input_item.copy()

                if material_id and material_id in self.materials:
                    material_data = self.materials[material_id]
                    enriched_input['materialName'] = material_data['name']
                    enriched_input['materialTier'] = material_data['tier']
                    enriched_input['materialRarity'] = material_data['rarity']
                    enriched_input['materialNarrative'] = material_data['narrative']
                    enriched_input['materialTags'] = material_data['tags']
                else:
                    # Material not found - add placeholders
                    enriched_input['materialName'] = material_id if material_id else 'Unknown'
                    enriched_input['materialTier'] = 1
                    enriched_input['materialRarity'] = 'common'
                    enriched_input['materialNarrative'] = ''
                    enriched_input['materialTags'] = []

                enriched_inputs.append(enriched_input)

            enriched['inputs'] = enriched_inputs

        return enriched

    def enrich_test_prompts(self, test_inputs: dict) -> dict:
        """
        Enrich all test prompts in test_inputs.json with material metadata.

        Args:
            test_inputs: Dict of test inputs by system key

        Returns:
            Enriched test inputs dict
        """
        enriched = {}

        for system_key, system_data in test_inputs.items():
            enriched[system_key] = system_data.copy()
            prompt = system_data.get('prompt', '')

            # Extract JSON from prompt
            if '{' in prompt and '}' in prompt:
                start = prompt.find('{')
                end = prompt.rfind('}') + 1
                json_str = prompt[start:end]

                try:
                    recipe_data = json.loads(json_str)

                    # Enrich recipe
                    enriched_recipe = self.enrich_recipe(recipe_data)

                    # Replace in prompt
                    enriched_json = json.dumps(enriched_recipe, indent=2)
                    enriched_prompt = prompt[:start] + enriched_json + prompt[end:]
                    enriched[system_key]['prompt'] = enriched_prompt

                except json.JSONDecodeError:
                    # Keep original if JSON parse fails
                    pass

        return enriched

    def enrich_few_shot_examples(self, few_shot_examples: dict) -> dict:
        """
        Enrich all few-shot examples with material metadata.

        Args:
            few_shot_examples: Dict of examples by system key

        Returns:
            Enriched examples dict
        """
        enriched = {}

        for system_key, examples in few_shot_examples.items():
            enriched_examples = []

            for example in examples:
                enriched_example = example.copy()

                # Enrich input if it has recipe structure
                if 'input' in enriched_example:
                    input_data = enriched_example['input']

                    # Handle JSON string inputs
                    if isinstance(input_data, str):
                        try:
                            parsed_input = json.loads(input_data)
                            enriched_input = self.enrich_recipe(parsed_input)
                            # Convert back to formatted JSON string
                            enriched_example['input'] = json.dumps(enriched_input, indent=2)
                        except json.JSONDecodeError:
                            # Keep original if not valid JSON
                            pass
                    # Handle dict inputs
                    elif isinstance(input_data, dict):
                        enriched_example['input'] = self.enrich_recipe(input_data)

                enriched_examples.append(enriched_example)

            enriched[system_key] = enriched_examples

        return enriched


def main():
    """Main function to enrich configuration files."""
    # Paths
    materials_file = "../../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    test_inputs_file = "../config/test_inputs.json"
    few_shot_file = "../examples/few_shot_examples.json"

    # Initialize enricher
    enricher = MaterialEnricher(materials_file)

    # Enrich test inputs
    print("\nEnriching test inputs...")
    with open(test_inputs_file, 'r') as f:
        test_inputs = json.load(f)

    enriched_test_inputs = enricher.enrich_test_prompts(test_inputs)

    with open(test_inputs_file + '.enriched', 'w') as f:
        json.dump(enriched_test_inputs, f, indent=2)

    print(f"✓ Enriched test inputs saved to {test_inputs_file}.enriched")

    # Enrich few-shot examples
    print("\nEnriching few-shot examples...")
    with open(few_shot_file, 'r') as f:
        few_shot_examples = json.load(f)

    enriched_examples = enricher.enrich_few_shot_examples(few_shot_examples)

    with open(few_shot_file + '.enriched', 'w') as f:
        json.dump(enriched_examples, f, indent=2)

    print(f"✓ Enriched few-shot examples saved to {few_shot_file}.enriched")

    # Show sample enrichment
    print("\n" + "="*80)
    print("SAMPLE ENRICHMENT (System 1 - Smithing)")
    print("="*80)

    if '1' in enriched_test_inputs:
        sample_prompt = enriched_test_inputs['1']['prompt']
        # Find first input
        if '"inputs"' in sample_prompt:
            start = sample_prompt.find('"inputs"')
            end = sample_prompt.find(']', start) + 1
            print(sample_prompt[start:end])


if __name__ == "__main__":
    main()
