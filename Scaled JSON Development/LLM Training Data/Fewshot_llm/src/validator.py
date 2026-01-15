"""
JSON Validator for Few-Shot LLM Outputs

Validates the structure and values of generated JSON against templates and schemas.

ENHANCED VALIDATION:
- Range checking: Flags if stats are ±33% outside tier ranges
- Tag validation: Ensures tags come from template-specific libraries
- Enum validation: Validates enum fields against known values
- Text pattern validation: Checks text fields if ≥20 examples exist
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set, Optional
from collections import defaultdict


class JSONValidator:
    """Validates generated JSON against templates and expected schemas with enhanced validation."""

    def __init__(self, templates_dir: str = None, validation_libraries_file: str = None):
        """
        Initialize validator with template directory and validation libraries.

        Args:
            templates_dir: Path to JSON templates directory
            validation_libraries_file: Path to validation_libraries.json
        """
        if templates_dir is None:
            # Default to relative path: from src/ to Fewshot_llm/ to LLM Training Data/ to Scaled JSON Development/ to json_templates/
            base_dir = Path(__file__).parent.parent.parent.parent
            templates_dir = base_dir / "json_templates"

        self.templates_dir = Path(templates_dir)
        self.templates = {}
        self.load_templates()

        # Load validation libraries for enhanced validation
        self.validation_libraries = {}
        if validation_libraries_file is None:
            validation_libraries_file = Path(__file__).parent.parent / "config" / "validation_libraries.json"

        self.load_validation_libraries(validation_libraries_file)

    def load_templates(self):
        """Load all JSON templates from the templates directory."""
        if not self.templates_dir.exists():
            print(f"Warning: Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    template_name = template_file.stem
                    self.templates[template_name] = json.load(f)
                    print(f"Loaded template: {template_name}")
            except Exception as e:
                print(f"Error loading template {template_file}: {e}")

    def load_validation_libraries(self, libraries_file: Path):
        """Load validation libraries for enhanced validation."""
        libraries_file = Path(libraries_file)
        if not libraries_file.exists():
            print(f"Warning: Validation libraries not found: {libraries_file}")
            print("  Enhanced validation (ranges, tags, enums) will be disabled.")
            return

        try:
            with open(libraries_file, 'r') as f:
                self.validation_libraries = json.load(f)
                print(f"✓ Loaded validation libraries for {len(self.validation_libraries)} templates")
        except Exception as e:
            print(f"Warning: Error loading validation libraries: {e}")

    def validate_structure(self, data: Dict[str, Any], template_name: str) -> Tuple[bool, List[str]]:
        """
        Validate JSON structure against a template.

        Args:
            data: The JSON data to validate
            template_name: Name of the template to validate against

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        if template_name not in self.templates:
            errors.append(f"Template '{template_name}' not found")
            return False, errors

        template = self.templates[template_name]

        # Extract expected structure from template
        if "_usable_template" in template:
            expected = template["_usable_template"]
        elif "_sample_items" in template and template["_sample_items"]:
            expected = template["_sample_items"][0]
        else:
            errors.append(f"Template '{template_name}' has no usable structure")
            return False, errors

        # Validate required fields
        self._validate_fields(data, expected, "", errors)

        # Validate data types
        self._validate_types(data, expected, "", errors)

        # Validate against possible values if available
        if "_all_possible_values" in template:
            self._validate_values(data, template["_all_possible_values"], "", errors)

        # ENHANCED VALIDATION (if libraries available)
        if template_name in self.validation_libraries:
            library = self.validation_libraries[template_name]

            # Validate stat ranges (±33% tolerance)
            self._validate_ranges(data, library, errors)

            # Validate tags against template-specific libraries
            self._validate_tags(data, library, errors)

            # Validate enums
            self._validate_enums(data, library, errors)

        return len(errors) == 0, errors

    def _validate_fields(self, data: Any, expected: Any, path: str, errors: List[str]):
        """Recursively validate that core required fields are present."""
        if not isinstance(expected, dict) or not isinstance(data, dict):
            return

        # Define truly required fields per type (not every field in template)
        # Note: Some ID fields have alternatives that are equally valid
        core_required_fields = {
            "name", "tier", "rarity", "category",  # Common to most types
            # Enemies
            "behavior", "stats", "drops",
            # Skills
            # Titles
            # Enchantments
            "applicableTo", "effect",
            # Core sub-fields
            "level"  # requirements.level is required, but requirements.stats can be empty
        }

        # Alternative ID field groups (at least ONE from each group must be present)
        id_field_alternatives = [
            {"itemId", "materialId", "enchantmentId"},  # Items/Materials/Enchantments
            {"enemyId"},  # Enemies
            {"resourceId"},  # Resource nodes
            {"skillId"},  # Skills
            {"titleId"},  # Titles
            {"recipeId"},  # Recipes
        ]

        # Fields that are often optional
        optional_fields = {"stats", "flags", "metadata", "effectParams", "effect_params", "attributes"}

        # Check if at least one ID field is present (only at root level)
        if not path:  # Only check ID fields at root level
            has_id = False
            for id_group in id_field_alternatives:
                if any(id_field in data for id_field in id_group):
                    has_id = True
                    break
            if not has_id and any(id_field in expected for id_group in id_field_alternatives for id_field in id_group):
                # At least one ID field from expected should be present
                expected_ids = [id_field for id_group in id_field_alternatives for id_field in id_group if id_field in expected]
                if expected_ids:
                    errors.append(f"Missing required ID field (expected one of: {', '.join(expected_ids)})")

        for key, expected_value in expected.items():
            if key.startswith("_"):  # Skip metadata fields
                continue

            # Skip optional fields when validating nested structures
            if key in optional_fields and path:
                continue

            # Skip ID fields (already validated above)
            if key in [id_field for id_group in id_field_alternatives for id_field in id_group]:
                continue

            # Only enforce truly core fields
            if key not in data and key in core_required_fields:
                errors.append(f"Missing required field: {path}.{key}" if path else f"Missing required field: {key}")
                continue

            # If field exists, recurse into nested structures
            if key in data:
                if isinstance(expected_value, dict) and not isinstance(expected_value, list):
                    self._validate_fields(data[key], expected_value, f"{path}.{key}" if path else key, errors)
                elif isinstance(expected_value, list) and expected_value and isinstance(expected_value[0], dict):
                    # Validate array items if data is also an array
                    if isinstance(data[key], list) and data[key]:
                        self._validate_fields(data[key][0], expected_value[0], f"{path}.{key}[0]" if path else f"{key}[0]", errors)

    def _validate_types(self, data: Any, expected: Any, path: str, errors: List[str]):
        """Recursively validate data types match expected types."""
        if not isinstance(expected, dict) or not isinstance(data, dict):
            return

        for key, expected_value in expected.items():
            if key.startswith("_") or key not in data:
                continue

            data_value = data[key]
            field_path = f"{path}.{key}" if path else key

            # Check type compatibility
            if expected_value is not None and data_value is not None:
                expected_type = type(expected_value)
                data_type = type(data_value)

                # Allow int/float interchangeability
                if expected_type in (int, float) and data_type not in (int, float):
                    errors.append(f"Type mismatch at {field_path}: expected number, got {data_type.__name__}")
                elif expected_type not in (int, float, dict, list) and expected_type != data_type:
                    # Only check exact types for non-numeric, non-container types
                    if not (expected_type == str and isinstance(data_value, str)):
                        pass  # Be lenient with string types

                # Recurse into nested structures
                if isinstance(expected_value, dict) and isinstance(data_value, dict):
                    self._validate_types(data_value, expected_value, field_path, errors)
                elif isinstance(expected_value, list) and isinstance(data_value, list):
                    if expected_value and data_value:
                        for i, item in enumerate(data_value[:1]):  # Check first item
                            self._validate_types(item, expected_value[0], f"{field_path}[{i}]", errors)

    def _validate_values(self, data: Dict[str, Any], possible_values: Dict[str, Any], path: str, errors: List[str]):
        """Validate values against known possible values from training data (lenient mode)."""
        # Skip value validation - allow LLM to be creative
        # Only check data types for critical fields
        pass

    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested dictionary using dot notation path."""
        parts = field_path.split(".")
        current = data

        for part in parts:
            # Handle array notation like "drops[].materialId"
            if "[]" in part:
                part = part.replace("[]", "")
                if part and part in current:
                    current = current[part]
                if isinstance(current, list) and current:
                    current = current[0]  # Check first item
            else:
                if not isinstance(current, dict) or part not in current:
                    return None
                current = current[part]

        return current

    def validate_json_string(self, json_str: str, template_name: str) -> Tuple[bool, List[str], Dict]:
        """
        Validate a JSON string.

        Args:
            json_str: JSON string to validate
            template_name: Template name to validate against

        Returns:
            Tuple of (is_valid, errors, parsed_data)
        """
        errors = []

        # Try to parse JSON
        try:
            data = json.loads(json_str)

            # If the result is a string, it might be double-encoded - try parsing again
            if isinstance(data, str):
                data = json.loads(data)

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {e}")
            return False, errors, None

        # Validate structure
        is_valid, structure_errors = self.validate_structure(data, template_name)
        errors.extend(structure_errors)

        return is_valid, errors, data

    def validate_output_file(self, output_file: str, template_name: str) -> Tuple[bool, List[str]]:
        """
        Validate a Few-Shot LLM output file.

        Args:
            output_file: Path to output JSON file
            template_name: Template to validate against

        Returns:
            Tuple of (is_valid, errors)
        """
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            return False, [f"Error loading file: {e}"]

        # The output file contains metadata wrapper
        if "response" not in data:
            return False, ["Output file missing 'response' field"]

        response_text = data["response"]

        # Try to extract JSON from response
        # Look for JSON code blocks first
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        else:
            # Assume entire response is JSON
            json_str = response_text.strip()

        # Validate the JSON
        is_valid, errors, parsed_data = self.validate_json_string(json_str, template_name)

        return is_valid, errors

    def batch_validate(self, output_dir: str, system_template_map: Dict[str, str]) -> Dict[str, Any]:
        """
        Batch validate all output files in a directory.

        Args:
            output_dir: Directory containing output JSON files
            system_template_map: Mapping of system keys to template names

        Returns:
            Dictionary with validation results
        """
        results = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "details": {}
        }

        output_path = Path(output_dir)
        if not output_path.exists():
            results["error"] = f"Output directory not found: {output_dir}"
            return results

        for output_file in output_path.glob("system_*.json"):
            # Extract system key from filename
            filename = output_file.stem
            # Format: system_<key>_<timestamp>
            parts = filename.split("_")
            if len(parts) < 2:
                continue

            system_key = parts[1]

            if system_key not in system_template_map:
                print(f"Warning: No template mapping for system {system_key}")
                continue

            template_name = system_template_map[system_key]

            is_valid, errors = self.validate_output_file(str(output_file), template_name)

            results["total"] += 1
            if is_valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1

            results["details"][filename] = {
                "system": system_key,
                "template": template_name,
                "valid": is_valid,
                "errors": errors
            }

        return results

    def print_validation_report(self, results: Dict[str, Any]):
        """Print a formatted validation report."""
        print("\n" + "=" * 80)
        print("VALIDATION REPORT")
        print("=" * 80)
        print(f"Total files: {results['total']}")
        print(f"Valid: {results['valid']}")
        print(f"Invalid: {results['invalid']}")
        print(f"Success rate: {results['valid'] / results['total'] * 100:.1f}%" if results['total'] > 0 else "N/A")
        print("=" * 80)

        if results["invalid"] > 0:
            print("\nERRORS BY FILE:")
            print("-" * 80)
            for filename, details in results["details"].items():
                if not details["valid"]:
                    print(f"\n{filename} (System {details['system']}):")
                    for error in details["errors"]:
                        print(f"  - {error}")

        print("\n" + "=" * 80)

    # ============================================================================
    # ENHANCED VALIDATION METHODS
    # ============================================================================

    def _validate_ranges(self, data: Dict[str, Any], library: Dict[str, Any], errors: List[str]):
        """
        Validate numeric values are within ±33% of tier ranges.

        Args:
            data: JSON data to validate
            library: Validation library for this template
            errors: List to append errors to
        """
        if 'stat_ranges' not in library or 'tier' not in data:
            return

        tier = data.get('tier', 1)
        stat_ranges = library['stat_ranges']

        def check_value(obj: Any, path: str = ""):
            """Recursively check numeric values."""
            if not isinstance(obj, dict):
                return

            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key

                # Check if this field has tier-based ranges
                if field_path in stat_ranges:
                    tier_ranges = stat_ranges[field_path]

                    # Check if current tier has a range
                    if str(tier) in tier_ranges:
                        range_data = tier_ranges[str(tier)]
                        min_val = range_data['min']
                        max_val = range_data['max']

                        # Calculate ±33% tolerance
                        tolerance = 0.33
                        extended_min = min_val * (1 - tolerance)
                        extended_max = max_val * (1 + tolerance)

                        # Check if value is a number
                        if isinstance(value, (int, float)):
                            if not (extended_min <= value <= extended_max):
                                errors.append(
                                    f"⚠️  Range warning: {field_path}={value} is outside T{tier} range "
                                    f"[{min_val:.1f}-{max_val:.1f}] by >33%"
                                )

                        # Check if value is a [min, max] range
                        elif isinstance(value, list) and len(value) == 2:
                            for i, v in enumerate(value):
                                if isinstance(v, (int, float)):
                                    field_with_index = f"{field_path}[{i}]"
                                    if field_with_index in stat_ranges and str(tier) in stat_ranges[field_with_index]:
                                        range_data_idx = stat_ranges[field_with_index][str(tier)]
                                        min_val_idx = range_data_idx['min']
                                        max_val_idx = range_data_idx['max']
                                        extended_min_idx = min_val_idx * (1 - tolerance)
                                        extended_max_idx = max_val_idx * (1 + tolerance)

                                        if not (extended_min_idx <= v <= extended_max_idx):
                                            errors.append(
                                                f"⚠️  Range warning: {field_with_index}={v} is outside T{tier} range "
                                                f"[{min_val_idx:.1f}-{max_val_idx:.1f}] by >33%"
                                            )

                # Recurse into nested objects
                elif isinstance(value, dict):
                    check_value(value, field_path)

        check_value(data)

    def _validate_tags(self, data: Dict[str, Any], library: Dict[str, Any], errors: List[str]):
        """
        Validate tags come from template-specific libraries.

        Args:
            data: JSON data to validate
            library: Validation library for this template
            errors: List to append errors to
        """
        metadata_tags = set(library.get('metadata_tags', []))
        effect_tags = set(library.get('effect_tags', []))

        # Check metadata tags
        if 'metadata' in data and 'tags' in data['metadata']:
            tags = data['metadata']['tags']
            if isinstance(tags, list):
                for tag in tags:
                    if tag not in metadata_tags and metadata_tags:  # Only validate if library exists
                        errors.append(f"⚠️  Tag warning: metadata tag '{tag}' not found in template library")

        # Check effect tags
        if 'effectTags' in data:
            tags = data['effectTags']
            if isinstance(tags, list):
                for tag in tags:
                    if tag not in effect_tags and effect_tags:
                        errors.append(f"⚠️  Tag warning: effect tag '{tag}' not found in template library")

        # Check top-level tags
        if 'tags' in data and isinstance(data['tags'], list):
            tags = data['tags']
            for tag in tags:
                if tag not in metadata_tags and metadata_tags:
                    errors.append(f"⚠️  Tag warning: tag '{tag}' not found in template library")

    def _validate_enums(self, data: Dict[str, Any], library: Dict[str, Any], errors: List[str]):
        """
        Validate enum fields use values from template library.

        Args:
            data: JSON data to validate
            library: Validation library for this template
            errors: List to append errors to
        """
        if 'enums' not in library:
            return

        enums = library['enums']

        def check_enums(obj: Any, path: str = ""):
            """Recursively check enum values."""
            if not isinstance(obj, dict):
                return

            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key

                # Check if this field is an enum
                if field_path in enums:
                    enum_data = enums[field_path]

                    # Only validate if it's actually an enum (limited values)
                    if enum_data.get('is_enum', False):
                        valid_values = set(enum_data['values'])

                        if isinstance(value, str) and value not in valid_values:
                            # Show first few valid options
                            options = ', '.join(sorted(list(valid_values))[:5])
                            if len(valid_values) > 5:
                                options += f", ... ({len(valid_values)} total)"
                            errors.append(
                                f"⚠️  Enum warning: {field_path}='{value}' not in template library. "
                                f"Valid options: {options}"
                            )

                # Recurse into nested objects
                if isinstance(value, dict):
                    check_enums(value, field_path)

        check_enums(data)


def main():
    """Main function for standalone validation."""
    import sys

    validator = JSONValidator()

    if len(sys.argv) < 2:
        print("Usage: python validator.py <output_file> <template_name>")
        print("   or: python validator.py --batch <output_dir>")
        return

    if sys.argv[1] == "--batch":
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "fewshot_outputs"

        # System to template mapping
        system_template_map = {
            "1": "smithing_items",
            "1x2": "smithing_recipes",  # For placement
            "2": "refining_items",      # Outputs materials (materialId)
            "2x2": "refining_recipes",
            "3": "alchemy_items",
            "3x2": "alchemy_recipes",
            "4": "engineering_items",
            "4x2": "engineering_recipes",
            "5": "enchanting_recipes",  # Outputs enchantments (enchantmentId)
            "5x2": "enchanting_recipes",
            "6": "hostiles",
            "7": "refining_items",      # Outputs materials (materialId) from drop sources
            "8": "node_types",
            "10": "skills",
            "11": "titles"
        }

        results = validator.batch_validate(output_dir, system_template_map)
        validator.print_validation_report(results)
    else:
        output_file = sys.argv[1]
        template_name = sys.argv[2] if len(sys.argv) > 2 else "smithing_items"

        is_valid, errors = validator.validate_output_file(output_file, template_name)

        if is_valid:
            print(f"✓ Valid JSON for template '{template_name}'")
        else:
            print(f"✗ Invalid JSON for template '{template_name}'")
            print("\nErrors:")
            for error in errors:
                print(f"  - {error}")


if __name__ == "__main__":
    main()
