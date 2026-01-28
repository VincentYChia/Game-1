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
import ast


# ============================================================================
# CONFIGURATION LOADING FROM FILE
# ============================================================================

def parse_configurations_file(filepath):
    """Parse configurations.txt to extract all configuration sets.

    Returns:
        Dict mapping config number -> {
            'PERSISTENT_PROMPT': str,
            'VERSION_PROMPTS': dict,
            'TYPE_ADDITIONS': dict,
            'CATEGORY_ADDITIONS': dict (optional)
        }
    """
    configs = {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"  ⚠ Configuration file not found: {filepath}")
        return configs

    # Split by configuration headers
    # Match both commented and uncommented configuration blocks
    # Handle various comment styles: no comment, single #, or double # #
    config_pattern = r'(?:#\s*#?\s*)?=+\s*\n(?:#\s*#?\s*)?CONFIGURATION\s+(\d+)\s*\n(?:#\s*#?\s*)?=+'

    # Find all configuration markers
    markers = list(re.finditer(config_pattern, content))

    for i, marker in enumerate(markers):
        config_num = int(marker.group(1))
        start = marker.end()

        # End is either next marker or end of file
        end = markers[i + 1].start() if i + 1 < len(markers) else len(content)

        config_block = content[start:end]

        # Check if this block is commented out (majority of lines start with #)
        lines = config_block.strip().split('\n')
        commented_lines = sum(1 for line in lines if line.strip().startswith('#'))
        is_commented = commented_lines > len(lines) * 0.5

        # If commented, uncomment the block for parsing
        if is_commented:
            config_block = '\n'.join(
                line[1:].lstrip() if line.strip().startswith('#') else line
                for line in lines
            )

        # Extract PERSISTENT_PROMPT
        persistent_match = re.search(
            r'PERSISTENT_PROMPT\s*=\s*\(?\s*(["\'].*?["\'])\s*\)?(?:\n|$)',
            config_block,
            re.DOTALL
        )
        if not persistent_match:
            # Try multiline format
            persistent_match = re.search(
                r'PERSISTENT_PROMPT\s*=\s*\(\s*\n?((?:["\'].*?["\'][\s\n]*)+)\)',
                config_block,
                re.DOTALL
            )

        persistent_prompt = ""
        if persistent_match:
            try:
                # Clean up and evaluate the string
                prompt_str = persistent_match.group(1).strip()
                # Handle multi-line string concatenation
                persistent_prompt = eval(prompt_str)
            except:
                persistent_prompt = persistent_match.group(1).strip().strip('"\'')

        # Extract VERSION_PROMPTS dict
        version_prompts = {}
        vp_match = re.search(
            r'VERSION_PROMPTS\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            config_block,
            re.DOTALL
        )
        if vp_match:
            try:
                vp_content = '{' + vp_match.group(1) + '}'
                version_prompts = ast.literal_eval(vp_content)
            except:
                # Parse manually
                vp_block = vp_match.group(1)
                for vm in re.finditer(r'(\d+)\s*:\s*(["\'].*?["\'])\s*,?', vp_block, re.DOTALL):
                    try:
                        version_prompts[int(vm.group(1))] = eval(vm.group(2))
                    except:
                        pass

        # Extract TYPE_ADDITIONS dict
        type_additions = {}
        ta_match = re.search(
            r'TYPE_ADDITIONS\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            config_block,
            re.DOTALL
        )
        if ta_match:
            try:
                ta_content = '{' + ta_match.group(1) + '}'
                type_additions = ast.literal_eval(ta_content)
            except:
                # Parse manually - key: 'value' pairs
                ta_block = ta_match.group(1)
                for tm in re.finditer(r"['\"](\w+)['\"]\s*:\s*(['\"].*?['\"])\s*[,}]", ta_block, re.DOTALL):
                    try:
                        type_additions[tm.group(1)] = eval(tm.group(2))
                    except:
                        pass

        # Extract CATEGORY_ADDITIONS dict (if present)
        category_additions = {}
        ca_match = re.search(
            r'CATEGORY_ADDITIONS\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            config_block,
            re.DOTALL
        )
        if ca_match:
            try:
                ca_content = '{' + ca_match.group(1) + '}'
                category_additions = ast.literal_eval(ca_content)
            except:
                pass

        configs[config_num] = {
            'PERSISTENT_PROMPT': persistent_prompt,
            'VERSION_PROMPTS': version_prompts,
            'TYPE_ADDITIONS': type_additions,
            'CATEGORY_ADDITIONS': category_additions,
            'is_commented': is_commented
        }

        print(f"  ✓ Loaded Configuration {config_num}: "
              f"{len(version_prompts)} version prompts, "
              f"{len(type_additions)} type additions"
              f"{' (was commented)' if is_commented else ''}")

    return configs


def load_configuration(config_num, configs_dict):
    """Load a specific configuration into the global variables.

    Args:
        config_num: Configuration number to load
        configs_dict: Dict from parse_configurations_file()

    Returns:
        True if loaded successfully, False otherwise
    """
    global PERSISTENT_PROMPT, VERSION_PROMPTS, TYPE_ADDITIONS, CATEGORY_ADDITIONS

    if config_num not in configs_dict:
        print(f"  ⚠ Configuration {config_num} not found, using defaults")
        return False

    config = configs_dict[config_num]

    if config['PERSISTENT_PROMPT']:
        PERSISTENT_PROMPT = config['PERSISTENT_PROMPT']

    if config['VERSION_PROMPTS']:
        VERSION_PROMPTS.update(config['VERSION_PROMPTS'])

    if config['TYPE_ADDITIONS']:
        TYPE_ADDITIONS.update(config['TYPE_ADDITIONS'])

    if config.get('CATEGORY_ADDITIONS'):
        CATEGORY_ADDITIONS.update(config['CATEGORY_ADDITIONS'])

    print(f"  ✓ Applied Configuration {config_num}")
    return True


# Path to configurations file
CONFIGURATIONS_FILE = Path(__file__).parent / 'configurations.txt'

# Default configurations (used if file not found)
PERSISTENT_PROMPT = ""

# Version-specific prompts
VERSION_PROMPTS = {
    1: "3D rendered item icon in bold illustrative fantasy style. CRITICAL: Items must be visually distinct from similar items through form, proportion, and design language. Item fills 70-80% of frame at dynamic angle. Materials must be clearly represented through texture, sheen, and visual effects. Gradient background, dramatic three-point lighting with colored rim lights, soft ground shadow. Emphasize archetypal fantasy design with enhanced brightness and saturation.",

    2: "3D rendered item icon in bold illustrative fantasy style. VERIFY item type completely before generating - distinguish axes from pickaxes, ores from ingots, nodes from processed materials. Form and function must be immediately recognizable. Materials MUST show distinct visual properties (metallic sheen, texture, color temperature, magical effects). Item 70-80% frame coverage, compelling diagonal angle. Gradient background, dramatic lighting with material-appropriate highlights. Push visual distinction aggressively.",

    3: "3D rendered item icon in bold illustrative fantasy style with MAXIMUM DISTINCTION. Read full description and verify: tool function (mining/chopping/combat), item state (raw node/ore/ingot/crafted), material properties. Each item category needs unique silhouette and design language. Materials must be exaggerated for clarity: copper=warm orange, steel=cool blue-grey, iron=neutral grey, wood types with signature effects. Reject realistic ambiguity - embrace fantasy symbolism. 70-80% coverage, dynamic angle, dramatic gradient background, bold three-point lighting with colored accents.",

    4: "HYPER-STYLIZED 3D fantasy icon with EXTREME visual clarity. Priority: INSTANT RECOGNITION at thumbnail size. Exaggerate defining features 150%. Tools vs weapons must have completely different design languages. Raw materials vs processed must be unmistakable. Color-code aggressively: copper=orange glow, iron=grey steel, mithril=silver-blue shimmer, gold=warm radiance. Bold outlines, saturated colors, clean silhouettes. 75% frame coverage, hero angle, vibrant gradient background.",

    5: "ULTIMATE CLARITY 3D fantasy icon. Design philosophy: If you can't identify it at 32x32 pixels, it fails. Maximum silhouette distinction. Iconic symbolic design over realistic detail. Each material type gets signature visual effect (glow, shimmer, texture pattern). Tool heads dramatically different from weapon heads. Environmental nodes clearly show 'harvestable in ground' vs 'inventory item'. Push stylization to the limit while maintaining fantasy aesthetic. Bold colors, clean edges, dramatic lighting.",
}

# Category-specific additions
CATEGORY_ADDITIONS = {
    'enemy': 'Stylized creature design with bold silhouette. Emphasize character and threat level through form, not gore. Clear visual storytelling.',

    'resource': 'This is a RESOURCE NODE (in-ground deposit, tree, quarry vein) NOT the harvested material. Show the source in natural context - rock formations, tree bark, ore veins in stone matrix. Must be clearly a gatherable environmental object, not a processed item.',

    'title': 'Symbolic emblem representing achievement concept. Use heraldic/medallion design language - shields, crests, symbolic icons, decorative frames. NOT literal illustrations. Think coat of arms meeting fantasy badge.',

    'skill': 'Abstract symbolic icon representing the skill concept through visual metaphor. Use bold graphic design language - geometric shapes, energy effects, elemental symbols, mystical sigils. Prioritize instant recognition over literal representation. Reference ability scroll/tome aesthetic.',

    'station': 'Crafting station with clear tier progression. Tier 1: Simple, rustic, basic materials. Tier 2: Refined, metal reinforcements, modest detail. Tier 3: Advanced, complex mechanisms, magical accents. Tier 4: Masterwork, intricate detail, glowing runes, premium materials. Each tier should be visually distinct at thumbnail size.',

    'device': 'Functional fantasy device. Type determines form factor - distinguish turrets, traps, gadgets clearly. Show purpose through design. Adhere to type as primary design driver.',

    'material': 'Processed material icon - ingots, refined components, drops. HIGHLY SYMBOLIC representation. Ingots = stylized bars with material signature (copper glow, steel sheen). Drops = crystallized essence with thematic effects. Prioritize instant material recognition over realism.',

    'consumable': 'Container design tells the story. Bottle/vial shape, liquid color, AND container details indicate effect. Health = round flask, red liquid, warm glow. Mana = elegant vial, blue liquid, mystical sparkles. Buff = geometric bottle with effect-colored liquid and atmospheric effects. Make containers creative and distinct.',

    'equipment': 'Equipment items must show material properties clearly. Metal type affects color temperature, sheen, and edge highlights. Copper = warm orange-gold. Iron = neutral grey. Steel = cool blue-grey. Bronze = rich amber. Ensure material is unmistakable.',
}

# Type-specific additions
TYPE_ADDITIONS = {
    # TOOLS - Critical distinction from weapons
    'tool': 'TOOL not weapon. Tools have utilitarian design - reinforced heads, practical grip wrapping, wear marks from use. Less elegant than weapons, more robust construction.',

    'axe': 'WOODCUTTING AXE. Wide, straight-edged blade optimized for chopping wood. Thick spine, broad cutting surface. Utilitarian handle with practical grip. NOT a battle axe - no spikes, curves, or aggressive styling.',

    'pickaxe': 'MINING PICKAXE. Distinctive pointed pick on one side, flat chisel on other (or dual picks). Narrow profile, long reach design. Reinforced shaft. Head angled for breaking rock. COMPLETELY different silhouette from axe - emphasize the pointed pick shape.',

    'hatchet': 'Small one-handed forestry hatchet. Compact axe head, short handle. Clearly smaller and lighter than full axe.',

    # WEAPONS - Aggressive elegant design
    'weapon': 'Combat weapon with elegant, aggressive design. Sharp lines, balanced proportions, decorative elements. Designed to look deadly and prestigious.',

    'battleaxe': 'COMBAT AXE. Curved aggressive blade, often asymmetric or double-headed. Sharp edges, intimidating design. Decorative elements, balanced for fighting. More elegant and deadly than tool axe.',

    'sword': 'Sword with clear blade profile. Material affects color, sheen, and edge glow.',

    'bow': 'Elegant bow with VISIBLE STRING. String must be rendered as fine line connecting limb tips, slightly curved under tension. If string is hard to see, add subtle glow or highlights. Emphasize recurve or longbow shape clearly.',

    'staff': 'Magical or combat staff. Ornate head design with crystals, orbs, or elemental effects. Carved shaft with runes or wrappings.',

    'dagger': 'Short blade, often curved or dual-edged. Distinct from sword by size and proportion. Emphasize compact lethality.',

    'spear': 'Long shaft with pointed head. Clear spearhead design - leaf-shaped, barbed, or angular. Shaft details like wrapping or metal bands.',

    'mace': 'Blunt weapon with distinctive head - spiked ball, flanged cylinder, or geometric shape. Heavy, intimidating appearance.',

    # MATERIALS
    'ingot': 'Stylized metal bar with beveled edges. Material signature is CRITICAL: Copper = warm orange-amber glow. Iron = neutral grey with subtle shine. Steel = cool blue-grey with high sheen. Gold = rich yellow with warm highlights. Bronze = deep amber-orange. Silver = bright white-grey with sharp highlights. Show material through color temperature and reflectivity.',

    'ore': 'Unrefined ore chunk - rough crystalline rock. Material shows as veins, crystals, or deposits in host stone. Copper ore = green malachite crystals. Iron ore = reddish-brown hematite. Gold ore = bright yellow veins in quartz. Emphasize raw, unprocessed state with natural crystal formations.',

    'wood': 'Processed lumber or wood resource. Different wood types need signature visual effects: Oak = rich brown, solid grain. Pine = lighter tan, visible knots. Ironwood = grey with metallic vein patterns. Ebony = deep black with subtle purple sheen. Crimson = red tinted with flame-like grain. Make wood types immediately distinguishable through color, effects, and character.',

    'node': 'Resource node - environmental deposit. Add terms: QUARRY for stone deposits, VEIN for ore deposits, TREE for wood sources. Show in natural environmental context - mineral vein in rock face, quarry stone formation, standing tree bark. Must be clearly different from refined materials.',

    # SPECIFIC ITEMS
    'potion': 'Fantasy potion in distinctive container. Round flask, decorative bottle, or vial. Liquid color indicates type. Container itself should have character - cork stopper, wax seal, etched glass, glowing effects.',

    'forge': 'Forge station with CLEAR tier progression: Tier 1 = simple stone hearth, basic bellows, primitive anvil. Tier 2 = brick forge, metal bellows, proper anvil, coal pile. Tier 3 = reinforced forge with chimney, mechanical bellows, tool racks, mystical accents. Tier 4 = masterwork forge with intricate metalwork, glowing runes, ethereal flames, magical anvil, premium materials throughout. Each tier must be dramatically more impressive.',

    'turret': 'Defensive turret with clear base. Mounted weapon system on stable platform. Show firing mechanism, ammunition, and sturdy foundation.',
}



SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / 'generated_icons'
CATALOG_PATH = SCRIPT_DIR / 'icons' / 'ITEM_CATALOG_FOR_ICONS.md'

GENERATION_TIMEOUT = 180
WAIT_BETWEEN_ITEMS = 25
VERSIONS_TO_GENERATE = 3

# Custom configuration range settings (used by mode 3)
CUSTOM_VERSION_START = 2  # Start from version 2
CUSTOM_VERSION_END = 5    # End at version 5
CUSTOM_OUTPUT_CYCLE = None  # Set to cycle number (e.g., 2) to output to icons-generated-cycle-2/

# Test items for quick validation (mode 1)
TEST_ITEMS = [
    {
        'name': 'iron_sword',
        'category': 'equipment',
        'type': 'sword',
        'subtype': 'sword',
        'narrative': 'A basic iron sword with a straight double-edged blade.',
        'base_folder': 'items',
        'subfolder': 'weapons'
    },
    {
        'name': 'copper_pickaxe',
        'category': 'equipment',
        'type': 'pickaxe',
        'subtype': 'tool',
        'narrative': 'A copper mining pickaxe with dual pointed heads for breaking rock.',
        'base_folder': 'items',
        'subfolder': 'tools'
    },
]

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

    if category == 'class':
        return ('classes', None)

    if category == 'quest':
        return ('quests', None)

    if category == 'npc':
        return ('npcs', None)

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

        # Always include the item
        item_data.setdefault('narrative', '')
        item_data.setdefault('category', 'misc')
        item_data.setdefault('type', 'unknown')
        item_data.setdefault('subtype', item_data['type'])

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


def pre_scan_directories_custom(items, version_start, version_end, cycle=None):
    """Scan output directories with custom version range and cycle support"""
    print("\n" + "="*70)
    print("PRE-SCAN: Checking existing files")
    print("="*70)

    MIN_FILE_SIZE = 5000

    all_version_stats = []

    for version in range(version_start, version_end + 1):
        output_base = get_output_base_for_version(version, cycle)

        existing_files = []
        missing_items = []

        for item in items:
            name = item['name']
            base_folder = item.get('base_folder', 'items')
            subfolder = item.get('subfolder')

            # Always use versioned filename for custom mode (or version 1 without cycle)
            if version == 1 and cycle is None:
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
            'missing_items': missing_items,
            'output_base': output_base
        })

        print(f"\nVersion {version}: {existing_count}/{total_count} existing, {missing_count} missing")
        print(f"  Output: {output_base.relative_to(SCRIPT_DIR)}")

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

def generate_item(driver, item, version=1, cycle=None):
    """Generate one item icon

    Args:
        driver: Selenium webdriver
        item: Item dict with name, category, type, etc.
        version: Version number (1-5) for prompt selection
        cycle: Optional cycle number for output to icons-generated-cycle-N/
    """
    name = item['name']
    base_folder = item.get('base_folder', 'items')
    subfolder = item.get('subfolder')

    # Use the shared output path logic
    output_base = get_output_base_for_version(version, cycle)

    if version == 1 and cycle is None:
        filename = f"{name}.png"
        version_label = ""
    else:
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

def get_output_base_for_version(version, cycle=None):
    """Get the output directory for a specific version and cycle.

    Args:
        version: The version number (1, 2, 3, etc.)
        cycle: Optional cycle number for icons-generated-cycle-N folders

    Returns:
        Path to output directory
    """
    if cycle is not None:
        # Output to icons-generated-cycle-N/generated_icons-V
        cycle_dir = SCRIPT_DIR / f'icons-generated-cycle-{cycle}'
        if version == 1:
            return cycle_dir / 'generated_icons'
        else:
            return cycle_dir / f'generated_icons-{version}'
    else:
        # Default behavior - output to generated_icons or generated_icons-V
        if version == 1:
            return OUTPUT_DIR
        else:
            return OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}-{version}"


def run_generation_for_cycle(items, version_start, version_end, output_cycle, configs_dict=None):
    """Run icon generation for a specific cycle with its configuration.

    Args:
        items: List of items to generate
        version_start: Starting version number
        version_end: Ending version number
        output_cycle: Cycle number for output directory
        configs_dict: Parsed configurations dict (if using file-based configs)

    Returns:
        Tuple of (success_count, failed_count, skipped_count, failed_items_list)
    """
    global PERSISTENT_PROMPT, VERSION_PROMPTS, TYPE_ADDITIONS

    # Load configuration for this cycle if available
    if configs_dict and output_cycle in configs_dict:
        print(f"\n📋 Loading Configuration {output_cycle} for Cycle {output_cycle}...")
        load_configuration(output_cycle, configs_dict)
    elif configs_dict:
        # Default to config 2 if no specific config for this cycle
        print(f"\n📋 No Configuration {output_cycle} found, using Configuration 2 as default...")
        if 2 in configs_dict:
            load_configuration(2, configs_dict)

    driver = setup_driver()
    total_success = 0
    total_failed = 0
    total_skipped = 0
    all_failed_items = []

    try:
        print("\n🌐 Opening Vheer...")
        if not safe_driver_get(driver, "https://vheer.com/app/game-assets-generator"):
            print("✗ Failed to open Vheer after multiple retries")
            driver.quit()
            return (0, len(items) * (version_end - version_start + 1), 0, [])

        time.sleep(16)
        driver.get("https://vheer.com/app/game-assets-generator")
        time.sleep(8)
        print("✓ Page loaded")

        select_cel_shaded_style(driver)
        print("✓ Ready\n")

        for version in range(version_start, version_end + 1):
            version_num = version - version_start + 1
            total_versions = version_end - version_start + 1

            print("\n" + "="*70)
            print(f"CYCLE {output_cycle} - GENERATING VERSION {version} ({version_num}/{total_versions})")
            print("="*70)

            output_folder = get_output_base_for_version(version, output_cycle)
            print(f"📁 Output: {output_folder}")

            success = 0
            failed = 0
            skipped = 0
            failed_list = []

            for i, item in enumerate(items, 1):
                print(f"\n[{i}/{len(items)}] Cycle {output_cycle} Version {version}")

                try:
                    ok, skip = generate_item(driver, item, version=version, cycle=output_cycle)

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
                            ok, skip = generate_item(driver, item, version=version, cycle=output_cycle)

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

                print(f"\nCycle {output_cycle} Version {version} Totals: ✓{success}  ✗{failed}  ⊘{skipped}")

                if i < len(items) and not skip:
                    print(f"⏱ Waiting {WAIT_BETWEEN_ITEMS}s...")
                    time.sleep(WAIT_BETWEEN_ITEMS)

            total_success += success
            total_failed += failed
            total_skipped += skipped
            if failed_list:
                all_failed_items.extend([(version, name) for name in failed_list])

            print(f"\n✓ Version {version} complete: {success} generated, {skipped} skipped, {failed} failed")

            if version < version_end:
                print(f"\n⏱ Waiting 30s before starting version {version + 1}...")
                time.sleep(30)

    except KeyboardInterrupt:
        print("\n\n⏸ Interrupted")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔒 Closing browser for this cycle...")
        driver.quit()
        time.sleep(3)

    return (total_success, total_failed, total_skipped, all_failed_items)


def main():
    global CUSTOM_VERSION_START, CUSTOM_VERSION_END, CUSTOM_OUTPUT_CYCLE

    print("="*70)
    print("VHEER AUTOMATION")
    print("="*70)

    print(f"\n📁 Script: {SCRIPT_DIR}")
    print(f"💾 Output: {OUTPUT_DIR}")

    # Check for configurations file
    configs_dict = None
    if CONFIGURATIONS_FILE.exists():
        print(f"\n📋 Loading configurations from: {CONFIGURATIONS_FILE.name}")
        configs_dict = parse_configurations_file(CONFIGURATIONS_FILE)
        if configs_dict:
            print(f"   Found {len(configs_dict)} configurations: {sorted(configs_dict.keys())}")
    else:
        print(f"\n⚠ No configurations.txt found, using built-in defaults")

    print("\nMode:")
    print("  [1] Test (2 items)")
    print("  [2] Full catalog")
    print("  [3] Custom configuration range (specify versions & cycle)")
    print("  [4] Auto-cycle (fill vacancies in all cycles with matching configs)")

    choice = input("\nChoice: ").strip()

    # Mode 4: Auto-cycle through all cycles with their configurations
    if choice == '4':
        print("\n" + "="*70)
        print("AUTO-CYCLE MODE")
        print("="*70)

        # Load catalog
        if not CATALOG_PATH.exists():
            print(f"\n⚠ Catalog not found: {CATALOG_PATH}")
            items = TEST_ITEMS
        else:
            print("\nLoading catalog...")
            items = parse_catalog(CATALOG_PATH)
            print(f"✓ Loaded {len(items)} items")

        # Scan all cycles to find vacancies
        print("\n" + "-"*50)
        print("SCANNING CYCLES FOR VACANCIES")
        print("-"*50)

        vacancies = {}  # cycle -> list of missing versions
        for cycle in range(1, 6):
            cycle_dir = SCRIPT_DIR / f'icons-generated-cycle-{cycle}'
            if cycle_dir.exists():
                missing_versions = []
                for ver in range(2, 5):  # Check versions 2, 3, 4 only (3 versions per cycle)
                    ver_dir = cycle_dir / f'generated_icons-{ver}'
                    if not ver_dir.exists():
                        missing_versions.append(ver)
                    else:
                        # Check if it has enough files (more than 10)
                        png_count = len(list(ver_dir.glob('**/*.png')))
                        if png_count < 10:
                            missing_versions.append(ver)
                            print(f"  Cycle {cycle} v{ver}: only {png_count} files (treating as vacancy)")

                if missing_versions:
                    vacancies[cycle] = missing_versions
                    print(f"  Cycle {cycle}: MISSING versions {missing_versions}")
                else:
                    print(f"  Cycle {cycle}: Complete (all versions present)")
            else:
                print(f"  Cycle {cycle}: Directory doesn't exist")

        if not vacancies:
            print("\n✓ All cycles complete! No vacancies found.")
            return

        # Show what will be generated
        print("\n" + "-"*50)
        print("GENERATION PLAN")
        print("-"*50)

        total_generations = 0
        for cycle, versions in sorted(vacancies.items()):
            config_num = cycle if cycle in (configs_dict or {}) else 2
            print(f"  Cycle {cycle}: Generate versions {versions} using Config {config_num}")
            total_generations += len(versions) * len(items)

        print(f"\nTotal: ~{total_generations} icon generations")
        print(f"Items per version: {len(items)}")

        # Confirm
        confirm = input("\nProceed with auto-cycle generation? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        # Run generation for each cycle
        grand_success = 0
        grand_failed = 0
        grand_skipped = 0
        all_failures = []

        for cycle, versions in sorted(vacancies.items()):
            version_start = min(versions)
            version_end = max(versions)

            print("\n" + "="*70)
            print(f"STARTING CYCLE {cycle}")
            print(f"Versions to generate: {versions}")
            print("="*70)

            success, failed, skipped, failures = run_generation_for_cycle(
                items,
                version_start=version_start,
                version_end=version_end,
                output_cycle=cycle,
                configs_dict=configs_dict
            )

            grand_success += success
            grand_failed += failed
            grand_skipped += skipped
            all_failures.extend([(cycle, v, n) for v, n in failures])

            print(f"\n✓ Cycle {cycle} complete: {success} success, {failed} failed, {skipped} skipped")

            # Wait between cycles
            remaining_cycles = [c for c in sorted(vacancies.keys()) if c > cycle]
            if remaining_cycles:
                print(f"\n⏱ Waiting 60s before starting Cycle {remaining_cycles[0]}...")
                print("  (This allows browser state to fully reset)")
                time.sleep(60)

        # Final summary
        print("\n" + "="*70)
        print("AUTO-CYCLE COMPLETE!")
        print("="*70)
        print(f"✓ Total Success: {grand_success}")
        print(f"✗ Total Failed: {grand_failed}")
        print(f"⊘ Total Skipped: {grand_skipped}")

        if all_failures:
            print(f"\n⚠ Failed items:")
            for cycle, version, name in all_failures[:20]:
                print(f"  - Cycle {cycle} v{version}: {name}")
            if len(all_failures) > 20:
                print(f"  ... and {len(all_failures) - 20} more")

        print("="*70)
        return

    # Determine version range based on mode
    version_start = 1
    version_end = VERSIONS_TO_GENERATE
    output_cycle = None

    if choice == '3':
        # Custom configuration mode
        print("\n" + "-"*50)
        print("CUSTOM CONFIGURATION")
        print("-"*50)

        # Get version range
        print(f"\nAvailable version prompts: 1-{len(VERSION_PROMPTS)}")
        version_input = input(f"Enter version range (e.g., '2-5' or '3'): ").strip()

        if '-' in version_input:
            try:
                start, end = version_input.split('-')
                version_start = int(start.strip())
                version_end = int(end.strip())
            except:
                print("  ⚠ Invalid range, using defaults")
                version_start = CUSTOM_VERSION_START
                version_end = CUSTOM_VERSION_END
        else:
            try:
                version_start = int(version_input)
                version_end = version_start
            except:
                print("  ⚠ Invalid input, using defaults")
                version_start = CUSTOM_VERSION_START
                version_end = CUSTOM_VERSION_END

        # Validate range
        version_start = max(1, min(version_start, len(VERSION_PROMPTS)))
        version_end = max(version_start, min(version_end, len(VERSION_PROMPTS)))

        print(f"  → Versions: {version_start} to {version_end}")

        # Get output cycle
        print("\nExisting cycle folders:")
        for i in range(1, 10):
            cycle_dir = SCRIPT_DIR / f'icons-generated-cycle-{i}'
            if cycle_dir.exists():
                print(f"  [{i}] icons-generated-cycle-{i}/")

        cycle_input = input("Output to cycle folder? (number or blank for default): ").strip()
        if cycle_input:
            try:
                output_cycle = int(cycle_input)
                print(f"  → Output to: icons-generated-cycle-{output_cycle}/")
            except:
                print("  → Using default output location")
                output_cycle = None
        else:
            output_cycle = None

        # Show output paths
        print("\nOutput paths:")
        for v in range(version_start, version_end + 1):
            out_path = get_output_base_for_version(v, output_cycle)
            print(f"  Version {v}: {out_path.relative_to(SCRIPT_DIR)}")

        # Load configuration for the cycle if available
        if output_cycle and configs_dict:
            config_to_use = output_cycle if output_cycle in configs_dict else 2
            print(f"\n📋 Loading Configuration {config_to_use} for Cycle {output_cycle}...")
            load_configuration(config_to_use, configs_dict)

    if choice == '2' or choice == '3':
        if not CATALOG_PATH.exists():
            print(f"\n⚠ Catalog not found: {CATALOG_PATH}")
            items = TEST_ITEMS
        else:
            print("\nLoading catalog...")
            items = parse_catalog(CATALOG_PATH)
            print(f"✓ Loaded {len(items)} items")
    else:
        items = TEST_ITEMS

    # Calculate total versions to generate
    versions_to_gen = version_end - version_start + 1

    print(f"\nItems: {len(items)}")
    print(f"Timeout: {GENERATION_TIMEOUT}s")
    print(f"Wait between: {WAIT_BETWEEN_ITEMS}s")
    print(f"Versions: {versions_to_gen} (v{version_start} to v{version_end})")
    if output_cycle:
        print(f"Output cycle: icons-generated-cycle-{output_cycle}/")

    # Pre-scan with custom range if specified
    pre_scan_directories_custom(items, version_start, version_end, output_cycle)

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

        for version in range(version_start, version_end + 1):
            version_num = version - version_start + 1
            total_versions = version_end - version_start + 1

            print("\n" + "="*70)
            print(f"GENERATING VERSION {version} ({version_num}/{total_versions})")
            print("="*70)

            output_folder = get_output_base_for_version(version, output_cycle)
            print(f"📁 Output: {output_folder}")

            success = 0
            failed = 0
            skipped = 0
            failed_list = []

            for i, item in enumerate(items, 1):
                print(f"\n[{i}/{len(items)}] Version {version}")

                try:
                    ok, skip = generate_item(driver, item, version=version, cycle=output_cycle)

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
                            ok, skip = generate_item(driver, item, version=version, cycle=output_cycle)

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

            if version < version_end:
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