"""
Vheer AI Game Assets Generator - Automation Script
Generates icons for game items automatically

Requirements:
- pip install selenium webdriver-manager pillow

Usage:
1. Run script
2. Choose test mode (2 items) or full catalog
3. Script will generate all icons automatically
##Minimize the screen to 50% for best outcomes
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    InvalidSessionIdException,
    NoSuchWindowException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from pathlib import Path
import time
import re
import shutil

# ============================================================================
# CONFIGURATION  2
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
    'station': 'Tier 1, Tier 2, Tier 3, and Tier 4 represent tiers 1 through 4. 4 is the most advanced and should have the most detail. 1 is the simplest and should be simplest in design',
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
CATALOG_PATH = SCRIPT_DIR / 'icons' / 'ITEM_CATALOG_FOR_ICONS.md'

GENERATION_TIMEOUT = 180
WAIT_BETWEEN_ITEMS = 25
VERSIONS_TO_GENERATE = 3

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_connection_error(exception):
    """Check if an exception is a connection/session error that requires driver restart"""
    if isinstance(exception, (InvalidSessionIdException, NoSuchWindowException)):
        return True

    error_str = str(exception).lower()
    connection_keywords = [
        'invalid session', 'no such window', 'chrome not reachable',
        'connection refused', 'connection reset', 'broken pipe'
    ]

    if any(keyword in error_str for keyword in connection_keywords):
        return True

    if 'read timed out' in error_str and 'localhost' in error_str:
        return True

    return False

def handle_popup_ad(driver):
    """Try multiple strategies to handle popup ads"""
    try:
        # Strategy 1: Wait for popup to disappear (max 10 seconds)
        print("  → Waiting for popup ad to clear...")
        time.sleep(3)

        # Strategy 2: Try to find and click close button
        close_selectors = [
            "button[aria-label='Close']",
            "button.close",
            ".popup-close",
            ".ad-close",
            "[class*='close']",
            "button:has(svg)"  # Close buttons often have X icons
        ]

        for selector in close_selectors:
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if close_btn.is_displayed():
                    close_btn.click()
                    print(f"  ✓ Closed popup using: {selector}")
                    time.sleep(1)
                    return True
            except:
                continue

        # Strategy 3: Remove popup overlay with JavaScript
        driver.execute_script("""
            // Remove common popup/overlay elements
            var overlays = document.querySelectorAll('[class*="popup"], [class*="overlay"], [class*="modal"]');
            overlays.forEach(el => el.remove());
        """)
        print("  ✓ Removed popup overlays with JavaScript")
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"  ⚠ Could not handle popup: {e}")
        return False

def categorize_item(item):
    """Determine subfolder based on item properties"""
    category = item.get('category', '').lower()
    item_type = item.get('type', '').lower()

    if category == 'enemy':
        return ('enemies', None)
    if category == 'resource':
        return ('resources', None)
    if category == 'title':
        return ('titles', None)
    if category == 'skill':
        return ('skills', None)

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
            return ('items', 'weapons')

    if category == 'station':
        return ('items', 'stations')
    if category == 'device':
        return ('items', 'devices')
    if category == 'consumable':
        return ('items', 'consumables')

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

            base_folder, subfolder = categorize_item(item_data)
            item_data['base_folder'] = base_folder
            item_data['subfolder'] = subfolder

            items.append(item_data)

    return items

def build_detail_prompt(item):
    """Build detail prompt from item data with optional additions"""
    try:
        base_prompt = f"""Generate an icon image off of the item description:
Icon_name: {item['name']}
Category: {item['category']}
Type: {item['type']}
Subtype: {item['subtype']}
Narrative: {item['narrative']}"""


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
    """Get the persistent prompt for a specific version"""
    return VERSION_PROMPTS.get(version, PERSISTENT_PROMPT)

def pre_scan_directories(items, versions_to_generate):
    """Scan output directories before browser opens"""
    print("\n" + "="*70)
    print("PRE-SCAN: Checking existing files")
    print("="*70)

    MIN_FILE_SIZE = 5000

    all_version_stats = []

    for version in range(1, versions_to_generate + 1):
        if version == 1:
            output_base = OUTPUT_DIR
        else:
            output_base = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"

        existing_files = []
        missing_items = []

        for item in items:
            name = item['name']
            base_folder = item.get('base_folder', 'items')
            subfolder = item.get('subfolder')

            if version == 1:
                filename = f"{name}.png"
            else:
                filename = f"{name}-{version}.png"

            if subfolder:
                save_dir = output_base / base_folder / subfolder
            else:
                save_dir = output_base / base_folder

            save_path = save_dir / filename

            if save_path.exists() and save_path.stat().st_size > MIN_FILE_SIZE:
                existing_files.append({
                    'name': name,
                    'path': save_path,
                    'size': save_path.stat().st_size
                })
            else:
                missing_items.append(name)

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

        print(f"\nVersion {version}: {existing_count}/{total_count} existing, {missing_count} missing")

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
    chrome_options.page_load_strategy = 'eager'

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def safe_driver_get(driver, url, max_retries=3):
    """Safely navigate to URL with connection retry logic"""
    for attempt in range(max_retries):
        try:
            driver.get(url)
            return True
        except Exception as e:
            print(f"  ⚠ Connection error (attempt {attempt+1}/{max_retries}): {type(e).__name__}")
            if attempt < max_retries - 1:
                wait_time = 10 * (attempt + 1)
                print(f"  → Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"  ✗ Failed after {max_retries} attempts")
                return False
    return False

def restart_driver(old_driver):
    """Restart the driver after a crash or connection error"""
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
    time.sleep(16)

    select_cel_shaded_style(new_driver)
    print("✓ Browser restarted and ready\n")

    return new_driver

def fill_textareas(driver, prompt1, prompt2):
    """Fill the two textareas with prompts"""
    try:
        textareas = driver.find_elements(By.TAG_NAME, 'textarea')

        print(f"  [DEBUG] Found {len(textareas)} textareas")

        if len(textareas) < 2:
            print(f"  [DEBUG] ERROR: Need 2 textareas, found {len(textareas)}")
            return False

        print(f"  [DEBUG] Persistent prompt length: {len(prompt1)} chars")
        print(f"  [DEBUG] Detail prompt length: {len(prompt2)} chars")

        print(f"  [DEBUG] Filling textarea 1...")
        textareas[0].click()
        time.sleep(0.2)
        textareas[0].send_keys(Keys.CONTROL + 'a')
        time.sleep(0.1)
        textareas[0].send_keys(prompt1)
        time.sleep(0.2)
        print(f"  [DEBUG] Textarea 1 filled")

        print(f"  [DEBUG] Filling textarea 2...")
        textareas[1].click()
        time.sleep(0.2)
        textareas[1].send_keys(Keys.CONTROL + 'a')
        time.sleep(0.1)
        textareas[1].send_keys(prompt2)
        time.sleep(1)
        print(f"  [DEBUG] Textarea 2 filled")

        return True

    except Exception as e:
        print(f"  [DEBUG] EXCEPTION in fill_textareas: {type(e).__name__}: {e}")

        if is_connection_error(e):
            print(f"  [DEBUG] Connection error detected - will restart driver")
            raise

        import traceback
        traceback.print_exc()
        return False

def select_cel_shaded_style(driver):
    """Click the Cel-Shaded style option"""
    try:
        print("  → Selecting Cel-Shaded style...")

        imgs = driver.find_elements(By.TAG_NAME, 'img')

        for img in imgs:
            alt = img.get_attribute('alt') or ''
            src = img.get_attribute('src') or ''

            if 'cel-shaded' in alt.lower() or 'Cel-Shaded' in src:
                try:
                    parent = img.find_element(By.XPATH, './..')
                    parent.click()
                    print("  ✓ Cel-Shaded style selected")
                    time.sleep(1)
                    return True
                except:
                    img.click()
                    print("  ✓ Cel-Shaded style selected")
                    time.sleep(1)
                    return True

        print("  ⚠ Cel-Shaded style not found (may already be default)")
        return True

    except Exception as e:
        print(f"  ⚠ Could not select style: {e}")
        return True

def click_generate_button(driver):
    """Find and click Generate button with popup handling"""
    try:
        # First, try to handle any popups
        handle_popup_ad(driver)

        buttons = driver.find_elements(By.TAG_NAME, 'button')

        for btn in buttons:
            if 'generate' in btn.text.lower():
                try:
                    # Try normal click first
                    btn.click()
                    print("  ✓ Generate button clicked (normal)")
                    return True
                except Exception as e:
                    if 'intercepted' in str(e).lower():
                        print("  ⚠ Click intercepted, trying JavaScript click...")
                        # Use JavaScript click to bypass popup
                        driver.execute_script("arguments[0].click();", btn)
                        print("  ✓ Generate button clicked (JavaScript)")
                        return True
                    raise

        return False

    except Exception as e:
        print(f"  ✗ Error clicking generate: {e}")
        return False

def wait_for_generation_complete(driver, timeout=180):
    """Wait for download button to appear - ROBUST VERSION

    Checks every 5 seconds, with detailed logging and stale element handling
    """
    print(f"    Waiting for generation (up to {timeout}s)...")

    start = time.time()
    check_count = 0

    while time.time() - start < timeout:
        check_count += 1
        elapsed = int(time.time() - start)

        # Progress every 15 seconds
        if check_count % 3 == 1:
            print(f"    [{elapsed}s] Checking...", flush=True)

        try:
            # Get fresh list of SVGs each time
            svgs = driver.find_elements(By.TAG_NAME, 'svg')

            # Check each SVG
            for svg_index, svg in enumerate(svgs):
                try:
                    # Get paths for this SVG - handle stale elements
                    paths = svg.find_elements(By.TAG_NAME, 'path')

                    for path_index, path in enumerate(paths):
                        try:
                            # Get the 'd' attribute - this is where we often fail
                            d = path.get_attribute('d')

                            if not d:
                                continue

                            # Check for download button signatures
                            # Arc path (top of download arrow)
                            if 'M3.09502 10C' in d and '21 11.4' in d:
                                print(f"    [{elapsed}s] ✓ Found download button (arc path)!")
                                return svg

                            # Arrow path (main shaft and chevron)
                            if 'M12 13L12 3' in d and 'M12 13C' in d:
                                print(f"    [{elapsed}s] ✓ Found download button (arrow path)!")
                                return svg

                        except StaleElementReferenceException:
                            # Path became stale, continue to next
                            continue
                        except Exception as path_err:
                            # Log unexpected path errors in first few checks
                            if check_count <= 2:
                                print(f"    [DEBUG] Path {path_index} error: {type(path_err).__name__}")
                            continue

                except StaleElementReferenceException:
                    # SVG became stale, continue to next
                    continue
                except Exception as svg_err:
                    # Log unexpected SVG errors in first few checks
                    if check_count <= 2:
                        print(f"    [DEBUG] SVG {svg_index} error: {type(svg_err).__name__}")
                    continue

        except (InvalidSessionIdException, NoSuchWindowException):
            # Fatal connection errors - re-raise
            raise
        except Exception as e:
            print(f"    [DEBUG] Check error: {type(e).__name__}")

        # Wait 5 seconds before next check
        time.sleep(5)

    print(f"    ✗ Timeout after {timeout}s - button never detected")
    return None

def click_download_button(driver, download_svg):
    """Click the download button (SVG's parent)"""
    try:
        parent = download_svg
        for _ in range(3):
            parent = parent.find_element(By.XPATH, './..')
            if parent.tag_name.lower() in ['button', 'a', 'div']:
                parent.click()
                return True

        download_svg.click()
        return True
    except:
        return False

def get_downloaded_file(timeout=10):
    """Check Downloads folder for new image file"""
    downloads = Path.home() / 'Downloads'
    start = time.time()

    print(f"  [DEBUG] Checking Downloads folder: {downloads}")

    while time.time() - start < timeout:
        image_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
            image_files.extend(downloads.glob(ext))

        image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        print(f"  [DEBUG] Found {len(image_files)} image files, checking most recent 5...")

        for file in image_files[:5]:
            age = time.time() - file.stat().st_mtime
            print(f"  [DEBUG]   {file.name}: {age:.1f}s old")
            if age < 15:
                print(f"  [DEBUG] ✓ Found recent file: {file.name}")
                return file

        time.sleep(1)

    print(f"  [DEBUG] ✗ No recent files found after {timeout}s")
    return None

def screenshot_with_crop(driver, save_path):
    """Screenshot image and crop 30px from all sides"""
    try:
        print(f"  [DEBUG] Attempting screenshot fallback...")
        imgs = driver.find_elements(By.TAG_NAME, 'img')
        print(f"  [DEBUG] Found {len(imgs)} images on page")

        for img in imgs:
            src = img.get_attribute('src') or ''
            size = img.size
            print(f"  [DEBUG]   Checking image: src={src[:50]}... size={size['width']}x{size['height']}")

            if 'blob:' in src or (size['width'] > 400 and size['height'] > 400):
                print(f"  [DEBUG]   ✓ Found suitable image for screenshot")
                temp_path = save_path.parent / f"temp_{save_path.name}"

                img.screenshot(str(temp_path))
                print(f"  [DEBUG]   Screenshot taken: {temp_path}")

                image = Image.open(temp_path)
                width, height = image.size
                print(f"  [DEBUG]   Cropping from {width}x{height}...")
                cropped = image.crop((30, 30, width - 30, height - 30))
                cropped.save(save_path)
                temp_path.unlink()
                print(f"  [DEBUG]   ✓ Screenshot saved and cropped")

                return True

        print(f"  [DEBUG] ✗ No suitable images found for screenshot")
        return False
    except Exception as e:
        print(f"  [DEBUG] ✗ Screenshot failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MAIN GENERATION
# ============================================================================

def generate_item(driver, item, version=1):
    """Generate one item icon"""
    name = item['name']
    base_folder = item.get('base_folder', 'items')
    subfolder = item.get('subfolder')

    if version == 1:
        output_base = OUTPUT_DIR
        filename = f"{name}.png"
        version_label = ""
    else:
        output_base = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"
        filename = f"{name}-{version}.png"
        version_label = f" [v{version}]"

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

    save_path = save_dir / filename

    if save_path.exists() and save_path.stat().st_size > 10000:
        print("  ✓ Already exists (resuming)")
        return True, True

    try:
        print("  → Filling prompts...")
        print("  [DEBUG] Operation: fill_textareas")
        persistent_prompt = get_persistent_prompt_for_version(version)
        detail_prompt = build_detail_prompt(item)
        if not fill_textareas(driver, persistent_prompt, detail_prompt):
            print("  ✗ Could not find textareas")
            return False, False
        time.sleep(1)

        print("  → Clicking Generate...")
        print("  [DEBUG] Operation: click_generate_button")
        if not click_generate_button(driver):
            print("  ✗ Could not find Generate button")
            return False, False

        time.sleep(2)

        print("  [DEBUG] Operation: wait_for_generation_complete (may take up to 180s)")
        try:
            result = wait_for_generation_complete(driver, GENERATION_TIMEOUT)

            if not result:
                print("  ✗ Generation timeout (no completion signal)")
                return False, False

            download_svg = result if hasattr(result, 'tag_name') else None

        except Exception as wait_error:
            print(f"  [DEBUG] Exception during wait_for_generation_complete: {type(wait_error).__name__}")
            if is_connection_error(wait_error):
                print(f"  [DEBUG] Connection error during generation wait - restarting driver")
                raise
            print(f"  ✗ Generation failed with error: {wait_error}")
            return False, False

        if download_svg:
            print("  → Clicking download button...")
            if not click_download_button(driver, download_svg):
                print("  ⚠ Could not click download button")
        else:
            print("  → Image detected, attempting download...")

        time.sleep(4)

        print("  → Checking Downloads folder...")
        downloaded_file = get_downloaded_file()

        print(f"  [DEBUG] Creating directory: {save_dir}")
        save_dir.mkdir(parents=True, exist_ok=True)
        print(f"  [DEBUG] Directory ready")

        if downloaded_file:
            print(f"  ✓ Downloaded: {downloaded_file.name}")
            print(f"  [DEBUG] Moving from: {downloaded_file}")
            print(f"  [DEBUG] Moving to: {save_path}")
            try:
                shutil.move(str(downloaded_file), str(save_path))
                print(f"  [DEBUG] ✓ File moved successfully")
                final_size = save_path.stat().st_size
                print(f"  [DEBUG] Final file size: {final_size} bytes ({final_size/1024:.1f} KB)")
                print(f"  ✓ Saved to: {save_path.relative_to(SCRIPT_DIR)}")
                return True, False
            except Exception as e:
                print(f"  [DEBUG] ✗ Move failed: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                return False, False
        else:
            print("  ⚠ Download not found, using screenshot...")
            if screenshot_with_crop(driver, save_path):
                final_size = save_path.stat().st_size
                print(f"  [DEBUG] Screenshot file size: {final_size} bytes ({final_size/1024:.1f} KB)")
                print(f"  ✓ Screenshot saved: {save_path.relative_to(SCRIPT_DIR)}")
                return True, False
            else:
                print("  ✗ Failed to save")
                return False, False

    except Exception as e:
        print(f"  [DEBUG] Exception caught in generate_item: {type(e).__name__}")
        print(f"  [DEBUG] Error details: {str(e)[:200]}")

        if is_connection_error(e):
            print(f"  ✗ Connection error detected: {type(e).__name__}")
            print(f"  [DEBUG] This error requires driver restart")
            raise
        else:
            print(f"  ✗ Operation error (not connection): {type(e).__name__}")
            print(f"  [DEBUG] This error does not require driver restart, continuing...")

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

    pre_scan_directories(items, VERSIONS_TO_GENERATE)

    input("\nPress Enter to start browser and begin generation...")

    driver = setup_driver()

    try:
        print("\n🌐 Opening Vheer...")
        if not safe_driver_get(driver, "https://vheer.com/app/game-assets-generator"):
            print("✗ Failed to open Vheer after multiple retries")
            driver.quit()
            return
        time.sleep(16)
        driver.get("https://vheer.com/app/game-assets-generator")
        time.sleep(8)
        print("✓ Page loaded")

        select_cel_shaded_style(driver)
        print("✓ Ready\n")

        total_success = 0
        total_failed = 0
        total_skipped = 0
        all_failed_items = []

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

                try:
                    ok, skip = generate_item(driver, item, version=version)

                    if skip:
                        skipped += 1
                    elif ok:
                        success += 1
                    else:
                        failed += 1
                        failed_list.append(item['name'])

                except Exception as e:
                    if is_connection_error(e):
                        print(f"  ⚠ Driver connection error: {type(e).__name__}")

                        try:
                            driver = restart_driver(driver)

                            print(f"  → Retrying item after restart...")
                            ok, skip = generate_item(driver, item, version=version)

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
                        raise

                print(f"\nVersion {version} Totals: ✓{success}  ✗{failed}  ⊘{skipped}")

                if i < len(items) and not skip:
                    print(f"⏱ Waiting {WAIT_BETWEEN_ITEMS}s...")
                    time.sleep(WAIT_BETWEEN_ITEMS)

            total_success += success
            total_failed += failed
            total_skipped += skipped
            if failed_list:
                all_failed_items.extend([(version, name) for name in failed_list])

            print(f"\n✓ Version {version} complete: {success} generated, {skipped} skipped, {failed} failed")

            if version < VERSIONS_TO_GENERATE:
                print(f"\n⏱ Waiting 30s before starting version {version + 1}...")
                time.sleep(30)

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