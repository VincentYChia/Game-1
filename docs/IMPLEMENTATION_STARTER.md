# Unified JSON Creator - Implementation Starter Guide

## Quick Start (5 Minutes)

### Option 1: Start with Existing Tool Extension
The easiest path is to **extend your existing smithing grid designer** into a unified system.

**Current Tool**: `/Game-1-modular/tools/smithing-grid-designer.py` (585 lines, fully functional)

**What it does now**:
- ✅ Loads recipes and materials
- ✅ Visual 3x3/5x5/7x7/9x9 grid editor
- ✅ Material palette with usage tracking
- ✅ Validation (material counts)
- ✅ Auto-save to JSON
- ✅ Spacebar quick-reselect

**Extend it to**:
1. Add "JSON Type Selector" dropdown (Items, Recipes, NPCs, Quests, etc.)
2. Switch forms based on selected type
3. Reuse grid editor component for placements
4. Add form-based editors for other types

### Option 2: Build Web-Based System (Recommended for Long-Term)
Start fresh with React + FastAPI for scalability.

---

## Path 1: Extend Existing Python/Tkinter Tool

### Step 1: Refactor Current Tool (Day 1)
```python
# unified_json_creator.py

class UnifiedJSONCreator:
    def __init__(self, root):
        self.root = root
        self.json_type = tk.StringVar(value="placements")

        # Top selector
        type_selector = ttk.Combobox(
            self.root,
            textvariable=self.json_type,
            values=["items", "recipes", "placements", "npcs", "quests", "skills"],
            state="readonly"
        )
        type_selector.bind('<<ComboboxSelected>>', self.on_type_change)

        # Content frame (switches based on type)
        self.content_frame = ttk.Frame(self.root)
        self.load_editor()

    def on_type_change(self, event=None):
        """Switch editor based on selected JSON type"""
        json_type = self.json_type.get()

        # Clear current editor
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Load appropriate editor
        if json_type == "placements":
            self.load_grid_editor()  # Reuse existing smithing designer
        elif json_type == "items":
            self.load_item_editor()
        elif json_type == "recipes":
            self.load_recipe_editor()
        # ... etc

    def load_grid_editor(self):
        """Load existing grid placement editor"""
        # Copy logic from smithing-grid-designer.py
        pass

    def load_item_editor(self):
        """Load form for creating items"""
        # Simple form with Entry fields
        pass
```

### Step 2: Add Item Creator Form (Day 2)
```python
def load_item_editor(self):
    """Form-based item creator"""
    form_frame = ttk.Frame(self.content_frame)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Item ID
    ttk.Label(form_frame, text="Item ID:").grid(row=0, column=0, sticky=tk.W)
    self.item_id_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=self.item_id_var, width=40).grid(row=0, column=1)

    # Name
    ttk.Label(form_frame, text="Name:").grid(row=1, column=0, sticky=tk.W)
    self.item_name_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=self.item_name_var, width=40).grid(row=1, column=1)

    # Category dropdown
    ttk.Label(form_frame, text="Category:").grid(row=2, column=0, sticky=tk.W)
    self.category_var = tk.StringVar()
    category_combo = ttk.Combobox(
        form_frame,
        textvariable=self.category_var,
        values=["weapon", "armor", "tool", "consumable", "device", "station", "material"],
        state="readonly",
        width=37
    )
    category_combo.grid(row=2, column=1)

    # Tier
    ttk.Label(form_frame, text="Tier:").grid(row=3, column=0, sticky=tk.W)
    self.tier_var = tk.IntVar(value=1)
    ttk.Spinbox(form_frame, from_=1, to=4, textvariable=self.tier_var, width=38).grid(row=3, column=1)

    # Rarity
    ttk.Label(form_frame, text="Rarity:").grid(row=4, column=0, sticky=tk.W)
    self.rarity_var = tk.StringVar()
    rarity_combo = ttk.Combobox(
        form_frame,
        textvariable=self.rarity_var,
        values=["common", "uncommon", "rare", "epic", "legendary", "artifact"],
        state="readonly",
        width=37
    )
    rarity_combo.grid(row=4, column=1)

    # Narrative text area
    ttk.Label(form_frame, text="Narrative:").grid(row=5, column=0, sticky=tk.NW)
    self.narrative_text = tk.Text(form_frame, width=40, height=4)
    self.narrative_text.grid(row=5, column=1)

    # Save button
    save_btn = ttk.Button(
        form_frame,
        text="💾 Save Item",
        command=self.save_item
    )
    save_btn.grid(row=6, column=1, pady=20)

def save_item(self):
    """Save item to JSON"""
    item = {
        "itemId": self.item_id_var.get(),
        "name": self.item_name_var.get(),
        "category": self.category_var.get(),
        "tier": self.tier_var.get(),
        "rarity": self.rarity_var.get(),
        "metadata": {
            "narrative": self.narrative_text.get("1.0", tk.END).strip()
        }
    }

    # Validate
    if not item["itemId"] or not item["name"]:
        messagebox.showerror("Error", "Item ID and Name are required")
        return

    # Save to file
    file_path = f"Game-1-modular/items.JSON/items-custom.JSON"
    # ... append to JSON array

    messagebox.showinfo("Success", f"Item '{item['name']}' saved!")
```

### Step 3: Add Validation (Day 3)
```python
class Validator:
    def __init__(self, data_dir):
        self.items = self.load_json(f"{data_dir}/items.JSON/*.JSON")
        self.recipes = self.load_json(f"{data_dir}/recipes.JSON/*.JSON")
        # ... load all types

    def validate_recipe(self, recipe):
        """Validate recipe cross-references"""
        errors = []

        # Check output exists
        if recipe['outputId'] not in self.items:
            errors.append(f"outputId '{recipe['outputId']}' does not exist")

        # Check inputs exist
        for inp in recipe.get('inputs', []):
            if inp['materialId'] not in self.items:
                errors.append(f"materialId '{inp['materialId']}' does not exist")

        # Check tier consistency
        output_tier = self.items.get(recipe['outputId'], {}).get('tier', 0)
        if recipe['stationTier'] > output_tier:
            errors.append(f"stationTier ({recipe['stationTier']}) > output tier ({output_tier})")

        return errors

    def validate_all(self):
        """Run all validation rules"""
        all_errors = []

        for recipe_id, recipe in self.recipes.items():
            errors = self.validate_recipe(recipe)
            if errors:
                all_errors.append({
                    'type': 'recipe',
                    'id': recipe_id,
                    'errors': errors
                })

        return all_errors
```

**Pros of this approach**:
- ✅ Fast to implement (3-5 days)
- ✅ Reuses existing working code
- ✅ No new tech stack needed
- ✅ Familiar Python/Tkinter

**Cons**:
- ❌ Tkinter UI is clunky
- ❌ Hard to make it web-accessible
- ❌ Limited to single-user desktop

---

## Path 2: Build Web-Based System (React + FastAPI)

### Project Setup

```bash
# Create project structure
mkdir unified-json-creator
cd unified-json-creator

# Backend
mkdir backend
cd backend
poetry init
poetry add fastapi uvicorn pydantic python-multipart
poetry add --dev pytest black ruff

# Frontend
cd ..
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install react-hook-form zod @hookform/resolvers
npm install zustand axios
```

### Backend Setup (Day 1-2)

**File**: `backend/app/models/item.py`
```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from enum import Enum

class ItemCategory(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    TOOL = "tool"
    CONSUMABLE = "consumable"
    DEVICE = "device"
    STATION = "station"
    MATERIAL = "material"

class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"

class ItemMetadata(BaseModel):
    version: str = "1.0"
    narrative: Optional[str] = None
    tags: List[str] = []

class StatMultipliers(BaseModel):
    weight: float = 1.0
    damage: float = 1.0
    defense: float = 1.0

class Requirements(BaseModel):
    level: int = 1
    stats: Dict[str, int] = {}

class Flags(BaseModel):
    stackable: bool = True
    placeable: bool = False
    repairable: bool = False

class Item(BaseModel):
    metadata: Optional[ItemMetadata] = None
    itemId: str = Field(..., min_length=1, pattern=r'^[a-z_]+$')
    name: str = Field(..., min_length=1)
    category: ItemCategory
    type: Optional[str] = None
    subtype: Optional[str] = None
    tier: int = Field(..., ge=1, le=4)
    rarity: Rarity
    effect: Optional[str] = None
    stackSize: int = Field(default=1, ge=1, le=999)
    statMultipliers: Optional[StatMultipliers] = None
    requirements: Optional[Requirements] = None
    flags: Optional[Flags] = None
```

**File**: `backend/app/api/items.py`
```python
from fastapi import APIRouter, HTTPException
from app.models.item import Item
from app.services.item_service import ItemService
from typing import List

router = APIRouter(prefix="/api/items", tags=["items"])
item_service = ItemService()

@router.post("/create", response_model=Item)
async def create_item(item: Item):
    """Create a new item"""
    try:
        created_item = item_service.create(item)
        return created_item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{item_id}", response_model=Item)
async def get_item(item_id: str):
    """Get item by ID"""
    item = item_service.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/", response_model=List[Item])
async def list_items(
    category: Optional[str] = None,
    tier: Optional[int] = None,
    rarity: Optional[str] = None
):
    """List items with optional filters"""
    return item_service.list(category=category, tier=tier, rarity=rarity)

@router.put("/{item_id}", response_model=Item)
async def update_item(item_id: str, item: Item):
    """Update existing item"""
    updated = item_service.update(item_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated

@router.delete("/{item_id}")
async def delete_item(item_id: str):
    """Delete item"""
    deleted = item_service.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item deleted successfully"}
```

**File**: `backend/app/services/item_service.py`
```python
import json
from pathlib import Path
from typing import List, Optional
from app.models.item import Item

class ItemService:
    def __init__(self, data_dir: str = "../../Game-1-modular/items.JSON"):
        self.data_dir = Path(data_dir)
        self.items = self._load_all()

    def _load_all(self) -> dict:
        """Load all items from JSON files"""
        items = {}
        for json_file in self.data_dir.glob("*.JSON"):
            with open(json_file) as f:
                data = json.load(f)
                # Handle both array and object formats
                if isinstance(data, list):
                    for item in data:
                        items[item['itemId']] = item
                elif isinstance(data, dict):
                    for section, section_data in data.items():
                        if section == 'metadata':
                            continue
                        if isinstance(section_data, list):
                            for item in section_data:
                                items[item['itemId']] = item
        return items

    def create(self, item: Item) -> Item:
        """Create new item"""
        if item.itemId in self.items:
            raise ValueError(f"Item '{item.itemId}' already exists")

        self.items[item.itemId] = item.dict()
        self._save()
        return item

    def get(self, item_id: str) -> Optional[Item]:
        """Get item by ID"""
        item_data = self.items.get(item_id)
        return Item(**item_data) if item_data else None

    def list(self, category=None, tier=None, rarity=None) -> List[Item]:
        """List items with filters"""
        items = []
        for item_data in self.items.values():
            if category and item_data.get('category') != category:
                continue
            if tier and item_data.get('tier') != tier:
                continue
            if rarity and item_data.get('rarity') != rarity:
                continue
            items.append(Item(**item_data))
        return items

    def update(self, item_id: str, item: Item) -> Optional[Item]:
        """Update existing item"""
        if item_id not in self.items:
            return None

        self.items[item_id] = item.dict()
        self._save()
        return item

    def delete(self, item_id: str) -> bool:
        """Delete item"""
        if item_id not in self.items:
            return False

        del self.items[item_id]
        self._save()
        return True

    def _save(self):
        """Save items back to JSON"""
        output_file = self.data_dir / "items-custom.JSON"
        with open(output_file, 'w') as f:
            json.dump({
                "metadata": {"version": "1.0", "custom": True},
                "items": list(self.items.values())
            }, f, indent=2)
```

**File**: `backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import items, recipes, validation

app = FastAPI(title="Unified JSON Creator API")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(items.router)
# app.include_router(recipes.router)
# app.include_router(validation.router)

@app.get("/")
async def root():
    return {"message": "Unified JSON Creator API", "version": "1.0"}
```

### Frontend Setup (Day 3-4)

**File**: `frontend/src/types/item.ts`
```typescript
export type ItemCategory = 'weapon' | 'armor' | 'tool' | 'consumable' | 'device' | 'station' | 'material';
export type Rarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | 'artifact';

export interface Item {
  itemId: string;
  name: string;
  category: ItemCategory;
  type?: string;
  subtype?: string;
  tier: 1 | 2 | 3 | 4;
  rarity: Rarity;
  effect?: string;
  stackSize?: number;
  statMultipliers?: {
    weight?: number;
    damage?: number;
    defense?: number;
  };
  requirements?: {
    level?: number;
    stats?: Record<string, number>;
  };
  flags?: {
    stackable?: boolean;
    placeable?: boolean;
    repairable?: boolean;
  };
  metadata?: {
    version?: string;
    narrative?: string;
    tags?: string[];
  };
}
```

**File**: `frontend/src/components/ItemCreator.tsx`
```tsx
import React from 'react';
import { useForm } from 'react-hook-form';
import { Item } from '../types/item';
import { createItem } from '../api/items';

export const ItemCreator: React.FC = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<Item>();

  const onSubmit = async (data: Item) => {
    try {
      await createItem(data);
      alert('Item created successfully!');
    } catch (error) {
      alert('Error creating item: ' + error);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Create Item</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Item ID */}
        <div>
          <label className="block text-sm font-medium mb-1">Item ID*</label>
          <input
            {...register('itemId', { required: true, pattern: /^[a-z_]+$/ })}
            className="w-full border rounded px-3 py-2"
            placeholder="iron_sword"
          />
          {errors.itemId && <p className="text-red-500 text-sm">Invalid item ID (use lowercase and underscores)</p>}
        </div>

        {/* Name */}
        <div>
          <label className="block text-sm font-medium mb-1">Name*</label>
          <input
            {...register('name', { required: true })}
            className="w-full border rounded px-3 py-2"
            placeholder="Iron Sword"
          />
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium mb-1">Category*</label>
          <select {...register('category', { required: true })} className="w-full border rounded px-3 py-2">
            <option value="">Select category...</option>
            <option value="weapon">Weapon</option>
            <option value="armor">Armor</option>
            <option value="tool">Tool</option>
            <option value="consumable">Consumable</option>
            <option value="device">Device</option>
            <option value="station">Station</option>
            <option value="material">Material</option>
          </select>
        </div>

        {/* Tier */}
        <div>
          <label className="block text-sm font-medium mb-1">Tier*</label>
          <select {...register('tier', { required: true, valueAsNumber: true })} className="w-full border rounded px-3 py-2">
            <option value="1">Tier 1 (Starter)</option>
            <option value="2">Tier 2 (Basic)</option>
            <option value="3">Tier 3 (Advanced)</option>
            <option value="4">Tier 4 (Legendary)</option>
          </select>
        </div>

        {/* Rarity */}
        <div>
          <label className="block text-sm font-medium mb-1">Rarity*</label>
          <select {...register('rarity', { required: true })} className="w-full border rounded px-3 py-2">
            <option value="common">Common</option>
            <option value="uncommon">Uncommon</option>
            <option value="rare">Rare</option>
            <option value="epic">Epic</option>
            <option value="legendary">Legendary</option>
            <option value="artifact">Artifact</option>
          </select>
        </div>

        {/* Narrative */}
        <div>
          <label className="block text-sm font-medium mb-1">Narrative</label>
          <textarea
            {...register('metadata.narrative')}
            className="w-full border rounded px-3 py-2"
            rows={3}
            placeholder="A sturdy iron blade..."
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
        >
          💾 Create Item
        </button>
      </form>
    </div>
  );
};
```

### Run the System

```bash
# Terminal 1: Backend
cd backend
poetry run uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Open browser: http://localhost:5173
```

---

## Quick Wins (Implement These First)

### Priority 1: Item Creator
- Most foundational JSON type
- Simple form-based UI
- No complex relationships

### Priority 2: Recipe Creator
- Builds on items
- Add dropdown to select existing items as outputs
- Add material picker for inputs

### Priority 3: Placement Editor
- Reuse/extend existing smithing grid designer
- Add support for all placement formats

### Priority 4: Validation Dashboard
- Show all validation errors
- One-click fixes for common issues

---

## Next Steps

1. **Choose your path** (Python/Tkinter or React/FastAPI)
2. **Start with Item Creator** (simplest type)
3. **Add validation** (cross-reference checking)
4. **Extend to other types** (recipes, quests, etc.)
5. **Add batch operations** (templates)
6. **Polish UI** (visual editors, shortcuts)

**Time Estimates**:
- Path 1 (Python extension): 1-2 weeks
- Path 2 (Web system): 3-4 weeks

Both paths will get you a working unified creator - choose based on your tech preferences and long-term goals!
