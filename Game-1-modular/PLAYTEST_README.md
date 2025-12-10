# Game-1 Playtest Build

Thank you for playtesting Game-1! This is an early playtest build of a 2D RPG with crafting systems, combat, and quests.

## 🎮 Quick Start

### Windows
1. Extract `Game1-Windows.zip`
2. Open the `Game1` folder
3. Double-click `Game1.exe`

### Linux
1. Extract `Game1-Linux.tar.gz`
2. Open terminal in the `Game1` folder
3. Run: `./Game1`

### macOS
*(macOS builds coming soon)*

## 🎯 What to Test

This is a comprehensive RPG with the following systems:

### Core Gameplay
- **Movement**: WASD or Arrow Keys
- **World Exploration**: 100×100 tile procedurally generated world
- **Resource Gathering**: Left-click on trees, ore nodes, stones

### Combat System
- **Attack**: Space bar (when weapon equipped)
- **Enemies**: Multiple tiers (T1-T4) with scaling difficulty
- **Safe Zone**: Center area (50,50) with no enemies

### Crafting System (5 Disciplines)
- **Smithing**: Weapons and armor (temperature + timing minigame)
- **Alchemy**: Potions and consumables (mixing minigame)
- **Refining**: Convert raw materials to refined (stages minigame)
- **Engineering**: Devices and utilities (assembly minigame)
- **Enchanting**: Adornments and enhancements (pattern minigame)

### Progression
- **Leveling**: Gain XP from combat and crafting
- **Classes**: 6 playable classes (Warrior, Ranger, Scholar, Artisan, Scavenger, Adventurer)
- **Skills**: 40+ combat skills with evolution paths
- **Titles**: 30+ titles earned through activities
- **Quests**: 20+ quests from NPCs

## ⌨️ Controls

### Movement & Interaction
- **WASD / Arrow Keys**: Move character
- **E**: Interact (NPCs, crafting stations, resources)
- **Left Click**: Attack / Harvest

### UI Navigation
- **I**: Toggle Inventory
- **C**: Toggle Character Stats
- **K**: Toggle Skills
- **Q**: Toggle Quest Log
- **B**: Toggle Encyclopedia
- **ESC**: Close UI / Open Start Menu

### Debug & Development
- **F1**: Toggle Debug Mode (infinite resources, instant crafting)
- **F5**: Quick Save (autosave.json)
- **F6**: Timestamped Save
- **F9**: Quick Load (from autosave)
- **F11**: Toggle Fullscreen

## 📁 Save Files

Your save files are stored in:
- **Windows**: `%APPDATA%\Game1\saves\`
- **Linux**: `~/.local/share/Game1/saves/`
- **macOS**: `~/Library/Application Support/Game1/saves/`

## 🐛 Known Issues

1. **Slow First Launch**: Asset loading may take 30-60 seconds on first run
2. **Antivirus Warnings**: Windows Defender may flag the exe (false positive - unsigned software)
3. **Performance**: Some systems may experience frame drops with many entities
4. **World Regeneration**: World regenerates on each load (placements preserved)

## 🧪 What We're Testing

Please provide feedback on:

### Critical Issues
- [ ] Game crashes or fails to launch
- [ ] Cannot save/load game
- [ ] Controls not responding
- [ ] Game-breaking bugs

### Gameplay Feedback
- [ ] Combat feel (difficulty, responsiveness)
- [ ] Crafting minigames (fun, clarity, difficulty)
- [ ] Resource gathering (pacing, balance)
- [ ] Quest system (clarity, rewards)
- [ ] Progression (leveling speed, stat balance)

### Polish & UX
- [ ] UI readability and clarity
- [ ] Icon/art quality
- [ ] Tutorial/onboarding (is anything confusing?)
- [ ] Performance issues
- [ ] Suggestions for improvement

## 📝 How to Report Issues

When reporting bugs, please include:
1. **What happened**: Describe the issue
2. **How to reproduce**: Steps to trigger the bug
3. **Expected behavior**: What should have happened
4. **System info**: OS, specs
5. **Save file**: If relevant, attach your save file

## 💡 Tips for Playtesters

1. **Start Simple**: Try basic crafting before advanced systems
2. **Use Debug Mode (F1)**: Great for testing without grinding
3. **Try Different Classes**: Each class plays differently
4. **Experiment with Skills**: Skills evolve as you level them up
5. **Talk to NPCs**: Quests provide good rewards and structure
6. **Check Encyclopedia (B)**: Tracks discoveries and provides hints

## 🚀 Development Roadmap

This playtest build focuses on core systems. Future updates may include:
- More content (items, recipes, quests)
- Multiplayer/co-op
- Base building
- Additional classes and skills
- Story campaign
- Sound and music
- More polish and optimization

## 📧 Contact

For questions, feedback, or bug reports:
- GitHub Issues: [Create an issue](../../issues)
- Discord: *(if you have a discord server)*
- Email: *(if you want to provide an email)*

## 🙏 Thank You!

Thanks for helping test Game-1! Your feedback is invaluable in making this game better.

---

**Build Info:**
- Version: Playtest Alpha
- Build System: PyInstaller + GitHub Actions
- Python Version: 3.11
- Game Engine: Pygame 2.6+
