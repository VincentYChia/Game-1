"""
Vheer AI Game Assets Generator Automation Script
Automates icon generation for 165+ game items with resume capability

Requirements:
- pip install selenium webdriver-manager pyperclip
- Chrome browser installed
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import os
import pyperclip

# Configuration
DOWNLOAD_FOLDER = r"C:\Users\vipVi\Downloads\Game-1-icons"
PERSISTENT_PROMPT = "Simple cel-shaded 3d stylized fantasy exploration item icons. Clean render, distinct details, transparent background."
WAIT_MIN = 20  # Minimum seconds between generations
WAIT_MAX = 35  # Maximum seconds between generations
GENERATION_WAIT = 20  # Seconds to wait for image generation to complete

# Game items catalog
ITEMS = [
    # EQUIPMENT - WEAPONS
    {
        "name": "iron_shortsword",
        "category": "equipment",
        "type": "weapon",
        "subtype": "shortsword",
        "narrative": "A simple iron blade with a wooden handle. Every warrior's first step on the path to mastery. The weight feels right in your hand - not perfect, but yours."
    },
    {
        "name": "copper_spear",
        "category": "equipment",
        "type": "weapon",
        "subtype": "spear",
        "narrative": "Simple copper-tipped spear with ash wood shaft. The extra reach keeps danger at arm's length. Perfect for those who prefer distance over direct confrontation."
    },
    {
        "name": "steel_longsword",
        "category": "equipment",
        "type": "weapon",
        "subtype": "longsword",
        "narrative": "Balanced steel longsword that flows like water and strikes like thunder. The blade sings when it cuts through air, a testament to its quality."
    },
    {
        "name": "steel_battleaxe",
        "category": "equipment",
        "type": "axe",
        "subtype": "battleaxe",
        "narrative": "Steel battleaxe with brutal cleaving power. Grip it with both hands and watch enemies fall like timber. Equally deadly in one hand for those strong enough to wield it."
    },
    {
        "name": "iron_warhammer",
        "category": "equipment",
        "type": "mace",
        "subtype": "warhammer",
        "narrative": "Heavy iron warhammer that crushes armor and bone alike. The weight demands both hands, but the devastation it delivers makes that trade worthwhile. Favored by those who prefer decisive, crushing blows."
    },
    {
        "name": "copper_dagger",
        "category": "equipment",
        "type": "dagger",
        "subtype": "dagger",
        "narrative": "Simple copper dagger, light and quick. Not much reach, but what it lacks in power it makes up for in speed. Perfect for those who value precision over brute force."
    },
    {
        "name": "composite_longbow",
        "category": "equipment",
        "type": "bow",
        "subtype": "longbow",
        "narrative": "Composite longbow of ash wood and sinew, strung with silk-spider thread. The draw is heavy, demanding both hands and steady arms, but arrows fly true and far. Distance is your advantage."
    },
    {
        "name": "fire_crystal_staff",
        "category": "equipment",
        "type": "staff",
        "subtype": "staff",
        "narrative": "Ironwood staff capped with a pulsing fire crystal. The wood never burns, the crystal never dims. Channel elemental forces through this focus, or wield it as a quarterstaff when enemies close distance."
    },
    {
        "name": "iron_round_shield",
        "category": "equipment",
        "type": "shield",
        "subtype": "buckler",
        "narrative": "Round iron shield with oak backing. Not just for blocking - bash enemies with the rim or use it to create openings. Defense and offense in one hand."
    },
    {
        "name": "mithril_dagger",
        "category": "equipment",
        "type": "weapon",
        "subtype": "dagger",
        "narrative": "Mithril dagger that seems to shimmer out of existence. Wickedly sharp and impossibly light, it strikes faster than the eye can follow. The blade whispers through air and flesh alike."
    },
    {
        "name": "pine_shortbow",
        "category": "equipment",
        "type": "weapon",
        "subtype": "shortbow",
        "narrative": "Simple pine shortbow strung with treated slime gel. Not powerful, but reliable and easy to maintain. Perfect for learning the basics of archery."
    },
    # EQUIPMENT - ARMOR
    {
        "name": "leather_tunic",
        "category": "equipment",
        "type": "armor",
        "subtype": "tunic",
        "narrative": "Basic leather protection stitched from wolf pelts and bound with slime gel. Better than nothing, lighter than metal, and it might just save your life."
    },
    {
        "name": "iron_boots",
        "category": "equipment",
        "type": "armor",
        "subtype": "boots",
        "narrative": "Reinforced leather boots with iron caps. Protects your feet without slowing you down. Essential for anyone who values both mobility and survival."
    },
    {
        "name": "iron_chestplate",
        "category": "equipment",
        "type": "armor",
        "subtype": "chestplate",
        "narrative": "Iron plates protecting vital organs with beetle carapace reinforcement. Heavy but reliable. When arrows fly and blades swing, you'll appreciate every ounce of protection."
    },
    {
        "name": "steel_helm",
        "category": "equipment",
        "type": "armor",
        "subtype": "helmet",
        "narrative": "Steel helm with full face protection and wolf pelt padding. Your head stays attached, which is nice. The padding reduces the ringing when you take a hit."
    },
    {
        "name": "steel_leggings",
        "category": "equipment",
        "type": "armor",
        "subtype": "leggings",
        "narrative": "Steel plate leggings with articulated joints. Heavy but protective, they guard your legs without restricting movement. Every smith's second major armor piece after the chestplate."
    },
    {
        "name": "iron_studded_gauntlets",
        "category": "equipment",
        "type": "armor",
        "subtype": "gauntlets",
        "narrative": "Leather gloves reinforced with iron studs across the knuckles. Light enough for dexterity, strong enough to turn a blade. Your hands are tools - protect them."
    },
    # Add remaining items here... (truncated for space, but you'll include all 165+)
]


def setup_driver():
    """Set up Chrome driver with download preferences"""
    chrome_options = Options()

    # Set download preferences
    prefs = {
        "download.default_directory": DOWNLOAD_FOLDER,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    # Create download folder if it doesn't exist
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def file_exists(item_name):
    """Check if file already exists (try both png and jpg)"""
    png_path = os.path.join(DOWNLOAD_FOLDER, f"{item_name}.png")
    jpg_path = os.path.join(DOWNLOAD_FOLDER, f"{item_name}.jpg")
    jpeg_path = os.path.join(DOWNLOAD_FOLDER, f"{item_name}.jpeg")

    if os.path.exists(png_path) or os.path.exists(jpg_path) or os.path.exists(jpeg_path):
        return True
    return False


def build_detail_prompt(item):
    """Build the detail prompt from item data"""
    return f"""Generate an icon image off of the item description:
Category: {item['category']}
Type: {item['type']}
Subtype: {item['subtype']}
Narrative: {item['narrative']}"""


def generate_item(driver, item):
    """Generate a single item icon"""
    try:
        item_name = item['name']

        # Check if file already exists
        if file_exists(item_name):
            print(f"✓ {item_name} already exists, skipping...")
            return True

        print(f"\nGenerating: {item_name}")

        # Find the Game Assets Type textarea
        type_textarea = driver.find_element(By.XPATH,
                                            "//textarea[contains(@placeholder, 'Game Assets Type') or preceding-sibling::div[contains(text(), 'Game Assets Type')]]")
        type_textarea.clear()
        time.sleep(0.5)
        type_textarea.send_keys(PERSISTENT_PROMPT)
        print("  → Entered persistent prompt")

        # Find the Game Assets Detail textarea
        detail_textarea = driver.find_element(By.XPATH,
                                              "//textarea[contains(@placeholder, 'Game Assets Detail') or preceding-sibling::div[contains(text(), 'Game Assets Detail')]]")
        detail_textarea.clear()
        time.sleep(0.5)
        detail_prompt = build_detail_prompt(item)
        detail_textarea.send_keys(detail_prompt)
        print("  → Entered detail prompt")

        time.sleep(1)

        # Click Generate button
        generate_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Generate')]")
        generate_button.click()
        print(f"  → Clicked Generate, waiting {GENERATION_WAIT} seconds...")

        # Wait for generation
        time.sleep(GENERATION_WAIT)

        # Find the generated image
        image = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                                            "img[alt*='generated'], img[src*='blob:'], .preview-image img, div[class*='preview'] img"))
        )

        # Right-click on image
        actions = ActionChains(driver)
        actions.context_click(image).perform()
        time.sleep(1)

        # Send keyboard commands: Arrow Down (to "Save image as"), Enter
        actions = ActionChains(driver)
        actions.send_keys(Keys.ARROW_DOWN)  # Move to "Save image as"
        actions.send_keys(Keys.ARROW_DOWN)  # Might need multiple downs depending on context menu
        time.sleep(0.5)
        actions.send_keys(Keys.RETURN)  # Press Enter
        actions.perform()

        time.sleep(2)

        # Handle Save As dialog using pyperclip and keyboard
        # Copy filename to clipboard
        file_path = os.path.join(DOWNLOAD_FOLDER, f"{item_name}.png")
        pyperclip.copy(file_path)

        # Paste filename (Ctrl+V) and save (Enter)
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(1)
        actions.send_keys(Keys.RETURN).perform()

        print(f"  ✓ Saved as {item_name}.png")

        return True

    except Exception as e:
        print(f"  ✗ Error generating {item.get('name', 'unknown')}: {e}")
        return False


def main():
    """Main function to run the automation"""
    print("=" * 70)
    print("VHEER AI GAME ASSETS GENERATOR - AUTOMATION SCRIPT")
    print("=" * 70)
    print(f"\nTotal items to process: {len(ITEMS)}")
    print(f"Download folder: {DOWNLOAD_FOLDER}")
    print(f"Wait time between generations: {WAIT_MIN}-{WAIT_MAX} seconds")
    print("\nChecking for existing files...\n")

    # Count existing files
    existing_count = sum(1 for item in ITEMS if file_exists(item['name']))
    remaining = len(ITEMS) - existing_count

    print(f"Existing files: {existing_count}")
    print(f"Remaining to generate: {remaining}\n")

    if remaining == 0:
        print("All items already generated! Exiting.")
        return

    input("Press Enter to start automation (make sure browser is ready)...")

    driver = setup_driver()

    try:
        # Navigate to Vheer Game Assets Generator
        print("\nNavigating to Vheer Game Assets Generator...")
        driver.get("https://vheer.com/app/game-assets-generator")

        # Wait for page to load
        time.sleep(5)
        print("Page loaded!\n")

        # Process each item
        successful = 0
        failed = 0
        skipped = 0

        for i, item in enumerate(ITEMS, 1):
            print(f"\n{'=' * 70}")
            print(f"Item {i}/{len(ITEMS)}: {item['name']}")
            print(f"{'=' * 70}")

            if file_exists(item['name']):
                skipped += 1
                continue

            success = generate_item(driver, item)

            if success:
                successful += 1
            else:
                failed += 1

            # Wait random time before next generation (except for last item)
            if i < len(ITEMS):
                wait_time = random.randint(WAIT_MIN, WAIT_MAX)
                print(f"\nWaiting {wait_time} seconds before next generation...")
                time.sleep(wait_time)

        # Final summary
        print("\n" + "=" * 70)
        print("GENERATION COMPLETE!")
        print("=" * 70)
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Skipped (already existed): {skipped}")
        print(f"Total: {len(ITEMS)}")
        print("=" * 70)

        input("\nPress Enter to close browser...")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Progress has been saved.")
        print("Run script again to resume from where you left off.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Progress has been saved. Run script again to resume.")

    finally:
        driver.quit()
        print("\nBrowser closed. Script finished.")


if __name__ == "__main__":
    main()