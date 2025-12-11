#!/bin/bash
# Game-1 Build Script for Linux/macOS
# Packages the game into a standalone executable using PyInstaller

set -e  # Exit on error

echo "======================================"
echo "  Game-1 Build Script"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the correct directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: main.py not found. Please run this script from the Game-1-modular directory.${NC}"
    exit 1
fi

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}PyInstaller not found. Installing...${NC}"
    pip3 install pyinstaller
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf build/ dist/
echo -e "${GREEN}✓ Cleaned${NC}"
echo ""

# Build with PyInstaller
echo -e "${YELLOW}Building Game-1 with PyInstaller...${NC}"
echo "This may take 5-10 minutes..."
echo ""

pyinstaller Game1.spec

echo ""
if [ -d "dist/Game1" ]; then
    echo -e "${GREEN}======================================"
    echo "  Build Complete!"
    echo "======================================${NC}"
    echo ""
    echo "Executable location: dist/Game1/Game1"
    echo "Total size: $(du -sh dist/Game1 | cut -f1)"
    echo ""
    echo "To test the game, run:"
    echo "  cd dist/Game1"
    echo "  ./Game1"
    echo ""
    echo -e "${YELLOW}Note: Save files will be stored in:${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  ~/Library/Application Support/Game1/saves/"
    else
        echo "  ~/.local/share/Game1/saves/"
    fi
else
    echo -e "${RED}Build failed. Check the output above for errors.${NC}"
    exit 1
fi
