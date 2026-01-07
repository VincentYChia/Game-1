# Minigame Background Assets

This folder contains optional PNG background images for crafting minigames.

## Supported Files

Place PNG files with these exact names to override the procedurally generated backgrounds:

| Filename | Discipline | Recommended Theme |
|----------|------------|-------------------|
| `smithing_bg.png` | Smithing | Forge with flames, anvil, embers |
| `refining_bg.png` | Refining | Kiln/foundry with bronze fire, gears |
| `alchemy_bg.png` | Alchemy | Lab/wizard tower mix, professional |
| `engineering_bg.png` | Engineering | Workbench, scattered tools, warm lighting |
| `enchanting_bg.png` | Enchanting | Light blue spirit theme, natural/clean |

## Image Requirements

- **Resolution**: 800x600 pixels recommended (will be scaled to fit minigame area)
- **Format**: PNG with transparency supported
- **Style**: Dark enough that UI elements remain readable

## How It Works

1. If a PNG file exists with the correct name, it will be loaded as the background
2. If no PNG exists, a procedurally generated background is used instead
3. Visual effects (particles, flames, etc.) are drawn ON TOP of the background

## Color Guidelines by Discipline

### Smithing
- Dark reds, oranges, blacks
- Forge fire glow at bottom
- Metallic grays for anvil area

### Refining
- Bronze/copper tones
- Kiln mouth with warm glow
- Gear decorations in corners

### Alchemy
- Light, professional colors
- Wood paneling at bottom
- Clean lab aesthetic with wizard tower hints

### Engineering
- Wood workbench browns
- Warm overhead lighting
- Tool shadows and metal accents

### Enchanting
- Light blues and soft whites
- Spirit-like gentle aesthetic
- Natural, clean, ethereal feel

## Tips

- Keep the center area relatively clear for gameplay elements
- Use darker edges to frame the minigame
- Include subtle texture for visual interest
- Effects layer will add particles, so don't make background too busy
