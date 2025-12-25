#!/usr/bin/env python3
"""
Deploy Update - Complete automation for deploying Update-N packages

This is the ONE COMMAND to deploy an update. It handles:
1. Placeholder icon generation
2. Catalog updates for Vheer
3. JSON validation
4. Conflict detection
5. Installation

Usage:
    python tools/deploy_update.py Update-1
    python tools/deploy_update.py Update-1 --force
    python tools/deploy_update.py Update-1 --skip-icons
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(command: list, description: str) -> bool:
    """Run a command and handle errors"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}\n")

    try:
        result = subprocess.run(command, check=True, cwd=project_root)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed: {description}")
        print(f"   Error code: {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def deploy_update(update_name: str, skip_icons: bool = False, skip_catalog: bool = False, force: bool = False):
    """Deploy an update package with full automation"""
    print(f"\n🚀 DEPLOYING {update_name}")
    print(f"{'='*70}\n")

    steps = [
        ("validate", f"Validating {update_name}..."),
        ("icons", "Generating placeholder icons..."),
        ("catalog", "Updating Vheer catalog..."),
        ("install", f"Installing {update_name}...")
    ]

    # Step 1: Validate
    print(f"📋 Step 1/4: {steps[0][1]}")
    validate_cmd = ["python", "tools/update_manager.py", "validate", update_name]
    if not run_command(validate_cmd, "Validation"):
        print(f"\n❌ Deployment failed at validation step")
        return False

    # Step 2: Generate icons (optional)
    if not skip_icons:
        print(f"\n🎨 Step 2/4: {steps[1][1]}")
        icons_cmd = ["python", "tools/create_placeholder_icons_simple.py", "--update", update_name]
        # Non-critical - continue even if fails
        run_command(icons_cmd, "Icon Generation")
    else:
        print(f"\n⏭️  Step 2/4: Skipped (--skip-icons)")

    # Step 3: Update catalog (optional)
    if not skip_catalog:
        print(f"\n📚 Step 3/4: {steps[2][1]}")
        catalog_cmd = ["python", "tools/update_catalog.py", "--update", update_name]
        # Non-critical - continue even if fails
        run_command(catalog_cmd, "Catalog Update")
    else:
        print(f"\n⏭️  Step 3/4: Skipped (--skip-catalog)")

    # Step 4: Install
    print(f"\n📦 Step 4/4: {steps[3][1]}")
    install_cmd = ["python", "tools/update_manager.py", "install", update_name]
    if force:
        install_cmd.append("--force")

    if not run_command(install_cmd, "Installation"):
        print(f"\n❌ Deployment failed at installation step")
        return False

    # Success!
    print(f"\n{'='*70}")
    print(f"✅ {update_name} DEPLOYED SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"\n📝 Next steps:")
    print(f"   1. Launch game: python main.py")
    print(f"   2. Check console for Update-N loading messages")
    print(f"   3. Test new content in-game")
    print(f"\n💡 To uninstall:")
    print(f"   python tools/update_manager.py uninstall {update_name}")
    print()

    return True


def main():
    parser = argparse.ArgumentParser(description='Deploy Update-N package (complete automation)')
    parser.add_argument('update', help='Update name (e.g., Update-1)')
    parser.add_argument('--force', action='store_true',
                       help='Force installation (ignore conflicts)')
    parser.add_argument('--skip-icons', action='store_true',
                       help='Skip placeholder icon generation')
    parser.add_argument('--skip-catalog', action='store_true',
                       help='Skip Vheer catalog update')

    args = parser.parse_args()

    success = deploy_update(
        args.update,
        skip_icons=args.skip_icons,
        skip_catalog=args.skip_catalog,
        force=args.force
    )

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
