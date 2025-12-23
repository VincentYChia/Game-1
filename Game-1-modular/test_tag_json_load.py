"""
Simple JSON tag loading test - doesn't require pygame
"""

import json
import os

def test_json_tags():
    """Test that JSON files have tags in them"""
    print("\n" + "="*70)
    print("🧪 TAG SYSTEM - JSON VALIDATION TEST")
    print("="*70 + "\n")
    
    # Test files to check
    test_files = [
        ("items.JSON/items-testing-tags.JSON", "Test Items"),
        ("items.JSON/items-smithing-2.JSON", "Weapons"),
        ("items.JSON/items-engineering-1.JSON", "Devices")
    ]
    
    for filepath, description in test_files:
        print(f"\n{'='*70}")
        print(f"Testing: {description} ({filepath})")
        print(f"{'='*70}\n")
        
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filepath}")
            continue
            
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Find all items with effectTags
        items_with_tags = []
        items_without_tags = []
        
        for section_name, section_data in data.items():
            if section_name == 'metadata':
                continue
            if not isinstance(section_data, list):
                continue
                
            for item in section_data:
                item_id = item.get('itemId', 'unknown')
                tags = item.get('effectTags', None)
                params = item.get('effectParams', None)
                
                if tags and len(tags) > 0:
                    items_with_tags.append({
                        'id': item_id,
                        'tags': tags,
                        'params': list(params.keys()) if params else []
                    })
                else:
                    items_without_tags.append(item_id)
        
        # Report
        print(f"✅ Items WITH tags: {len(items_with_tags)}")
        for item in items_with_tags[:10]:  # Show first 10
            print(f"   • {item['id']}")
            print(f"     Tags: {item['tags']}")
            if item['params']:
                print(f"     Params: {item['params']}")
        if len(items_with_tags) > 10:
            print(f"   ... and {len(items_with_tags) - 10} more")
        
        print(f"\n⚠️  Items WITHOUT tags: {len(items_without_tags)}")
        if items_without_tags:
            for item_id in items_without_tags[:5]:
                print(f"   • {item_id}")
            if len(items_without_tags) > 5:
                print(f"   ... and {len(items_without_tags) - 5} more")
    
    print("\n" + "="*70)
    print("✅ JSON VALIDATION COMPLETE")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_json_tags()
