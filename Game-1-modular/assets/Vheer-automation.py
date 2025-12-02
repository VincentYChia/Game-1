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
DEBUG_MODE = False  # Set to True to see detailed element detection info

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def debug_page_elements(driver):
    """Debug helper: Print all potential download-related elements"""
    if not DEBUG_MODE:
        return

    print("\n  [DEBUG] Page elements:")

    # Check buttons
    try:
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        print(f"  - Buttons: {len(buttons)}")
        for i, btn in enumerate(buttons[:10]):  # First 10
            text = btn.text[:30] if btn.text else ""
            aria = btn.get_attribute('aria-label') or ""
            print(f"    [{i}] text='{text}' aria='{aria}'")
    except Exception as e:
        print(f"  - Buttons error: {e}")

    # Check SVGs
    try:
        svgs = driver.find_elements(By.TAG_NAME, 'svg')
        print(f"  - SVGs: {len(svgs)}")
        download_svgs = [s for s in svgs
                        if 'download' in (s.get_attribute('aria-label') or '').lower() or
                           'download' in (s.get_attribute('class') or '').lower()]
        print(f"    - With 'download': {len(download_svgs)}")
    except Exception as e:
        print(f"  - SVGs error: {e}")

    # Check images
    try:
        imgs = driver.find_elements(By.TAG_NAME, 'img')
        blob_imgs = [img for img in imgs if 'blob:' in (img.get_attribute('src') or '')]
        print(f"  - Images: {len(imgs)} total, {len(blob_imgs)} with blob URLs")
    except Exception as e:
        print(f"  - Images error: {e}")

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
    """Build detail prompt from item data"""
    return f"""Generate an icon image off of the item description:
Category: {item['category']}
Type: {item['type']}
Subtype: {item['subtype']}
Narrative: {item['narrative']}"""

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

def safe_driver_get(driver, url, max_retries=3):
    """Safely navigate to URL with connection retry logic

    Args:
        driver: Selenium WebDriver instance
        url: URL to navigate to
        max_retries: Maximum number of retry attempts

    Returns:
        True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            driver.get(url)
            return True
        except Exception as e:
            print(f"  ⚠ Connection error (attempt {attempt+1}/{max_retries}): {type(e).__name__}")
            if attempt < max_retries - 1:
                wait_time = 10 * (attempt + 1)  # Increasing wait: 10s, 20s, 30s
                print(f"  → Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"  ✗ Failed after {max_retries} attempts")
                return False
    return False

def restart_driver(old_driver):
    """Restart the driver after a crash or connection error

    Args:
        old_driver: The driver instance to restart

    Returns:
        New driver instance
    """
    print("\n🔄 Browser connection lost - restarting...")

    try:
        old_driver.quit()
    except:
        pass

    time.sleep(5)

    new_driver = setup_driver()

    if not safe_driver_get(new_driver, "https://vheer.com/app/game-assets-generator"):
        raise Exception("Failed to restart driver - check internet connection")

    print("  → Waiting for page to load...")
    time.sleep(8)

    select_cel_shaded_style(new_driver)
    print("✓ Browser restarted and ready\n")

    return new_driver

def fill_textareas(driver, prompt1, prompt2):
    """Fill the two textareas with prompts"""
    textareas = driver.find_elements(By.TAG_NAME, 'textarea')

    if len(textareas) < 2:
        return False

    # Fill first textarea
    textareas[0].click()
    time.sleep(0.2)
    textareas[0].send_keys(Keys.CONTROL + 'a')
    time.sleep(0.1)
    textareas[0].send_keys(prompt1)
    time.sleep(0.2)

    # Fill second textarea
    textareas[1].click()
    time.sleep(0.2)
    textareas[1].send_keys(Keys.CONTROL + 'a')
    time.sleep(0.1)
    textareas[1].send_keys(prompt2)
    time.sleep(0.2)

    return True

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
    """Wait for download button to appear (robust multi-method detection)"""
    print(f"    Waiting for generation (up to {timeout}s)...", end="", flush=True)

    start = time.time()
    last_check = 0

    while time.time() - start < timeout:
        # METHOD 1: Look for buttons with "download" text
        try:
            buttons = driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                text = (btn.text or '').lower()
                aria_label = (btn.get_attribute('aria-label') or '').lower()
                if 'download' in text or 'download' in aria_label:
                    elapsed = time.time() - start
                    print(f" {elapsed:.0f}s ✓ (text)")
                    return btn
        except:
            pass

        # METHOD 2: Look for SVG download icons (flexible path matching)
        try:
            svgs = driver.find_elements(By.TAG_NAME, 'svg')
            for svg in svgs:
                # Check SVG attributes
                aria_label = (svg.get_attribute('aria-label') or '').lower()
                class_name = (svg.get_attribute('class') or '').lower()

                if 'download' in aria_label or 'download' in class_name:
                    elapsed = time.time() - start
                    print(f" {elapsed:.0f}s ✓ (svg-attr)")
                    return svg

                # Check path data for download-like patterns
                paths = svg.find_elements(By.TAG_NAME, 'path')
                for path in paths:
                    d = (path.get_attribute('d') or '').strip()
                    # Common download icon patterns:
                    # - Arrow pointing down: M12 (vertical line or arrow)
                    # - Download tray: M3, M4, M5 (horizontal base)
                    if d:  # Has path data
                        # Check for known download icon patterns
                        if ('M12' in d and 'L12' in d) or \
                           ('M3' in d and ('M21' in d or 'H21' in d)) or \
                           ('M4' in d and 'M20' in d) or \
                           'M12 13L12 3M12 13C' in d or \
                           'M3.09502 10C' in d:
                            elapsed = time.time() - start
                            print(f" {elapsed:.0f}s ✓ (svg-path)")
                            return svg
        except:
            pass

        # METHOD 3: Look for generated images (blob URLs or large images)
        try:
            imgs = driver.find_elements(By.TAG_NAME, 'img')
            for img in imgs:
                src = img.get_attribute('src') or ''
                # Look for blob URLs (generated content) or data URLs
                if ('blob:' in src or 'data:image' in src):
                    # Check if image is reasonably large (generated icon, not UI element)
                    try:
                        size = img.size
                        if size['width'] > 300 and size['height'] > 300:
                            elapsed = time.time() - start
                            print(f" {elapsed:.0f}s ✓ (image)")
                            # Return a dummy element that signals success
                            return img
                    except:
                        pass
        except:
            pass

        # METHOD 4: Look for specific download button classes/IDs
        try:
            # Common patterns for download buttons
            download_elements = driver.find_elements(By.XPATH,
                "//*[contains(@class, 'download') or contains(@id, 'download') or "
                "contains(@data-action, 'download') or contains(@title, 'Download')]")

            if download_elements:
                elapsed = time.time() - start
                print(f" {elapsed:.0f}s ✓ (xpath)")
                return download_elements[0]
        except:
            pass

        # Progress update every 10 seconds
        current = int(time.time() - start)
        if current >= last_check + 10:
            last_check = current
            print(f"\n    [{current}s] Generating...", end="", flush=True)

        time.sleep(1)

    print(f"\n    ⚠ Timeout after {timeout}s")

    # Debug: Show what elements are present at timeout
    if DEBUG_MODE:
        debug_page_elements(driver)

    return None

def click_download_button(driver, download_element):
    """Click the download button (handles various element types)"""
    try:
        element_tag = download_element.tag_name.lower()

        # If it's already a button, click it directly
        if element_tag == 'button':
            download_element.click()
            return True

        # If it's an image, look for download button nearby
        if element_tag == 'img':
            # Try to find download button in the page
            try:
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                for btn in buttons:
                    text = (btn.text or '').lower()
                    aria = (btn.get_attribute('aria-label') or '').lower()
                    if 'download' in text or 'download' in aria:
                        btn.click()
                        return True
            except:
                pass

        # For SVG or other elements, try to find clickable parent
        parent = download_element
        for _ in range(4):
            try:
                parent = parent.find_element(By.XPATH, './..')
                parent_tag = parent.tag_name.lower()

                # Check if parent looks clickable
                onclick = parent.get_attribute('onclick')
                role = parent.get_attribute('role')
                cursor = parent.value_of_css_property('cursor')

                if parent_tag in ['button', 'a'] or \
                   onclick or \
                   role == 'button' or \
                   cursor == 'pointer':
                    parent.click()
                    return True
            except:
                break

        # Fallback: click element itself
        download_element.click()
        return True

    except Exception as e:
        print(f"  ⚠ Click error: {e}")
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

def generate_item(driver, item, timeout=None, version=1):
    """Generate one item icon

    Args:
        driver: Selenium WebDriver instance
        item: Item dictionary with name, category, etc.
        timeout: Optional timeout override (default: GENERATION_TIMEOUT)
        version: Version number (1, 2, 3, etc.) for multiple generations

    Returns:
        (success, skipped) tuple
    """
    if timeout is None:
        timeout = GENERATION_TIMEOUT

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
        # Fill textareas
        print("  → Filling prompts...")
        detail_prompt = build_detail_prompt(item)
        if not fill_textareas(driver, PERSISTENT_PROMPT, detail_prompt):
            print("  ✗ Could not find textareas")
            return False, False

        # Click Generate
        print("  → Clicking Generate...")
        if not click_generate_button(driver):
            print("  ✗ Could not find Generate button")
            return False, False

        time.sleep(2)

        # Wait for download button to appear (use passed timeout)
        download_svg = wait_for_download_button(driver, timeout)

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

def generate_item_with_retry(driver, item, version=1):
    """Generate item with escalating retry logic

    Retry strategy:
    1. First attempt: normal timeout
    2. Second attempt: 1.5x timeout
    3. Third attempt: refresh page, wait 20s, retry

    Args:
        driver: Selenium WebDriver instance
        item: Item dictionary
        version: Version number for multi-generation

    Returns:
        (success, skipped) tuple
    """
    # Attempt 1: Normal timeout
    ok, skip = generate_item(driver, item, timeout=GENERATION_TIMEOUT, version=version)
    if ok or skip:
        return ok, skip

    # Attempt 2: Extended timeout (1.5x)
    print("\n  ⚠ RETRY 1/2: Extending timeout to 1.5x...")
    extended_timeout = int(GENERATION_TIMEOUT * 1.5)
    ok, skip = generate_item(driver, item, timeout=extended_timeout, version=version)
    if ok or skip:
        return ok, skip

    # Attempt 3: Refresh page and retry
    print("\n  ⚠ RETRY 2/2: Refreshing page...")
    try:
        if not safe_driver_get(driver, "https://vheer.com/app/game-assets-generator"):
            print("  ✗ Could not reload page")
            return False, False

        print("  → Waiting 20s for page to settle...")
        time.sleep(20)

        # Re-select cel-shaded style
        select_cel_shaded_style(driver)
        print("  → Retrying generation...")

        ok, skip = generate_item(driver, item, timeout=GENERATION_TIMEOUT, version=version)
        return ok, skip

    except Exception as e:
        print(f"  ✗ Refresh failed: {e}")
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

    input("\nPress Enter to start...")

    driver = setup_driver()

    try:
        print("\n🌐 Opening Vheer...")
        if not safe_driver_get(driver, "https://vheer.com/app/game-assets-generator"):
            print("\n❌ Could not connect to Vheer - check internet connection")
            return

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

                # Try to generate with connection error recovery
                try:
                    ok, skip = generate_item_with_retry(driver, item, version=version)

                    if skip:
                        skipped += 1
                    elif ok:
                        success += 1
                    else:
                        failed += 1
                        failed_list.append(item['name'])

                except Exception as e:
                    # Check if it's a connection error
                    error_str = str(e).lower()
                    if "connection" in error_str or "timeout" in error_str or "read timed out" in error_str:
                        print(f"  ⚠ Driver connection error: {type(e).__name__}")

                        try:
                            # Restart driver and retry this item
                            driver = restart_driver(driver)

                            print(f"  → Retrying item after restart...")
                            ok, skip = generate_item_with_retry(driver, item, version=version)

                            if skip:
                                skipped += 1
                            elif ok:
                                success += 1
                            else:
                                failed += 1
                                failed_list.append(item['name'])

                        except Exception as restart_error:
                            print(f"  ✗ Failed to restart driver: {restart_error}")
                            failed += 1
                            failed_list.append(item['name'])
                    else:
                        # Not a connection error - re-raise
                        raise

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