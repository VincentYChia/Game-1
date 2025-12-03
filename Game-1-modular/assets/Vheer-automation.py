"""
Vheer AI Game Assets Generator - Automation Script
Generates icons for game items automatically

Requirements:
- pip install selenium webdriver-manager pillow

Usage:
1. Run script
2. Choose test mode (2 items) or full catalog
3. Script will generate all icons automatically
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from pathlib import Path
import time
import re
import shutil

# ============================================================================
# CONFIGURATION
# ============================================================================

PERSISTENT_PROMPT = "Simple cel-shaded 3d stylized fantasy exploration item icons. Clean render, distinct details, transparent background."

# Version-specific prompts (replaces entire persistent prompt for that version)
# Empty dict means use default PERSISTENT_PROMPT for all versions
VERSION_PROMPTS = {
    1: "3D rendered item icon in illustrative fantasy style. Item large in frame (70-80% coverage), slight diagonal positioning. Neutral background with gradient, clean three-point lighting, soft shadow beneath. Focus on representing the idea of the item through an idealized fantasy illustration. Smooth, detailed, and brighter.",
    2: "3D rendered item icon in illustrative fantasy style. Render EXACTLY the item described - verify item type, form, and state before generating. Item large in frame (70-80% coverage), slight diagonal positioning. Neutral background with gradient, clean three-point lighting, soft shadow beneath. Focus on representing the precise idea of the item through idealized fantasy illustration. Smooth, detailed, and brighter.",
    3: "3D rendered item icon in illustrative fantasy style. Read full item description carefully - distinguish between similar items (axe vs pickaxe, ore vs ingot vs node, dagger vs sword). Render the specific form described. Item fills 70-80% of frame, diagonal angle. Neutral gradient background, clean three-point lighting, soft shadow. Represent the idealized archetypal form with smooth detail and enhanced brightness. Accuracy to description is critical.",
}

# Category-specific additions (appends to detail prompt for matching categories)
# All available categories from catalog:
CATEGORY_ADDITIONS = {
    # 'equipment': 'Additional guidance for equipment',
    # 'consumable': 'Additional guidance for consumables',
    'enemy': 'Focus on stylized enemies. Avoid excessive realism or any elements that may disgust users',
    'resource': 'This is a node for resources not the actual resource, your illustration should reflect that',
    'title': 'This is an icon for a in-game title. So it should be a representative icon based on the idea not an illustration',
    'skill': 'This is an icon for a in-game skill. So it should be a representative icon based on the idea not an illustration',
    'station': 't1, t2, t3, and t4 represent tiers 1 through 4. 4 is the most advanced and should have the most detail. 1 is the simplest and should be simplest in design',
    'device': 'Adhere closely to the type as the largest distinction for design.',
    'material': 'For less specific and documented materials adhering to the style is more important. Use the narrative as the most important description',
}

# Type-specific additions (appends to detail prompt for matching types)
# All available types from catalog:
TYPE_ADDITIONS = {
    # Equipment types:
    # 'weapon': 'Additional guidance for weapons',
    # 'sword': 'Additional guidance for swords',
    # 'axe': 'Additional guidance for axes',
    # 'mace': 'Additional guidance for maces',
    # 'dagger': 'Additional guidance for daggers',
    # 'spear': 'Additional guidance for spears',
    # 'bow': 'Additional guidance for bows',
    # 'staff': 'Additional guidance for staves',
    # 'shield': 'Additional guidance for shields',
    # 'armor': 'Additional guidance for armor',
    # 'tool': 'Additional guidance for tools',
    # 'accessory': 'Additional guidance for accessories',
    # Consumable types:
    # 'potion': 'Additional guidance for potions',
    # 'food': 'Additional guidance for food',
    # 'scroll': 'Additional guidance for scrolls',
    'turret': 'Turrets require a base'
    # Other types as needed...
}

TEST_ITEMS = [
    {
        'name': 'Iron_Sword',
        'base_folder': 'items',
        'subfolder': 'weapons',
        'category': 'equipment',
        'type': 'weapon',
        'subtype': 'shortsword',
        'narrative': 'A basic but reliable blade forged from iron.'
    },
    {
        'name': 'Health_Potion',
        'base_folder': 'items',
        'subfolder': 'consumables',
        'category': 'consumable',
        'type': 'potion',
        'subtype': 'healing',
        'narrative': 'A red vial filled with healing liquid.'
    }
]

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / 'generated_icons'
CATALOG_PATH = SCRIPT_DIR.parent.parent / "Scaled JSON Development" / "ITEM_CATALOG_FOR_ICONS.md"

GENERATION_TIMEOUT = 180
WAIT_BETWEEN_ITEMS = 25
VERSIONS_TO_GENERATE = 3  # Generate 3 versions of each icon

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def categorize_item(item):
    """Determine subfolder based on item properties

    Returns tuple: (base_folder, subfolder)
    - base_folder: 'items', 'enemies', 'resources', 'titles', or 'skills'
    - subfolder: specific category within base folder (or None for non-items)
    """
    category = item.get('category', '').lower()
    item_type = item.get('type', '').lower()

    # Non-item entities
    if category == 'enemy':
        return ('enemies', None)
    if category == 'resource':
        return ('resources', None)
    if category == 'title':
        return ('titles', None)
    if category == 'skill':
        return ('skills', None)

    # Item entities - all go under 'items' base folder
    if category == 'equipment':
        if item_type in ['weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff', 'shield']:
            return ('items', 'weapons')
        elif item_type in ['armor']:
            return ('items', 'armor')
        elif item_type in ['tool']:
            return ('items', 'tools')
        elif item_type in ['accessory']:
            return ('items', 'accessories')
        else:
            return ('items', 'weapons')  # Default for equipment

    if category == 'station':
        return ('items', 'stations')
    if category == 'device':
        return ('items', 'devices')
    if category == 'consumable':
        return ('items', 'consumables')

    # Default: materials
    return ('items', 'materials')

def parse_catalog(filepath):
    """Parse ITEM_CATALOG_FOR_ICONS.md"""
    items = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = re.split(r'\n### ', content)

    for section in sections[1:]:
        lines = section.strip().split('\n')
        if not lines:
            continue

        item_name = lines[0].strip()
        item_data = {'name': item_name}

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- **Category**:'):
                item_data['category'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Type**:'):
                item_data['type'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Subtype**:'):
                item_data['subtype'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Narrative**:'):
                item_data['narrative'] = line.split(':', 1)[1].strip()

        if 'narrative' in item_data:
            item_data.setdefault('subtype', item_data.get('type', 'unknown'))
            item_data.setdefault('category', 'material')
            item_data.setdefault('type', 'unknown')

            # Get folder structure from categorize_item
            base_folder, subfolder = categorize_item(item_data)
            item_data['base_folder'] = base_folder
            item_data['subfolder'] = subfolder

            items.append(item_data)

    return items

def build_detail_prompt(item):
    """Build detail prompt from item data with optional additions

    Applies CATEGORY_ADDITIONS and TYPE_ADDITIONS if matching
    """
    try:
        base_prompt = f"""Generate an icon image off of the item description:
Icon_name: {item['name']}
Category: {item['category']}
Type: {item['type']}
Subtype: {item['subtype']}
Narrative: {item['narrative']}"""

        # Apply category-specific additions
        category = item.get('category', '').lower()
        if category in CATEGORY_ADDITIONS:
            print(f"  [DEBUG] Adding category guidance for: {category}")
            base_prompt += f"\n\nAdditional guidance: {CATEGORY_ADDITIONS[category]}"

        # Apply type-specific additions (more specific than category)
        item_type = item.get('type', '').lower()
        if item_type in TYPE_ADDITIONS:
            print(f"  [DEBUG] Adding type guidance for: {item_type}")
            base_prompt += f"\n\nType-specific: {TYPE_ADDITIONS[item_type]}"

        return base_prompt

    except Exception as e:
        print(f"  [DEBUG] EXCEPTION in build_detail_prompt: {type(e).__name__}: {e}")
        print(f"  [DEBUG] Item data: {item}")
        import traceback
        traceback.print_exc()
        raise

def get_persistent_prompt_for_version(version):
    """Get the persistent prompt for a specific version

    Returns VERSION_PROMPTS[version] if set, otherwise default PERSISTENT_PROMPT
    """
    return VERSION_PROMPTS.get(version, PERSISTENT_PROMPT)

def pre_scan_directories(items, versions_to_generate):
    """Scan output directories before browser opens

    Shows summary of existing vs missing files for each version
    Only counts files > 5KB (excludes tiny placeholders)

    Args:
        items: List of item dictionaries
        versions_to_generate: Number of versions to check
    """
    print("\n" + "="*70)
    print("PRE-SCAN: Checking existing files")
    print("="*70)

    MIN_FILE_SIZE = 5000  # 5KB minimum

    # Track overall stats
    all_version_stats = []

    for version in range(1, versions_to_generate + 1):
        # Determine output base for this version
        if version == 1:
            output_base = OUTPUT_DIR
        else:
            output_base = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"

        existing_files = []
        missing_items = []

        # Check each item
        for item in items:
            name = item['name']
            base_folder = item.get('base_folder', 'items')
            subfolder = item.get('subfolder')

            # Build file path (same logic as generate_item)
            if version == 1:
                filename = f"{name}.png"
            else:
                filename = f"{name}-{version}.png"

            if subfolder:
                save_dir = output_base / base_folder / subfolder
            else:
                save_dir = output_base / base_folder

            save_path = save_dir / filename

            # Check if exists and has valid size
            if save_path.exists() and save_path.stat().st_size > MIN_FILE_SIZE:
                existing_files.append({
                    'name': name,
                    'path': save_path,
                    'size': save_path.stat().st_size
                })
            else:
                missing_items.append(name)

        # Store stats
        existing_count = len(existing_files)
        missing_count = len(missing_items)
        total_count = len(items)

        all_version_stats.append({
            'version': version,
            'existing': existing_count,
            'missing': missing_count,
            'total': total_count,
            'existing_files': existing_files,
            'missing_items': missing_items
        })

        # Print summary for this version
        print(f"\nVersion {version}: {existing_count}/{total_count} existing, {missing_count} missing")

    # Ask if user wants detailed view
    if sum(stats['existing'] for stats in all_version_stats) > 0:
        print("\n" + "-"*70)
        show_details = input("Show detailed file list? [y/N]: ").strip().lower()

        if show_details == 'y':
            for stats in all_version_stats:
                if stats['existing'] > 0:
                    print(f"\n--- Version {stats['version']} - First 5 existing files ---")
                    for file_info in stats['existing_files'][:5]:
                        size_kb = file_info['size'] / 1024
                        rel_path = file_info['path'].relative_to(SCRIPT_DIR)
                        print(f"  ✓ {file_info['name']}: {rel_path} ({size_kb:.1f} KB)")

    print("="*70)
    return all_version_stats

# ============================================================================
# SELENIUM FUNCTIONS
# ============================================================================

def setup_driver():
    """Setup Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def fill_textareas(driver, prompt1, prompt2):
    """Fill the two textareas with prompts"""
    try:
        textareas = driver.find_elements(By.TAG_NAME, 'textarea')

        print(f"  [DEBUG] Found {len(textareas)} textareas")

        if len(textareas) < 2:
            print(f"  [DEBUG] ERROR: Need 2 textareas, found {len(textareas)}")
            return False

        # Debug: Show prompt lengths
        print(f"  [DEBUG] Persistent prompt length: {len(prompt1)} chars")
        print(f"  [DEBUG] Detail prompt length: {len(prompt2)} chars")

        # Fill first textarea
        print(f"  [DEBUG] Filling textarea 1...")
        textareas[0].click()
        time.sleep(0.2)
        textareas[0].send_keys(Keys.CONTROL + 'a')
        time.sleep(0.1)
        textareas[0].send_keys(prompt1)
        time.sleep(0.2)
        print(f"  [DEBUG] Textarea 1 filled")

        # Fill second textarea
        print(f"  [DEBUG] Filling textarea 2...")
        textareas[1].click()
        time.sleep(0.2)
        textareas[1].send_keys(Keys.CONTROL + 'a')
        time.sleep(0.1)
        textareas[1].send_keys(prompt2)
        time.sleep(0.2)
        print(f"  [DEBUG] Textarea 2 filled")

        return True

    except Exception as e:
        print(f"  [DEBUG] EXCEPTION in fill_textareas: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def select_cel_shaded_style(driver):
    """Click the Cel-Shaded style option"""
    try:
        print("  → Selecting Cel-Shaded style...")

        # Find image with alt="Cel-Shaded"
        imgs = driver.find_elements(By.TAG_NAME, 'img')

        for img in imgs:
            alt = img.get_attribute('alt') or ''
            src = img.get_attribute('src') or ''

            if 'cel-shaded' in alt.lower() or 'Cel-Shaded' in src:
                # Click the image (or its parent container)
                try:
                    # Try clicking parent first (usually a button/div)
                    parent = img.find_element(By.XPATH, './..')
                    parent.click()
                    print("  ✓ Cel-Shaded style selected")
                    time.sleep(1)
                    return True
                except:
                    # Fallback: click image itself
                    img.click()
                    print("  ✓ Cel-Shaded style selected")
                    time.sleep(1)
                    return True

        print("  ⚠ Cel-Shaded style not found (may already be default)")
        return True  # Don't fail if not found

    except Exception as e:
        print(f"  ⚠ Could not select style: {e}")
        return True  # Don't fail the whole process

def click_generate_button(driver):
    """Find and click Generate button"""
    buttons = driver.find_elements(By.TAG_NAME, 'button')

    for btn in buttons:
        if 'generate' in btn.text.lower():
            btn.click()
            return True

    return False

def wait_for_download_button(driver, timeout=180):
    """Wait for download SVG button to appear"""
    print(f"    Waiting for generation (up to {timeout}s)...", end="", flush=True)

    start = time.time()
    last_check = 0

    while time.time() - start < timeout:
        svgs = driver.find_elements(By.TAG_NAME, 'svg')

        for svg in svgs:
            paths = svg.find_elements(By.TAG_NAME, 'path')
            for path in paths:
                d = path.get_attribute('d') or ''
                if 'M12 13L12 3M12 13C' in d or 'M3.09502 10C' in d:
                    elapsed = time.time() - start
                    print(f" {elapsed:.0f}s ✓")
                    return svg

        # Progress update every 10 seconds
        current = int(time.time() - start)
        if current >= last_check + 10:
            last_check = current
            print(f"\n    [{current}s] Generating...", end="", flush=True)

        time.sleep(1)

    print(f"\n    ⚠ Timeout after {timeout}s")
    return None

def click_download_button(driver, download_svg):
    """Click the download button (SVG's parent)"""
    try:
        # Try to find clickable parent
        parent = download_svg
        for _ in range(3):
            parent = parent.find_element(By.XPATH, './..')
            if parent.tag_name.lower() in ['button', 'a', 'div']:
                parent.click()
                return True

        # Fallback: click SVG itself
        download_svg.click()
        return True
    except:
        return False

def get_downloaded_file(timeout=10):
    """Check Downloads folder for new image file"""
    downloads = Path.home() / 'Downloads'
    start = time.time()

    while time.time() - start < timeout:
        image_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
            image_files.extend(downloads.glob(ext))

        image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for file in image_files[:5]:
            age = time.time() - file.stat().st_mtime
            if age < 15:
                return file

        time.sleep(1)

    return None

def screenshot_with_crop(driver, save_path):
    """Screenshot image and crop 30px from all sides"""
    try:
        imgs = driver.find_elements(By.TAG_NAME, 'img')

        for img in imgs:
            src = img.get_attribute('src') or ''
            if 'blob:' in src or (img.size['width'] > 400 and img.size['height'] > 400):
                temp_path = save_path.parent / f"temp_{save_path.name}"
                img.screenshot(str(temp_path))

                # Crop 30px from all sides
                image = Image.open(temp_path)
                width, height = image.size
                cropped = image.crop((30, 30, width - 30, height - 30))
                cropped.save(save_path)
                temp_path.unlink()

                return True

        return False
    except:
        return False

# ============================================================================
# MAIN GENERATION
# ============================================================================

def generate_item(driver, item, version=1):
    """Generate one item icon

    Args:
        driver: Selenium WebDriver instance
        item: Item dictionary with name, category, etc.
        version: Version number (1, 2, 3, etc.) for multiple generations

    Returns:
        (success, skipped) tuple
    """
    name = item['name']
    base_folder = item.get('base_folder', 'items')
    subfolder = item.get('subfolder')

    # Modify output directory and filename based on version
    if version == 1:
        output_base = OUTPUT_DIR
        filename = f"{name}.png"
        version_label = ""
    else:
        output_base = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"
        filename = f"{name}-{version}.png"
        version_label = f" [v{version}]"

    # Build display path and save path
    if subfolder:
        display_path = f"{base_folder}/{subfolder}/{filename}"
        save_dir = output_base / base_folder / subfolder
    else:
        display_path = f"{base_folder}/{filename}"
        save_dir = output_base / base_folder

    print(f"\n{'='*70}")
    print(f"Entity: {name}{version_label}")
    print(f"Path: {display_path}")
    print(f"{'='*70}")

    # Check if already exists in output folder (simple & robust)
    save_path = save_dir / filename

    if save_path.exists() and save_path.stat().st_size > 10000:
        print("  ✓ Already exists (resuming)")
        return True, True

    try:
        # Fill textareas with version-specific persistent prompt
        print("  → Filling prompts...")
        persistent_prompt = get_persistent_prompt_for_version(version)
        detail_prompt = build_detail_prompt(item)
        if not fill_textareas(driver, persistent_prompt, detail_prompt):
            print("  ✗ Could not find textareas")
            return False, False

        # Click Generate
        print("  → Clicking Generate...")
        if not click_generate_button(driver):
            print("  ✗ Could not find Generate button")
            return False, False

        time.sleep(2)

        # Wait for download button to appear
        download_svg = wait_for_download_button(driver, GENERATION_TIMEOUT)

        if not download_svg:
            print("  ✗ Generation timeout")
            return False, False

        # Click download button
        print("  → Clicking download button...")
        if not click_download_button(driver, download_svg):
            print("  ⚠ Could not click download button")

        time.sleep(4)

        # Check for downloaded file
        print("  → Checking Downloads folder...")
        downloaded_file = get_downloaded_file()

        save_dir.mkdir(parents=True, exist_ok=True)

        if downloaded_file:
            print(f"  ✓ Downloaded: {downloaded_file.name}")
            shutil.move(str(downloaded_file), str(save_path))
            print(f"  ✓ Saved to: {save_path.relative_to(SCRIPT_DIR)}")
            return True, False
        else:
            print("  ⚠ Download not found, using screenshot...")
            if screenshot_with_crop(driver, save_path):
                print(f"  ✓ Screenshot saved: {save_path.relative_to(SCRIPT_DIR)}")
                return True, False
            else:
                print("  ✗ Failed to save")
                return False, False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, False

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*70)
    print("VHEER AUTOMATION")
    print("="*70)

    print(f"\n📁 Script: {SCRIPT_DIR}")
    print(f"💾 Output: {OUTPUT_DIR}")

    # Choose mode
    print("\nMode:")
    print("  [1] Test (2 items)")
    print("  [2] Full catalog")

    choice = input("\nChoice: ").strip()

    if choice == '2':
        if not CATALOG_PATH.exists():
            print(f"\n⚠ Catalog not found: {CATALOG_PATH}")
            items = TEST_ITEMS
        else:
            print("\nLoading catalog...")
            items = parse_catalog(CATALOG_PATH)
            print(f"✓ Loaded {len(items)} items")
    else:
        items = TEST_ITEMS

    print(f"\nItems: {len(items)}")
    print(f"Timeout: {GENERATION_TIMEOUT}s")
    print(f"Wait between: {WAIT_BETWEEN_ITEMS}s")
    print(f"Versions: {VERSIONS_TO_GENERATE}")

    # Pre-scan directories before opening browser
    pre_scan_directories(items, VERSIONS_TO_GENERATE)

    input("\nPress Enter to start browser and begin generation...")

    driver = setup_driver()

    try:
        print("\n🌐 Opening Vheer...")
        driver.get("https://vheer.com/app/game-assets-generator")
        time.sleep(8)
        print("✓ Page loaded")

        # Select Cel-Shaded style (once at start)
        select_cel_shaded_style(driver)
        print("✓ Ready\n")

        # Track totals across all versions
        total_success = 0
        total_failed = 0
        total_skipped = 0
        all_failed_items = []

        # Loop through all versions
        for version in range(1, VERSIONS_TO_GENERATE + 1):
            print("\n" + "="*70)
            print(f"GENERATING VERSION {version} of {VERSIONS_TO_GENERATE}")
            print("="*70)

            if version > 1:
                output_folder = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"
                print(f"📁 Output: {output_folder}")
            else:
                print(f"📁 Output: {OUTPUT_DIR}")

            success = 0
            failed = 0
            skipped = 0
            failed_list = []

            for i, item in enumerate(items, 1):
                print(f"\n[{i}/{len(items)}] Version {version}")

                ok, skip = generate_item(driver, item, version=version)

                if skip:
                    skipped += 1
                elif ok:
                    success += 1
                else:
                    failed += 1
                    failed_list.append(item['name'])

                print(f"\nVersion {version} Totals: ✓{success}  ✗{failed}  ⊘{skipped}")

                if i < len(items) and not skip:
                    print(f"⏱ Waiting {WAIT_BETWEEN_ITEMS}s...")
                    time.sleep(WAIT_BETWEEN_ITEMS)

            # Update totals
            total_success += success
            total_failed += failed
            total_skipped += skipped
            if failed_list:
                all_failed_items.extend([(version, name) for name in failed_list])

            print(f"\n✓ Version {version} complete: {success} generated, {skipped} skipped, {failed} failed")

            # Wait before next version
            if version < VERSIONS_TO_GENERATE:
                print(f"\n⏱ Waiting 30s before starting version {version + 1}...")
                time.sleep(30)

        # Final summary
        print("\n" + "="*70)
        print("ALL VERSIONS COMPLETE!")
        print("="*70)
        print(f"✓ Total Success: {total_success}")
        print(f"✗ Total Failed: {total_failed}")
        print(f"⊘ Total Skipped: {total_skipped}")

        if total_success > 0:
            print(f"\n📁 Base output: {OUTPUT_DIR.absolute()}")
            if VERSIONS_TO_GENERATE > 1:
                for v in range(2, VERSIONS_TO_GENERATE + 1):
                    versioned_dir = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{v}"
                    print(f"📁 Version {v}: {versioned_dir.absolute()}")

        if all_failed_items:
            print(f"\n⚠ Failed items:")
            for version, name in all_failed_items:
                print(f"  - v{version}: {name}")

        print("="*70)

        input("\nPress Enter to close...")

    except KeyboardInterrupt:
        print("\n\n⏸ Interrupted")

    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()
        print("\n✓ Closed")

if __name__ == "__main__":
    main()
