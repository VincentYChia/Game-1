"""
Comprehensive Validation Test - Tests enhanced validator on all outputs

Runs the upgraded validator on all output files and generates a detailed report
showing:
- Range warnings (stats outside ±33% tolerance)
- Tag warnings (unknown tags)
- Enum warnings (invalid enum values)
- Summary statistics
"""

import json
from pathlib import Path
from collections import defaultdict
from validator import JSONValidator


def comprehensive_validation_test():
    """Run comprehensive validation test on all outputs."""

    print("\n" + "="*80)
    print("COMPREHENSIVE VALIDATION TEST")
    print("="*80)

    validator = JSONValidator()
    outputs_dir = Path(__file__).parent.parent / "outputs"

    # Find all output files
    output_files = []
    for file_path in outputs_dir.rglob("*.json"):
        if file_path.name != "summary.json":  # Skip summary files
            output_files.append(file_path)

    print(f"\nFound {len(output_files)} output files to validate")
    print("-"*80)

    # Track results
    results = {
        'total_files': len(output_files),
        'valid': 0,
        'invalid': 0,
        'range_warnings': [],
        'tag_warnings': [],
        'enum_warnings': [],
        'other_errors': []
    }

    # Map system keys to template names
    system_to_template = {
        "1": "smithing_items",
        "2": "refining_items",
        "3": "alchemy_items",
        "4": "engineering_items",
        "5": "enchanting_recipes",
        "6": "hostiles",
        "7": "refining_items",
        "8": "node_types",
        "10": "skills",
        "11": "titles",
    }

    # Validate each file
    for output_file in sorted(output_files):
        print(f"\nValidating: {output_file.relative_to(outputs_dir)}")

        try:
            with open(output_file, 'r') as f:
                output_data = json.load(f)

            # Extract JSON response
            json_response = output_data.get('response', '')
            system_key = output_data.get('system_key', '')
            template_name = system_to_template.get(system_key, '')

            if not json_response:
                print("  ⚠️  No response found")
                results['invalid'] += 1
                continue

            # Validate
            is_valid, errors, parsed_data = validator.validate_json_string(json_response, template_name)

            if is_valid:
                print("  ✓ Valid")
                results['valid'] += 1
            else:
                print("  ✗ Invalid")
                results['invalid'] += 1

                # Categorize errors
                for error in errors:
                    print(f"    {error}")

                    if "Range warning" in error:
                        results['range_warnings'].append({
                            'file': str(output_file.relative_to(outputs_dir)),
                            'template': template_name,
                            'error': error
                        })
                    elif "Tag warning" in error:
                        results['tag_warnings'].append({
                            'file': str(output_file.relative_to(outputs_dir)),
                            'template': template_name,
                            'error': error
                        })
                    elif "Enum warning" in error:
                        results['enum_warnings'].append({
                            'file': str(output_file.relative_to(outputs_dir)),
                            'template': template_name,
                            'error': error
                        })
                    else:
                        results['other_errors'].append({
                            'file': str(output_file.relative_to(outputs_dir)),
                            'template': template_name,
                            'error': error
                        })

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results['invalid'] += 1
            results['other_errors'].append({
                'file': str(output_file.relative_to(outputs_dir)),
                'error': f"Exception: {e}"
            })

    # Print summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)

    print(f"\nTotal Files: {results['total_files']}")
    print(f"Valid: {results['valid']} ({results['valid']/results['total_files']*100:.1f}%)")
    print(f"Invalid: {results['invalid']} ({results['invalid']/results['total_files']*100:.1f}%)")

    print(f"\n\nWarning Breakdown:")
    print(f"  Range Warnings: {len(results['range_warnings'])}")
    print(f"  Tag Warnings: {len(results['tag_warnings'])}")
    print(f"  Enum Warnings: {len(results['enum_warnings'])}")
    print(f"  Other Errors: {len(results['other_errors'])}")

    # Detailed breakdown by template
    print("\n" + "-"*80)
    print("WARNINGS BY TEMPLATE")
    print("-"*80)

    template_warnings = defaultdict(lambda: {'range': 0, 'tag': 0, 'enum': 0, 'other': 0})

    for warning in results['range_warnings']:
        template_warnings[warning['template']]['range'] += 1

    for warning in results['tag_warnings']:
        template_warnings[warning['template']]['tag'] += 1

    for warning in results['enum_warnings']:
        template_warnings[warning['template']]['enum'] += 1

    for warning in results['other_errors']:
        template = warning.get('template', 'unknown')
        template_warnings[template]['other'] += 1

    for template, counts in sorted(template_warnings.items()):
        total = sum(counts.values())
        print(f"\n{template}:")
        print(f"  Total: {total}")
        print(f"  Range: {counts['range']}")
        print(f"  Tag: {counts['tag']}")
        print(f"  Enum: {counts['enum']}")
        print(f"  Other: {counts['other']}")

    # Save detailed results
    results_file = Path(__file__).parent.parent / "outputs" / "validation_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print(f"✓ Detailed results saved to: {results_file}")
    print("="*80)

    return results


if __name__ == "__main__":
    comprehensive_validation_test()
