"""
Vheer Automation - SIMPLE & RELIABLE
No coordinates. Just finds elements and interacts with them.

Requirements:
- pip install selenium webdriver-manager pillow

This script:
1. Opens Vheer
2. Finds the 2 textareas (by index, since they're unlabeled)
3. Fills them with Ctrl+A and typing
4. Clicks Generate button
5. Waits for image
6. Screenshots it
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
from pathlib import Path
from PIL import Image
import re

# ============================================================================
# CONFIGURATION
# ============================================================================

# Persistent prompt
PERSISTENT_PROMPT = "Simple cel-shaded 3d stylized fantasy exploration item icons. Clean render, distinct details, transparent background."

# Test items
TEST_ITEMS = [
    {
        'name': 'Iron_Sword',
        'subfolder': 'weapons',
        'category': 'equipment',
        'type': 'weapon',
        'subtype': 'shortsword',
        'narrative': 'A basic but reliable blade forged from iron.'
    },
    {
        'name': 'Health_Potion',
        'subfolder': 'consumables',
        'category': 'consumable',
        'type': 'potion',
        'subtype': 'healing',
        'narrative': 'A red vial filled with healing liquid.'
    }
]

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / 'generated_icons'  # Clear folder right next to script
CATALOG_PATH = SCRIPT_DIR.parent.parent / "Scaled JSON Development" / "ITEM_CATALOG_FOR_ICONS.md"

# Settings
GENERATION_WAIT = 180  # seconds to wait for generation
BETWEEN_ITEMS = 25     # seconds between items
DEBUG_MODE = False     # Set to True to pause before clicking Generate

# ============================================================================
# SETUP
# ============================================================================

def setup_driver():
    """Setup Chrome"""
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    print("✓ Chrome ready")
    return driver

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_detail_prompt(item):
    """Build detail prompt from item data"""
    return f"""Generate an icon image off of the item description:
Category: {item['category']}
Type: {item['type']}
Subtype: {item['subtype']}
Narrative: {item['narrative']}"""

def categorize_item(item):
    """Determine subfolder"""
    category = item.get('category', '').lower()
    item_type = item.get('type', '').lower()

    if category == 'equipment' and item_type == 'weapon':
        return 'weapons'
    if category == 'equipment' and item_type == 'armor':
        return 'armor'
    if category == 'equipment' and item_type == 'tool':
        return 'tools'
    if category == 'equipment' and item_type == 'accessory':
        return 'accessories'
    if category == 'station':
        return 'stations'
    if category == 'device':
        return 'devices'
    if category == 'consumable':
        return 'consumables'
    return 'materials'

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
            item_data['subfolder'] = categorize_item(item_data)
            items.append(item_data)

    return items

# ============================================================================
# CORE AUTOMATION
# ============================================================================

def fill_textarea(textarea, text):
    """Fill textarea: click, Ctrl+A, type"""
    textarea.click()
    time.sleep(0.2)
    textarea.send_keys(Keys.CONTROL + 'a')
    time.sleep(0.1)
    textarea.send_keys(text)
    time.sleep(0.2)

def wait_for_image(driver, timeout=180):
    """Wait for generation to complete by watching for download button"""
    print(f"    Waiting for generation (up to {timeout}s)...", end="", flush=True)

    start = time.time()
    last_check = 0

    while time.time() - start < timeout:
        try:
            # Look for download button (most reliable indicator)
            buttons = driver.find_elements(By.TAG_NAME, 'button')

            for btn in buttons:
                text = btn.text.lower()
                aria = (btn.get_attribute('aria-label') or '').lower()

                if 'download' in text or 'download' in aria:
                    elapsed = time.time() - start
                    print(f" {elapsed:.0f}s ✓ (download button appeared)")

                    # Now find the actual image
                    imgs = driver.find_elements(By.TAG_NAME, 'img')
                    for img in imgs:
                        src = img.get_attribute('src') or ''
                        if 'blob:' in src:
                            return img

                    # If no blob image, return any large image
                    for img in imgs:
                        try:
                            if img.size['width'] > 200 and img.size['height'] > 200:
                                return img
                        except:
                            continue

                    # Return first image as last resort
                    return imgs[0] if imgs else None

            # Progress check every 10 seconds
            current_time = int(time.time() - start)
            if current_time >= last_check + 10:
                last_check = current_time
                print(f"\n    [{current_time}s] Still generating...", end="", flush=True)

                # Check for loading/generating indicators
                loading = driver.find_elements(By.XPATH, "//*[contains(@class, 'loading') or contains(@class, 'spinner') or contains(@class, 'generating')]")
                if loading:
                    print(" (loading indicator visible)", end="", flush=True)
        except:
            pass

        time.sleep(1)

    # Timeout - provide debug info
    print(f"\n    ⚠ Timeout after {timeout}s")
    print("    🔍 Debug info:")

    try:
        # Check what buttons exist
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        button_texts = [b.text for b in buttons if b.text.strip()]
        print(f"      • Available buttons: {button_texts}")

        # Check for download button specifically
        download_btns = [b for b in buttons if 'download' in b.text.lower()]
        print(f"      • Download buttons found: {len(download_btns)}")

        # Check images
        imgs = driver.find_elements(By.TAG_NAME, 'img')
        print(f"      • Total images on page: {len(imgs)}")

        # Check for error text
        body_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        if 'error' in body_text:
            print("      ⚠ Page contains 'error' text")
        if 'limit' in body_text or 'quota' in body_text:
            print("      ⚠ Possible rate limit or quota issue")

    except Exception as e:
        print(f"      ✗ Error getting debug info: {e}")

    return None

def download_image(driver, save_path, timeout=10):
    """Download the generated image (better quality than screenshot)"""
    print("  → Downloading image...")

    try:
        # Method 1: Look for download button
        print("    Looking for download button...")
        buttons = driver.find_elements(By.TAG_NAME, 'button')

        download_btn = None
        for btn in buttons:
            # Check button text
            text = btn.text.lower()
            if 'download' in text or 'save' in text:
                download_btn = btn
                break

            # Check aria-label
            aria = btn.get_attribute('aria-label') or ''
            if 'download' in aria.lower():
                download_btn = btn
                break

        if download_btn:
            print("    ✓ Found download button, clicking...")
            download_btn.click()
            time.sleep(3)

            # Check Downloads folder for new file
            downloads_folder = Path.home() / 'Downloads'

            # Get most recent image files
            image_files = []
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
                image_files.extend(downloads_folder.glob(ext))

            # Sort by modification time
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Check most recent files
            for file in image_files[:5]:
                age = time.time() - file.stat().st_mtime
                if age < 15:  # Modified in last 15 seconds
                    print(f"    ✓ Found downloaded file: {file.name}")
                    # Move to proper location
                    import shutil
                    shutil.move(str(file), str(save_path))
                    print(f"    ✓ Moved to: {save_path}")
                    return True

        # Method 2: Right-click on image and use context menu
        print("    Trying right-click method...")
        imgs = driver.find_elements(By.TAG_NAME, 'img')
        for img in imgs:
            src = img.get_attribute('src') or ''
            if 'blob:' in src:
                print("    ✓ Found blob image")

                # Right-click on image
                actions = ActionChains(driver)
                actions.context_click(img).perform()
                time.sleep(1)

                # Try to trigger "Save image as"
                # This is tricky because it opens OS dialog
                # Fall through to screenshot method
                break

        # Method 3: Fallback to screenshot
        print("    Falling back to screenshot...")
        for img in imgs:
            src = img.get_attribute('src') or ''
            if 'blob:' in src:
                img.screenshot(str(save_path))
                if save_path.exists() and save_path.stat().st_size > 10000:
                    print(f"    ✓ Screenshot saved (fallback method)")
                    return True

        print("    ✗ All download methods failed")
        return False

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False

def generate_one_item(driver, item):
    """Generate a single item"""
    name = item['name']
    subfolder = item['subfolder']

    print(f"\n{'='*70}")
    print(f"Item: {name} → {subfolder}/")
    print(f"{'='*70}")

    # Check if exists
    save_dir = OUTPUT_DIR / subfolder
    save_path = save_dir / f"{name}.png"

    if save_path.exists() and save_path.stat().st_size > 10000:
        print("  ✓ Already exists, skipping")
        return True, True

    try:
        # Wait a moment for page to be ready
        time.sleep(1)

        # Find all textareas
        print("  → Finding textareas...")
        textareas = driver.find_elements(By.TAG_NAME, 'textarea')

        if len(textareas) < 2:
            print(f"  ✗ Only found {len(textareas)} textareas")
            return False, False

        print(f"  ✓ Found {len(textareas)} textareas")

        # Use first 2 textareas
        textarea1 = textareas[0]
        textarea2 = textareas[1]

        # Fill prompt 1
        print("  → Filling persistent prompt...")
        fill_textarea(textarea1, PERSISTENT_PROMPT)

        # Fill prompt 2
        print("  → Filling detail prompt...")
        detail_prompt = build_detail_prompt(item)
        fill_textarea(textarea2, detail_prompt)

        # Find Generate button
        print("  → Finding Generate button...")
        generate_btn = None

        buttons = driver.find_elements(By.TAG_NAME, 'button')
        for btn in buttons:
            text = btn.text.lower()
            if 'generate' in text:
                generate_btn = btn
                print(f"    Found button with text: '{btn.text}'")
                break

        if not generate_btn:
            print("  ✗ Generate button not found")
            print(f"    Available buttons: {[b.text for b in buttons if b.text]}")
            return False, False

        # Debug mode: pause before clicking
        if DEBUG_MODE:
            print("  🐛 DEBUG MODE: Check if prompts are filled correctly")
            input("    Press Enter to click Generate...")

        print("  ✓ Clicking Generate...")
        generate_btn.click()
        time.sleep(2)

        # Check for any error messages
        try:
            error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'error') or contains(text(), 'Error')]")
            if error_elements:
                print(f"    ⚠ Possible errors on page: {[e.text for e in error_elements[:3]]}")
        except:
            pass

        # Wait for image
        image_element = wait_for_image(driver, GENERATION_WAIT)

        if not image_element:
            print("  ✗ Image did not generate")
            return False, False

        # Download/save the image
        save_dir.mkdir(parents=True, exist_ok=True)

        if download_image(driver, save_path):
            print(f"  ✓ SUCCESS: Saved to {save_path.relative_to(SCRIPT_DIR)}")
            return True, False
        else:
            print("  ✗ Failed to save image")
            return False, False

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, False

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*70)
    print("VHEER AUTOMATION - SIMPLE VERSION")
    print("="*70)

    print(f"\n📁 Script location: {SCRIPT_DIR}")
    print(f"💾 Images will be saved to: {OUTPUT_DIR}")
    print(f"   (This folder will be created next to the script)")

    # Choose mode
    print("\nMode:")
    print("  [1] Test (2 items)")
    print("  [2] Full catalog (all items)")

    choice = input("\nChoice (1 or 2): ").strip()

    if choice == '2':
        if not CATALOG_PATH.exists():
            print(f"\n⚠ Catalog not found: {CATALOG_PATH}")
            print("Using test mode instead...")
            items = TEST_ITEMS
        else:
            print("\nLoading catalog...")
            items = parse_catalog(CATALOG_PATH)
            print(f"✓ Loaded {len(items)} items")
    else:
        items = TEST_ITEMS

    print(f"\nItems to generate: {len(items)}")
    print(f"Wait between items: {BETWEEN_ITEMS}s")
    print(f"Generation timeout: {GENERATION_WAIT}s")

    if DEBUG_MODE:
        print("\n🐛 DEBUG MODE ENABLED - Will pause before each Generate click")

    print("\n💡 TIP: If generation keeps timing out:")
    print("   - Check if Vheer has rate limits")
    print("   - Try waiting longer between items")
    print("   - Set DEBUG_MODE = True in the script to debug")

    print("\n" + "="*70)
    input("Press Enter to start...")

    driver = setup_driver()

    try:
        print("\n🌐 Opening Vheer...")
        driver.get("https://vheer.com/app/game-assets-generator")

        print("⏳ Waiting for page to load...")
        time.sleep(8)
        print("✓ Page ready\n")

        # Process items
        success = 0
        failed = 0
        skipped = 0
        failed_list = []

        for i, item in enumerate(items, 1):
            print(f"\n[{i}/{len(items)}]")

            ok, skip = generate_one_item(driver, item)

            if skip:
                skipped += 1
            elif ok:
                success += 1
            else:
                failed += 1
                failed_list.append(item['name'])

            print(f"\nTotals: ✓{success}  ✗{failed}  ⊘{skipped}")

            # Wait before next (except last)
            if i < len(items) and not skip:
                print(f"⏱ Waiting {BETWEEN_ITEMS}s...")
                time.sleep(BETWEEN_ITEMS)

        # Final summary
        print("\n" + "="*70)
        print("COMPLETE!")
        print("="*70)
        print(f"✓ Success: {success}")
        print(f"✗ Failed: {failed}")
        print(f"⊘ Skipped: {skipped}")

        if success > 0:
            print(f"\n📁 Images saved to: {OUTPUT_DIR.absolute()}")
            print(f"   Check the folder structure:")
            print(f"   {OUTPUT_DIR.name}/")
            print(f"     weapons/")
            print(f"     consumables/")
            print(f"     materials/")
            print(f"     etc...")

        if failed_list:
            print(f"\n⚠ Failed items:")
            for name in failed_list:
                print(f"  - {name}")

        print("="*70)

        input("\nPress Enter to close browser...")

    except KeyboardInterrupt:
        print("\n\n⏸ Interrupted by user")

    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()
        print("✓ Browser closed")

if __name__ == "__main__":
    main()