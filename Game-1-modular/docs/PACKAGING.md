# Game-1 Packaging Documentation

This document explains how the game is packaged for distribution and how to create builds.

## 📦 Overview

Game-1 uses **PyInstaller** to create standalone executables that don't require Python or pip installations. The packaging system is integrated with **GitHub Actions** for automated builds.

## 🏗️ Architecture

### Path Management System

The game uses a custom `PathManager` (in `core/paths.py`) to handle resource loading in both development and packaged environments:

- **Development mode**: Loads from source directories
- **Packaged mode**: Loads from PyInstaller's temporary extraction folder (`sys._MEIPASS`)
- **Save files**: Always stored in user's home directory (writable location)

#### Save File Locations
- **Windows**: `%APPDATA%\Game1\saves\`
- **Linux**: `~/.local/share/Game1/saves\`
- **macOS**: `~/Library/Application Support/Game1/saves\`

### Files Modified for Packaging

The following files were updated to support packaged environments:

1. **core/paths.py** (NEW) - Path management system
2. **systems/save_manager.py** - Uses `get_save_path()`
3. **rendering/image_cache.py** - Uses `get_resource_path()`
4. **core/game_engine.py** - Wraps all file paths with `get_resource_path()`
5. **data/databases/*.py** - All database loaders use `get_resource_path()`

## 🛠️ Build System

### Local Builds

#### Prerequisites
```bash
pip install -r requirements-dev.txt
```

#### Build Commands

**Linux/macOS:**
```bash
./build.sh
```

**Windows:**
```cmd
build.bat
```

**Cross-platform (Python):**
```bash
cd Game-1-modular
pyinstaller Game1.spec
```

### Output

Builds are created in `dist/Game1/`:
- **Executable**: `Game1` (Linux/macOS) or `Game1.exe` (Windows)
- **All assets**: Bundled in the directory
- **Total size**: ~360-400 MB

## ⚙️ PyInstaller Configuration

### Game1.spec File

The `.spec` file defines how PyInstaller packages the game:

```python
# Key configuration:
- Entry point: main.py
- Bundled data:
  - assets/
  - items.JSON/
  - recipes.JSON/
  - placements.JSON/
  - Definitions.JSON/
  - progression/
  - Skills/

- Optimizations:
  - UPX compression enabled
  - Excludes: pytest, tkinter, unittest (dev tools)
  - No console window (windowed mode)

- Output: Directory bundle (not single-file)
```

### Why Directory Bundle?

We use directory bundle instead of `--onefile` because:
1. **Faster startup** (no extraction delay)
2. **Easier asset updates** (can replace individual files)
3. **Better compatibility** (some antivirus flag single-file less)
4. **Debugging** (can inspect bundled files)

## 🤖 Automated Builds (GitHub Actions)

### Workflow: `.github/workflows/build-game.yml`

#### Triggers
1. **Push** to `claude/game-packaging-standalone-*` branches
2. **Tags** matching `v*` (e.g., `v1.0.0`)
3. **Manual** via workflow_dispatch

#### Build Matrix
- **Windows**: `windows-latest` runner
- **Linux**: `ubuntu-latest` runner
- **macOS**: *(can be added)*

#### Process
1. Checkout code
2. Set up Python 3.11
3. Install dependencies + PyInstaller
4. Build with PyInstaller
5. Create archives (ZIP for Windows, tar.gz for Linux)
6. Upload artifacts (30-day retention)
7. **If tagged**: Create GitHub Release

### Creating a Release

To create an automated release:

```bash
git tag -a v0.1.0 -m "Playtest build v0.1.0"
git push origin v0.1.0
```

GitHub Actions will:
1. Build for Windows and Linux
2. Create a new Release
3. Attach the build artifacts
4. Generate release notes

## 📋 Build Checklist

Before creating a release build:

- [ ] All code committed and pushed
- [ ] Version number updated (if applicable)
- [ ] PLAYTEST_README.md is up to date
- [ ] Test builds locally on your platform
- [ ] Tag the commit with version number
- [ ] Push tag to trigger release

## 🐛 Troubleshooting

### Build Fails

**Problem**: PyInstaller import errors
```
Solution: Ensure all dependencies are in requirements.txt
Check hidden imports in Game1.spec
```

**Problem**: Assets not found
```
Solution: Verify all paths use get_resource_path()
Check datas list in Game1.spec
```

**Problem**: Save system doesn't work
```
Solution: Check PathManager initialization
Verify write permissions in save directory
```

### Runtime Issues

**Problem**: "No module named..." errors
```
Solution: Add missing module to hiddenimports in Game1.spec
```

**Problem**: Images not loading
```
Solution: Check image_cache.py uses get_resource_path()
Verify assets/ directory is bundled
```

**Problem**: JSON files not loading
```
Solution: Check all database .load_from_file() calls use get_resource_path()
```

## 🔧 Optimization Tips

### Reducing Build Size

1. **Compress assets**:
   ```bash
   # Use tools like pngquant for PNG compression
   find assets -name "*.png" -exec pngquant --ext .png --force {} \;
   ```

2. **Exclude unused modules**:
   ```python
   # In Game1.spec, add to excludes list
   excludes=['matplotlib', 'numpy', ...]
   ```

3. **Use UPX compression**:
   ```python
   # Already enabled in Game1.spec
   upx=True
   ```

### Improving Startup Time

1. **Lazy load assets**: Load images on-demand (already implemented)
2. **Reduce initial data**: Load only essential JSONs at startup
3. **Directory bundle**: Faster than `--onefile` (already used)

## 📊 Build Statistics

| Metric | Value |
|--------|-------|
| **Source size** | ~2 MB (Python code) |
| **Asset size** | ~358 MB (images) |
| **Build output** | ~360-400 MB |
| **Build time** | 5-10 minutes |
| **Startup time** | 30-60 seconds (first launch) |
| **Memory usage** | ~200-400 MB (runtime) |

## 🚀 Distribution Workflow

### For Playtesters

1. **Build locally** or wait for GitHub Actions
2. **Download** artifact from Actions tab or Release
3. **Share** download link with playtesters
4. **Collect feedback** via GitHub Issues

### For Updates

1. **Make changes** to code/assets
2. **Commit and push** to your branch
3. **Wait** for GitHub Actions to build
4. **Download** updated build
5. **Notify** playtesters of update

### For Major Releases

1. **Test thoroughly** with local build
2. **Update version** in code and docs
3. **Create tag**: `git tag -a v1.0.0 -m "Version 1.0.0"`
4. **Push tag**: `git push origin v1.0.0`
5. **GitHub creates release** automatically
6. **Edit release notes** if needed
7. **Announce** to community

## 📝 Notes for Developers

### Modifying Packaged Data

If you change which JSON files are loaded:
1. Update `Game1.spec` datas list
2. Update database load calls in `core/game_engine.py`
3. Wrap paths with `get_resource_path()`

### Adding New Assets

1. Place files in appropriate `assets/` subdirectory
2. PyInstaller automatically includes entire `assets/` folder
3. Reference using `ImageCache` system

### Changing Save Format

If modifying save system:
1. Update `SaveManager` in `systems/save_manager.py`
2. Save path is always `get_save_path(filename)`
3. Test both development and packaged modes

## 🔐 Code Signing (Optional)

For production releases, consider code signing to avoid antivirus warnings:

**Windows**:
```bash
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com Game1.exe
```

**macOS**:
```bash
codesign --sign "Developer ID Application: Your Name" --deep Game1.app
```

Cost: ~$100-300/year for certificates

## 📚 Resources

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pygame Documentation](https://www.pygame.org/docs/)

---

**Questions or Issues?**
Create an issue on GitHub or check the troubleshooting section above.
