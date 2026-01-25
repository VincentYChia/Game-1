"""
LLM Item Generator - Creates new items from validated recipes

Uses Claude API to generate item definitions based on:
- Recipe placement (materials and quantities)
- Station type and tier
- Material properties and narratives

Design principles:
- Modular: Easy to swap prompts, models, and backends
- Robust: Graceful fallbacks if API unavailable
- Scalable: Support for all 5 crafting disciplines
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import hashlib


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class LLMConfig:
    """Configuration for LLM item generation"""
    api_key: str = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2000
    temperature: float = 0.4  # Slightly lower for more consistent output
    top_p: float = 0.95
    timeout: float = 30.0
    enabled: bool = True

    # Fallback behavior
    use_fallback_on_error: bool = True
    cache_enabled: bool = True
    cache_dir: str = "invented_items_cache"


# ==============================================================================
# RESULT TYPES
# ==============================================================================

@dataclass
class GeneratedItem:
    """Result from LLM item generation"""
    success: bool
    item_data: Optional[Dict] = None
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    discipline: str = ""
    error: Optional[str] = None
    from_cache: bool = False

    @property
    def is_error(self) -> bool:
        return not self.success


# ==============================================================================
# PROMPT BUILDERS (One per discipline)
# ==============================================================================

class PromptBuilder(ABC):
    """Abstract base for discipline-specific prompt builders"""

    @abstractmethod
    def build_system_prompt(self) -> str:
        """Build the system prompt for this discipline"""
        pass

    @abstractmethod
    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        """Build the user prompt with recipe context"""
        pass

    @abstractmethod
    def parse_response(self, response_text: str) -> Dict:
        """Parse LLM response into item data"""
        pass


class SmithingPromptBuilder(PromptBuilder):
    """Builds prompts for smithing item generation"""

    SYSTEM_PROMPT = """You are a crafting expert for an action fantasy sandbox RPG. Given smithing recipes with materials and metadata, generate complete item definitions with stats, tags, and properties. Return ONLY valid JSON matching the expected schema.

# Smithing Items - Field Guidelines

Generate a JSON object following this template, there is a library of tags to select from. Stay within tier limits and stay within the library of options for each field. Anything not in the library will render the JSON invalid. You are to pick the most suitable values, tags, and otherwise output using this library as a guide.

```json
{
  "metadata": {
    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",
    "tags": ["Pick 2-5 from: "1H", "2H", "accessory", "alchemy", "amulet", "armor", "armor_breaker", "axe", "bash", "bow", "bracelet", "brewing", "chest", "cleaving", "crushing", "dagger", "defensive", "elemental", "engineering", "fast", "feet", "fire", "flexible", "forge", "forging", "hands", "head", "heavy", "legendary", "legs", "light", "lightning", "mace", "master", "mechanical", "melee", "metal", "pickaxe", "precision", "quality", "ranged", "reach", "refinery", "ring", "shield", "smithing", "spear", "staff", "standard", "starter", "station", "sword", "tool", "versatile", "water"]
  },
  "category": "Pick one: ["equipment", "station"]",
  "slot": "Pick one: ["accessory", "chest", "feet", "hands", "head", "legs", "mainHand"]",
  "type": "Pick one: ["accessory", "alchemy", "armor", "axe", "bow", "dagger", "engineering", "mace", "refining", "shield", "smithing", "staff", "tool", "weapon"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===
  "range": 0.5-15.0

  "effectTags": ["Pick 2-5 from: "burn", "crushing", "fire", "physical", "piercing", "single", "slashing"],

  "effectParams": {
    "baseDamage": 0,  // Tier 1: 10.0-30.0, Tier 2: 18.0-50.0, Tier 3: ~41.0, Tier 4: ~75.0
    "burn_damage_per_second": 0,  // 
    "burn_duration": 0,  // 
  },

  "stats": {
    "damage[0]": 0,  // Tier 1: ~8.0, Tier 2: ~15.0, Tier 3: ~30.0, Tier 4: ~60.0
    "damage[1]": 0,  // Tier 1: ~12.0, Tier 2: ~22.0, Tier 3: ~45.0, Tier 4: ~90.0
    "durability[0]": 0,  // Tier 1: ~500.0, Tier 2: ~1000.0, Tier 3: ~2000.0, Tier 4: ~4000.0
    "durability[1]": 0,  // Tier 1: ~500.0, Tier 2: ~1000.0, Tier 3: ~2000.0, Tier 4: ~4000.0
    "forestry": 0,  // 
    "mining": 0,  // 
    "weight": 0,  // 2.5-5.5
  },

  "requirements": {
    "level": Pick a level requirement,  // Tier 1: 1-5, Tier 2: 6-15, Tier 3: 16-25, Tier 4: 26-30
    "stats": {
      "AGI": Pick a value relative to the tier,  // 1-30.
      "INT": Pick a value relative to the tier,  // 1-30.
      "STR": Pick a value relative to the tier,  // 1-30.
    }
  },

  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}
```

## Important Guidelines:

1. **IDs**: Use snake_case (e.g., `iron_sword`, `health_potion`)
2. **Names**: Use Title Case matching ID (e.g., `Iron Sword`, `Health Potion`)
3. **Tier Consistency**: Ensure all stats match the specified tier
4. **Tags**: Only use tags from the library above
5. **Narrative**: Keep it concise (2-3 sentences) and thematic
6. **Stats**: Stay within ±20% of tier ranges
"""

    def build_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        """Build user prompt from recipe context"""
        inputs = recipe_context.get('inputs', [])
        station_tier = recipe_context.get('station_tier', 1)

        # Build materials description
        materials_desc = []
        for mat_input in inputs:
            mat_id = mat_input.get('materialId')
            qty = mat_input.get('quantity', 1)

            # Get material data
            mat_data = self._get_material_data(mat_id, materials_db)

            materials_desc.append({
                "materialId": mat_id,
                "quantity": qty,
                "materialName": mat_data.get('name', mat_id.replace('_', ' ').title()),
                "materialTier": mat_data.get('tier', 1),
                "materialRarity": mat_data.get('rarity', 'common'),
                "materialNarrative": mat_data.get('narrative', ''),
                "materialTags": mat_data.get('tags', [])
            })

        prompt_data = {
            "recipeId": f"invented_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stationTier": station_tier,
            "stationType": "smithing",
            "inputs": materials_desc,
            "narrative": "Player-invented smithing recipe. Create an appropriate item."
        }

        return json.dumps(prompt_data, indent=2)

    def _get_material_data(self, mat_id: str, materials_db) -> Dict:
        """Extract material data for prompt"""
        if hasattr(materials_db, 'get_material'):
            mat = materials_db.get_material(mat_id)
            if mat:
                tags = []
                if hasattr(mat, 'properties') and mat.properties:
                    tags = mat.properties.get('tags', [])
                return {
                    'name': mat.name if hasattr(mat, 'name') else mat_id,
                    'tier': mat.tier,
                    'rarity': getattr(mat, 'rarity', 'common'),
                    'narrative': getattr(mat, 'description', ''),
                    'tags': tags
                }
        return {'name': mat_id, 'tier': 1, 'rarity': 'common', 'narrative': '', 'tags': []}

    def parse_response(self, response_text: str) -> Dict:
        """Parse LLM response into item data"""
        # Find JSON in response
        text = response_text.strip()

        # Try direct parse first
        if text.startswith('{'):
            return json.loads(text)

        # Find JSON block
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end+1])

        raise ValueError("No valid JSON found in response")


class RefiningPromptBuilder(PromptBuilder):
    """Builds prompts for refining material generation"""

    SYSTEM_PROMPT = """You are a game material designer for a fantasy crafting RPG. Generate JSON material definitions for refining recipes.

Given core and surrounding materials, create a refined material that:
1. Combines properties of input materials
2. Has appropriate tier (usually +1 from inputs)
3. Includes thematic narrative and tags

Output ONLY valid JSON with this structure:
{
  "metadata": {
    "narrative": "2-3 sentences describing the material",
    "tags": ["refined", "category_tag", "property_tag"]
  },
  "materialId": "snake_case_id",
  "name": "Title Case Name",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary",
  "category": "metal|wood|stone|gem|elemental|monster_drop"
}"""

    def build_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        core_inputs = recipe_context.get('core_inputs', [])
        surrounding_inputs = recipe_context.get('surrounding_inputs', [])
        station_tier = recipe_context.get('station_tier', 1)

        # Build materials descriptions
        core_desc = []
        for mat_input in core_inputs:
            mat_data = self._get_material_data(mat_input.get('materialId'), materials_db)
            core_desc.append({
                "materialId": mat_input.get('materialId'),
                "quantity": mat_input.get('quantity', 1),
                **mat_data
            })

        surrounding_desc = []
        for mat_input in surrounding_inputs:
            mat_data = self._get_material_data(mat_input.get('materialId'), materials_db)
            surrounding_desc.append({
                "materialId": mat_input.get('materialId'),
                "quantity": mat_input.get('quantity', 1),
                **mat_data
            })

        prompt_data = {
            "recipeId": f"invented_refining_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stationTier": station_tier,
            "stationType": "refining",
            "coreInputs": core_desc,
            "surroundingInputs": surrounding_desc,
            "narrative": "Player-invented refining recipe. Create an appropriate refined material."
        }

        return json.dumps(prompt_data, indent=2)

    def _get_material_data(self, mat_id: str, materials_db) -> Dict:
        if hasattr(materials_db, 'get_material'):
            mat = materials_db.get_material(mat_id)
            if mat:
                return {
                    'materialName': mat.name if hasattr(mat, 'name') else mat_id,
                    'materialTier': mat.tier,
                    'materialRarity': getattr(mat, 'rarity', 'common'),
                    'materialCategory': mat.category
                }
        return {'materialName': mat_id, 'materialTier': 1, 'materialRarity': 'common', 'materialCategory': 'unknown'}

    def parse_response(self, response_text: str) -> Dict:
        text = response_text.strip()
        if text.startswith('{'):
            return json.loads(text)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end+1])
        raise ValueError("No valid JSON found in response")


class AlchemyPromptBuilder(PromptBuilder):
    """Builds prompts for alchemy item generation"""

    SYSTEM_PROMPT = """You are a game item designer for a fantasy crafting RPG. Generate JSON consumable definitions for alchemy recipes.

Given ingredients in order, create a potion/consumable that:
1. Has effects based on ingredient properties
2. Matches tier of highest-tier ingredient
3. Includes thematic narrative and tags

Output ONLY valid JSON with this structure:
{
  "metadata": {
    "narrative": "2-3 sentences describing the item",
    "tags": ["potion", "effect_type", "consumable"]
  },
  "itemId": "snake_case_id",
  "name": "Title Case Name",
  "category": "consumable",
  "type": "potion",
  "subtype": "healing|buff|utility|damage",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary",
  "effect": "Description of what it does",
  "duration": number_in_seconds_or_0_for_instant,
  "stackSize": 20,
  "requirements": {
    "level": number
  },
  "flags": {
    "stackable": true,
    "consumable": true,
    "repairable": false
  }
}"""

    def build_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        ingredients = recipe_context.get('ingredients', [])
        station_tier = recipe_context.get('station_tier', 1)

        ingredients_desc = []
        for i, ing in enumerate(ingredients):
            mat_data = self._get_material_data(ing.get('materialId'), materials_db)
            ingredients_desc.append({
                "slot": i + 1,
                "materialId": ing.get('materialId'),
                "quantity": ing.get('quantity', 1),
                **mat_data
            })

        prompt_data = {
            "recipeId": f"invented_alchemy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stationTier": station_tier,
            "stationType": "alchemy",
            "ingredients": ingredients_desc,
            "narrative": "Player-invented alchemy recipe. Create an appropriate potion or consumable."
        }

        return json.dumps(prompt_data, indent=2)

    def _get_material_data(self, mat_id: str, materials_db) -> Dict:
        if hasattr(materials_db, 'get_material'):
            mat = materials_db.get_material(mat_id)
            if mat:
                tags = []
                if hasattr(mat, 'properties') and mat.properties:
                    tags = mat.properties.get('tags', [])
                return {
                    'materialName': mat.name if hasattr(mat, 'name') else mat_id,
                    'materialTier': mat.tier,
                    'materialRarity': getattr(mat, 'rarity', 'common'),
                    'materialTags': tags
                }
        return {'materialName': mat_id, 'materialTier': 1, 'materialRarity': 'common', 'materialTags': []}

    def parse_response(self, response_text: str) -> Dict:
        text = response_text.strip()
        if text.startswith('{'):
            return json.loads(text)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end+1])
        raise ValueError("No valid JSON found in response")


class EngineeringPromptBuilder(PromptBuilder):
    """Builds prompts for engineering device generation"""

    SYSTEM_PROMPT = """You are a game item designer for a fantasy crafting RPG. Generate JSON device definitions for engineering recipes.

Given slot assignments (FRAME, FUNCTION, POWER, etc.), create a device that:
1. Has appropriate type (turret, bomb, trap, tool)
2. Matches tier of materials
3. Includes thematic narrative and tags

Output ONLY valid JSON with this structure:
{
  "metadata": {
    "narrative": "2-3 sentences describing the device",
    "tags": ["device", "type_tag", "effect_tag"]
  },
  "itemId": "snake_case_id",
  "name": "Title Case Name",
  "category": "device",
  "type": "turret|bomb|trap|tool",
  "subtype": "specific_type",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary",
  "effect": "Description of what it does",
  "effectTags": ["damage_type", "geometry_tag"],
  "effectParams": {
    "baseDamage": number,
    "range": number
  },
  "stackSize": 5-10,
  "requirements": {
    "level": number
  },
  "flags": {
    "stackable": true,
    "placeable": true,
    "repairable": false
  }
}"""

    def build_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        slots = recipe_context.get('slots', [])
        station_tier = recipe_context.get('station_tier', 1)

        slots_desc = []
        for slot in slots:
            mat_data = self._get_material_data(slot.get('materialId'), materials_db)
            slots_desc.append({
                "type": slot.get('type', 'UNKNOWN'),
                "materialId": slot.get('materialId'),
                "quantity": slot.get('quantity', 1),
                **mat_data
            })

        prompt_data = {
            "recipeId": f"invented_engineering_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stationTier": station_tier,
            "stationType": "engineering",
            "slots": slots_desc,
            "narrative": "Player-invented engineering recipe. Create an appropriate device."
        }

        return json.dumps(prompt_data, indent=2)

    def _get_material_data(self, mat_id: str, materials_db) -> Dict:
        if hasattr(materials_db, 'get_material'):
            mat = materials_db.get_material(mat_id)
            if mat:
                return {
                    'materialName': mat.name if hasattr(mat, 'name') else mat_id,
                    'materialTier': mat.tier,
                    'materialRarity': getattr(mat, 'rarity', 'common')
                }
        return {'materialName': mat_id, 'materialTier': 1, 'materialRarity': 'common'}

    def parse_response(self, response_text: str) -> Dict:
        text = response_text.strip()
        if text.startswith('{'):
            return json.loads(text)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end+1])
        raise ValueError("No valid JSON found in response")


class AdornmentPromptBuilder(PromptBuilder):
    """Builds prompts for adornment/enchanting generation"""

    SYSTEM_PROMPT = """You are a game item designer for a fantasy crafting RPG. Generate JSON accessory/enchantment definitions.

Given vertex materials and shapes, create an accessory that:
1. Has magical properties based on materials
2. Matches tier of highest-tier material
3. Includes thematic narrative and tags

Output ONLY valid JSON with this structure:
{
  "metadata": {
    "narrative": "2-3 sentences describing the accessory",
    "tags": ["accessory", "type_tag", "enchant_type"]
  },
  "itemId": "snake_case_id",
  "name": "Title Case Name",
  "category": "equipment",
  "type": "accessory",
  "subtype": "ring|amulet|bracelet|charm",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary",
  "slot": "accessory",
  "enchantments": [
    {"type": "enchant_name", "level": 1-5}
  ],
  "stats": {
    "stat_name": bonus_value
  },
  "requirements": {
    "level": number
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""

    def build_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, recipe_context: Dict, materials_db) -> str:
        vertices = recipe_context.get('vertices', {})
        shapes = recipe_context.get('shapes', [])
        station_tier = recipe_context.get('station_tier', 1)

        vertices_desc = {}
        for coord, mat_data in vertices.items():
            mat_info = self._get_material_data(mat_data.get('materialId'), materials_db)
            vertices_desc[coord] = {
                "materialId": mat_data.get('materialId'),
                **mat_info
            }

        prompt_data = {
            "recipeId": f"invented_adornment_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stationTier": station_tier,
            "stationType": "enchanting",
            "vertices": vertices_desc,
            "shapes": shapes,
            "narrative": "Player-invented adornment recipe. Create an appropriate accessory."
        }

        return json.dumps(prompt_data, indent=2)

    def _get_material_data(self, mat_id: str, materials_db) -> Dict:
        if hasattr(materials_db, 'get_material'):
            mat = materials_db.get_material(mat_id)
            if mat:
                tags = []
                if hasattr(mat, 'properties') and mat.properties:
                    tags = mat.properties.get('tags', [])
                return {
                    'materialName': mat.name if hasattr(mat, 'name') else mat_id,
                    'materialTier': mat.tier,
                    'materialRarity': getattr(mat, 'rarity', 'common'),
                    'materialTags': tags
                }
        return {'materialName': mat_id, 'materialTier': 1, 'materialRarity': 'common', 'materialTags': []}

    def parse_response(self, response_text: str) -> Dict:
        text = response_text.strip()
        if text.startswith('{'):
            return json.loads(text)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end+1])
        raise ValueError("No valid JSON found in response")


# ==============================================================================
# LLM BACKENDS
# ==============================================================================

class LLMBackend(ABC):
    """Abstract base for LLM API backends"""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str,
                 config: LLMConfig) -> Tuple[str, Optional[str]]:
        """
        Generate text from LLM.

        Returns:
            Tuple of (response_text, error_message or None)
        """
        pass


class AnthropicBackend(LLMBackend):
    """Anthropic Claude API backend"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def generate(self, system_prompt: str, user_prompt: str,
                 config: LLMConfig) -> Tuple[str, Optional[str]]:
        try:
            client = self._get_client()

            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            return response.content[0].text, None

        except Exception as e:
            return "", f"API error: {str(e)}"


class MockBackend(LLMBackend):
    """Mock backend for testing without API"""

    def generate(self, system_prompt: str, user_prompt: str,
                 config: LLMConfig) -> Tuple[str, Optional[str]]:
        # Return a simple mock item
        mock_item = {
            "metadata": {
                "narrative": "A mysterious item crafted from unusual materials.",
                "tags": ["invented", "mysterious"]
            },
            "itemId": f"invented_item_{datetime.now().strftime('%H%M%S')}",
            "name": "Mysterious Invention",
            "category": "equipment",
            "type": "weapon",
            "tier": 1,
            "rarity": "uncommon"
        }
        return json.dumps(mock_item, indent=2), None


# ==============================================================================
# MAIN ITEM GENERATOR
# ==============================================================================

class LLMItemGenerator:
    """
    Main entry point for LLM-based item generation.

    Usage:
        generator = LLMItemGenerator(project_root, materials_db, config)
        result = generator.generate('smithing', recipe_context)
        if result.success:
            item_data = result.item_data
    """

    # Prompt builder registry
    PROMPT_BUILDERS = {
        'smithing': SmithingPromptBuilder,
        'refining': RefiningPromptBuilder,
        'alchemy': AlchemyPromptBuilder,
        'engineering': EngineeringPromptBuilder,
        'adornments': AdornmentPromptBuilder,
        'enchanting': AdornmentPromptBuilder,  # Alias
    }

    def __init__(self, project_root: Path, materials_db,
                 config: Optional[LLMConfig] = None):
        """
        Initialize the item generator.

        Args:
            project_root: Path to Game-1 project root
            materials_db: MaterialDatabase instance
            config: LLM configuration (uses defaults if None)
        """
        self.project_root = Path(project_root)
        self.materials_db = materials_db
        self.config = config or LLMConfig()

        # Lazy initialized components
        self._backend = None
        self._prompt_builders = {}
        self._cache = {}

        print(f"LLMItemGenerator initialized")
        print(f"  Model: {self.config.model}")
        print(f"  Enabled: {self.config.enabled}")

    @property
    def backend(self) -> LLMBackend:
        """Get or create LLM backend"""
        if self._backend is None:
            if self.config.api_key:
                self._backend = AnthropicBackend(self.config.api_key)
            else:
                print("  Warning: No API key - using mock backend")
                self._backend = MockBackend()
        return self._backend

    def get_prompt_builder(self, discipline: str) -> Optional[PromptBuilder]:
        """Get or create prompt builder for discipline"""
        if discipline not in self._prompt_builders:
            builder_class = self.PROMPT_BUILDERS.get(discipline)
            if builder_class:
                self._prompt_builders[discipline] = builder_class()
        return self._prompt_builders.get(discipline)

    def generate(self, discipline: str, interactive_ui) -> GeneratedItem:
        """
        Generate a new item from interactive UI state.

        Args:
            discipline: One of 'smithing', 'adornments', 'alchemy', 'refining', 'engineering'
            interactive_ui: The InteractiveXUI instance with current placement

        Returns:
            GeneratedItem with item_data if successful
        """
        if not self.config.enabled:
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error="LLM generation disabled"
            )

        # Get prompt builder
        builder = self.get_prompt_builder(discipline)
        if not builder:
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=f"No prompt builder for discipline: {discipline}"
            )

        # Extract recipe context from UI
        try:
            recipe_context = self._extract_recipe_context(discipline, interactive_ui)
        except Exception as e:
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=f"Failed to extract recipe context: {e}"
            )

        # Check cache
        cache_key = self._get_cache_key(discipline, recipe_context)
        if self.config.cache_enabled and cache_key in self._cache:
            cached = self._cache[cache_key]
            return GeneratedItem(
                success=True,
                item_data=cached,
                item_id=cached.get('itemId', cached.get('materialId')),
                item_name=cached.get('name'),
                discipline=discipline,
                from_cache=True
            )

        # Build prompts
        try:
            system_prompt = builder.build_system_prompt()
            user_prompt = builder.build_user_prompt(recipe_context, self.materials_db)
        except Exception as e:
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=f"Failed to build prompt: {e}"
            )

        # Call LLM
        print(f"Generating item for {discipline}...")
        response_text, error = self.backend.generate(
            system_prompt, user_prompt, self.config
        )

        if error:
            if self.config.use_fallback_on_error:
                return self._generate_fallback(discipline, recipe_context)
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=error
            )

        # Parse response
        try:
            item_data = builder.parse_response(response_text)

            # Validate required fields
            item_id = item_data.get('itemId', item_data.get('materialId'))
            if not item_id:
                raise ValueError("Missing itemId/materialId in response")

            # Cache result
            if self.config.cache_enabled:
                self._cache[cache_key] = item_data

            return GeneratedItem(
                success=True,
                item_data=item_data,
                item_id=item_id,
                item_name=item_data.get('name'),
                discipline=discipline
            )

        except Exception as e:
            if self.config.use_fallback_on_error:
                return self._generate_fallback(discipline, recipe_context)
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=f"Failed to parse response: {e}"
            )

    def _extract_recipe_context(self, discipline: str, ui) -> Dict:
        """Extract recipe context from interactive UI state"""
        context = {
            'station_tier': getattr(ui, 'station_tier', 1)
        }

        if discipline == 'smithing':
            # Extract grid placements
            inputs = []
            for (x, y), placed_mat in ui.grid.items():
                # Check if this material already in inputs
                found = False
                for inp in inputs:
                    if inp['materialId'] == placed_mat.item_id:
                        inp['quantity'] += 1
                        found = True
                        break
                if not found:
                    inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': 1
                    })
            context['inputs'] = inputs

        elif discipline == 'adornments':
            # Extract vertices
            vertices = {}
            for coord_key, placed_mat in ui.vertices.items():
                vertices[coord_key] = {'materialId': placed_mat.item_id}
            context['vertices'] = vertices
            context['shapes'] = [
                {'type': s['type'], 'vertices': s['vertices']}
                for s in ui.shapes
            ]

        elif discipline == 'alchemy':
            # Extract slot ingredients
            ingredients = []
            for slot_idx, placed_mat in enumerate(ui.slots):
                if placed_mat:
                    ingredients.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            context['ingredients'] = ingredients

        elif discipline == 'refining':
            # Extract core and surrounding slots
            core_inputs = []
            for placed_mat in ui.core_slots:
                if placed_mat:
                    core_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            context['core_inputs'] = core_inputs

            surrounding_inputs = []
            for placed_mat in ui.surrounding_slots:
                if placed_mat:
                    surrounding_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            context['surrounding_inputs'] = surrounding_inputs

        elif discipline == 'engineering':
            # Extract slot assignments
            slots = []
            for slot_type, materials in ui.slots.items():
                for placed_mat in materials:
                    slots.append({
                        'type': slot_type,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            context['slots'] = slots

        return context

    def _get_cache_key(self, discipline: str, recipe_context: Dict) -> str:
        """Generate cache key from recipe context"""
        # Create deterministic string from context
        context_str = json.dumps(recipe_context, sort_keys=True)
        return f"{discipline}:{hashlib.md5(context_str.encode()).hexdigest()}"

    def _generate_fallback(self, discipline: str, recipe_context: Dict) -> GeneratedItem:
        """Generate a simple fallback item when LLM fails"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Determine tier from materials
        max_tier = 1
        all_materials = []

        for key in ['inputs', 'ingredients', 'core_inputs', 'surrounding_inputs', 'slots']:
            if key in recipe_context:
                for item in recipe_context[key]:
                    mat_id = item.get('materialId')
                    if mat_id:
                        all_materials.append(mat_id)
                        mat = self.materials_db.get_material(mat_id) if hasattr(self.materials_db, 'get_material') else None
                        if mat:
                            max_tier = max(max_tier, mat.tier)

        if discipline in ['smithing', 'engineering']:
            item_data = {
                "metadata": {
                    "narrative": "A unique invention crafted with unusual techniques.",
                    "tags": ["invented", "unique"]
                },
                "itemId": f"invented_{discipline}_{timestamp}",
                "name": f"Invented {discipline.title()} Item",
                "category": "equipment",
                "type": "weapon" if discipline == 'smithing' else "device",
                "tier": max_tier,
                "rarity": "uncommon",
                "flags": {
                    "stackable": False,
                    "equippable": discipline == 'smithing',
                    "placeable": discipline == 'engineering'
                }
            }
        elif discipline == 'alchemy':
            item_data = {
                "metadata": {
                    "narrative": "A mysterious potion with unknown properties.",
                    "tags": ["potion", "invented"]
                },
                "itemId": f"invented_potion_{timestamp}",
                "name": "Mysterious Potion",
                "category": "consumable",
                "type": "potion",
                "tier": max_tier,
                "rarity": "uncommon",
                "effect": "Unknown effect",
                "stackSize": 20,
                "flags": {
                    "stackable": True,
                    "consumable": True
                }
            }
        elif discipline == 'refining':
            item_data = {
                "metadata": {
                    "narrative": "A refined material with unique properties.",
                    "tags": ["refined", "invented"]
                },
                "materialId": f"invented_material_{timestamp}",
                "name": "Refined Material",
                "tier": max_tier,
                "rarity": "uncommon",
                "category": "metal"
            }
        else:  # adornments
            item_data = {
                "metadata": {
                    "narrative": "A magical accessory with mysterious enchantments.",
                    "tags": ["accessory", "invented"]
                },
                "itemId": f"invented_accessory_{timestamp}",
                "name": "Mysterious Accessory",
                "category": "equipment",
                "type": "accessory",
                "tier": max_tier,
                "rarity": "uncommon",
                "slot": "accessory"
            }

        return GeneratedItem(
            success=True,
            item_data=item_data,
            item_id=item_data.get('itemId', item_data.get('materialId')),
            item_name=item_data.get('name'),
            discipline=discipline,
            error="Used fallback generation (LLM unavailable)"
        )

    def update_config(self, **kwargs):
        """Update configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"Updated LLM config: {key} = {value}")

        # Clear backend if API key changed
        if 'api_key' in kwargs:
            self._backend = None

    def clear_cache(self):
        """Clear the item cache"""
        self._cache.clear()
        print("LLM item cache cleared")


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

_item_generator: Optional[LLMItemGenerator] = None


def get_item_generator() -> Optional[LLMItemGenerator]:
    """Get the global item generator instance"""
    return _item_generator


def init_item_generator(project_root: Path, materials_db,
                        config: Optional[LLMConfig] = None) -> LLMItemGenerator:
    """Initialize and return the global item generator"""
    global _item_generator
    _item_generator = LLMItemGenerator(project_root, materials_db, config)
    return _item_generator
