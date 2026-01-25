"""
LLM Item Generator - Creates new items from validated recipes

Uses Claude API to generate item definitions based on:
- Recipe placement (materials and quantities)
- Station type and tier
- Material properties and narratives

Design principles:
- Uses actual prompts from Fewshot_llm directory
- Follows the exact JSON schema expected by the game
- Robust fallbacks if API unavailable
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import hashlib


# ==============================================================================
# DEBUG LOGGING
# ==============================================================================

class LLMDebugLogger:
    """Logs LLM input/output for debugging"""

    def __init__(self, log_dir: str = "llm_debug_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.enabled = True

    def log_request(self, discipline: str, system_prompt: str, user_prompt: str,
                    response: str, error: Optional[str] = None):
        """Log a complete LLM request/response cycle"""
        if not self.enabled:
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{timestamp}_{discipline}.json"
        filepath = self.log_dir / filename

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "discipline": discipline,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": response,
            "error": error
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            print(f"  LLM debug log saved: {filepath}")
        except Exception as e:
            print(f"  Warning: Failed to save LLM debug log: {e}")


# Global debug logger instance
_llm_debug_logger: Optional[LLMDebugLogger] = None


def get_llm_debug_logger() -> LLMDebugLogger:
    """Get or create the global debug logger"""
    global _llm_debug_logger
    if _llm_debug_logger is None:
        _llm_debug_logger = LLMDebugLogger()
    return _llm_debug_logger


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class LLMConfig:
    """Configuration for LLM item generation"""
    api_key: str = ""  # Set via environment or explicitly
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

    # Few-shot settings
    max_few_shot_examples: int = 3


# ==============================================================================
# LOADING STATE (Thread-safe for UI indicator)
# ==============================================================================

class LoadingState:
    """Thread-safe loading state for UI indicators"""

    def __init__(self):
        self._lock = threading.Lock()
        self._is_loading = False
        self._message = ""
        self._progress = 0.0  # 0.0 to 1.0

    @property
    def is_loading(self) -> bool:
        with self._lock:
            return self._is_loading

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    @property
    def progress(self) -> float:
        with self._lock:
            return self._progress

    def start(self, message: str = "Loading..."):
        with self._lock:
            self._is_loading = True
            self._message = message
            self._progress = 0.0

    def update(self, message: str = None, progress: float = None):
        with self._lock:
            if message is not None:
                self._message = message
            if progress is not None:
                self._progress = min(1.0, max(0.0, progress))

    def finish(self):
        with self._lock:
            self._is_loading = False
            self._message = ""
            self._progress = 1.0


# Global loading state instance
_loading_state = LoadingState()


def get_loading_state() -> LoadingState:
    """Get the global loading state instance"""
    return _loading_state


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

    # Recipe data for save system
    recipe_inputs: Optional[List[Dict]] = None
    station_tier: int = 1
    narrative: str = ""

    @property
    def is_error(self) -> bool:
        return not self.success


# ==============================================================================
# PROMPT LOADER - Uses actual Fewshot_llm files
# ==============================================================================

class FewshotPromptLoader:
    """Loads prompts and examples from the Fewshot_llm directory"""

    # Discipline to system prompt number mapping
    DISCIPLINE_TO_SYSTEM = {
        'smithing': '1',
        'refining': '2',
        'alchemy': '3',
        'engineering': '4',
        'adornments': '5',
        'enchanting': '5',  # Alias
    }

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.fewshot_dir = self.project_root / "Scaled JSON Development" / "LLM Training Data" / "Fewshot_llm"

        self._system_prompts = {}
        self._few_shot_examples = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Load prompts and examples if not already loaded"""
        if self._loaded:
            return

        # Load system prompts
        prompts_dir = self.fewshot_dir / "prompts" / "system_prompts"
        if prompts_dir.exists():
            for discipline, system_num in self.DISCIPLINE_TO_SYSTEM.items():
                prompt_file = prompts_dir / f"system_{system_num}.txt"
                if prompt_file.exists():
                    try:
                        with open(prompt_file, 'r', encoding='utf-8') as f:
                            self._system_prompts[discipline] = f.read()
                        print(f"  Loaded system prompt for {discipline}")
                    except Exception as e:
                        print(f"  Warning: Failed to load {prompt_file}: {e}")

        # Load few-shot examples
        examples_file = self.fewshot_dir / "examples" / "few_shot_examples.json"
        if examples_file.exists():
            try:
                with open(examples_file, 'r', encoding='utf-8') as f:
                    all_examples = json.load(f)

                # Map examples to disciplines
                for discipline, system_num in self.DISCIPLINE_TO_SYSTEM.items():
                    if system_num in all_examples:
                        self._few_shot_examples[discipline] = all_examples[system_num]
                        print(f"  Loaded {len(all_examples[system_num])} examples for {discipline}")

            except Exception as e:
                print(f"  Warning: Failed to load few-shot examples: {e}")

        self._loaded = True

    def get_system_prompt(self, discipline: str) -> str:
        """Get system prompt for a discipline"""
        self._ensure_loaded()
        return self._system_prompts.get(discipline, self._get_fallback_system_prompt(discipline))

    def get_few_shot_examples(self, discipline: str, max_examples: int = 3) -> List[Dict]:
        """Get few-shot examples for a discipline"""
        self._ensure_loaded()
        examples = self._few_shot_examples.get(discipline, [])
        return examples[:max_examples]

    def _get_fallback_system_prompt(self, discipline: str) -> str:
        """Fallback system prompt if file not found"""
        return f"""You are a crafting expert for an action fantasy sandbox RPG.
Given {discipline} recipes with materials and metadata, generate complete item definitions.
Return ONLY valid JSON matching the game's expected schema.

Important:
- Use snake_case for IDs (e.g., iron_sword)
- Use Title Case for names (e.g., Iron Sword)
- Include metadata.narrative and metadata.tags
- Match tier ranges for stats
"""


# ==============================================================================
# LLM BACKEND
# ==============================================================================

class AnthropicBackend:
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


class MockBackend:
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
            "rarity": "uncommon",
            "slot": "mainHand",
            "effectTags": ["physical", "slashing", "single"],
            "effectParams": {"baseDamage": 15},
            "statMultipliers": {"damage": 1.0, "attackSpeed": 1.0, "durability": 1.0, "weight": 1.0},
            "requirements": {"level": 1, "stats": {}},
            "flags": {"stackable": False, "equippable": True, "repairable": True}
        }
        return json.dumps(mock_item, indent=2), None


# ==============================================================================
# MAIN ITEM GENERATOR
# ==============================================================================

class LLMItemGenerator:
    """
    Main entry point for LLM-based item generation.

    Uses actual prompts from Fewshot_llm directory.
    """

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

        # Load prompts from Fewshot_llm
        self.prompt_loader = FewshotPromptLoader(project_root)

        # Lazy initialized components
        self._backend = None
        self._cache = {}

        print(f"LLMItemGenerator initialized")
        print(f"  Model: {self.config.model}")
        print(f"  Enabled: {self.config.enabled}")

    @property
    def backend(self):
        """Get or create LLM backend"""
        if self._backend is None:
            api_key = self.config.api_key or os.environ.get('ANTHROPIC_API_KEY', '')
            if api_key:
                self._backend = AnthropicBackend(api_key)
            else:
                print("  Warning: No API key - using mock backend")
                self._backend = MockBackend()
        return self._backend

    def generate(self, discipline: str, interactive_ui, narrative: str = "") -> GeneratedItem:
        """
        Generate a new item from interactive UI state.

        Args:
            discipline: One of 'smithing', 'adornments', 'alchemy', 'refining', 'engineering'
            interactive_ui: The InteractiveXUI instance with current placement
            narrative: Optional player-provided description of desired item

        Returns:
            GeneratedItem with item_data if successful
        """
        if not self.config.enabled:
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error="LLM generation disabled"
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
            recipe_inputs = self._extract_recipe_inputs(recipe_context)
            station_tier = recipe_context.get('station_tier', 1)
            return GeneratedItem(
                success=True,
                item_data=cached,
                item_id=cached.get('itemId', cached.get('materialId')),
                item_name=cached.get('name'),
                discipline=discipline,
                from_cache=True,
                recipe_inputs=recipe_inputs,
                station_tier=station_tier,
                narrative=narrative
            )

        # Build prompts
        system_prompt = self.prompt_loader.get_system_prompt(discipline)
        user_prompt = self._build_user_prompt(discipline, recipe_context, narrative)

        # Call LLM
        print(f"Generating item for {discipline}...")
        response_text, error = self.backend.generate(
            system_prompt, user_prompt, self.config
        )

        # Log input/output for debugging
        debug_logger = get_llm_debug_logger()
        debug_logger.log_request(
            discipline=discipline,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response_text,
            error=error
        )

        if error:
            if self.config.use_fallback_on_error:
                return self._generate_fallback(discipline, recipe_context, narrative)
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=error
            )

        # Parse response
        try:
            item_data = self._parse_response(response_text)

            # Validate required fields
            item_id = item_data.get('itemId', item_data.get('materialId'))
            if not item_id:
                raise ValueError("Missing itemId/materialId in response")

            # Cache result
            if self.config.cache_enabled:
                self._cache[cache_key] = item_data

            # Extract recipe inputs for persistence
            recipe_inputs = self._extract_recipe_inputs(recipe_context)
            station_tier = recipe_context.get('station_tier', 1)

            return GeneratedItem(
                success=True,
                item_data=item_data,
                item_id=item_id,
                item_name=item_data.get('name'),
                discipline=discipline,
                recipe_inputs=recipe_inputs,
                station_tier=station_tier,
                narrative=narrative
            )

        except Exception as e:
            print(f"  Parse error: {e}")
            if self.config.use_fallback_on_error:
                return self._generate_fallback(discipline, recipe_context, narrative)
            return GeneratedItem(
                success=False,
                discipline=discipline,
                error=f"Failed to parse response: {e}"
            )

    def _build_user_prompt(self, discipline: str, recipe_context: Dict, narrative: str = "") -> str:
        """Build user prompt with recipe context and few-shot examples"""
        # Get few-shot examples
        examples = self.prompt_loader.get_few_shot_examples(discipline, self.config.max_few_shot_examples)

        # Build examples section
        examples_text = ""
        if examples:
            examples_text = "\n\nExamples:\n"
            for i, ex in enumerate(examples, 1):
                examples_text += f"\nExample {i} Input:\n{ex.get('input', '')}\n"
                examples_text += f"\nExample {i} Output:\n{ex.get('output', '')}\n"

        # Build recipe context JSON
        recipe_json = json.dumps(recipe_context, indent=2)

        # Build the user prompt
        prompt = f"""Create an item definition for this {discipline} recipe:

{recipe_json}

Return ONLY the JSON item definition, no extra text.{examples_text}"""

        return prompt

    def _extract_recipe_context(self, discipline: str, ui) -> Dict:
        """Extract recipe context from interactive UI state"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        context = {
            'recipeId': f"invented_{timestamp}",
            'stationTier': getattr(ui, 'station_tier', 1),
            'stationType': discipline
        }

        if discipline == 'smithing':
            # Extract grid placements
            inputs = []
            material_counts = {}
            for (x, y), placed_mat in ui.grid.items():
                mat_id = placed_mat.item_id
                material_counts[mat_id] = material_counts.get(mat_id, 0) + 1

            for mat_id, qty in material_counts.items():
                mat_data = self._get_material_data(mat_id)
                inputs.append({
                    'materialId': mat_id,
                    'quantity': qty,
                    'materialName': mat_data.get('name', mat_id.replace('_', ' ').title()),
                    'materialTier': mat_data.get('tier', 1),
                    'materialRarity': mat_data.get('rarity', 'common'),
                    'materialNarrative': mat_data.get('narrative', ''),
                    'materialTags': mat_data.get('tags', [])
                })
            context['inputs'] = inputs

        elif discipline == 'adornments' or discipline == 'enchanting':
            # Extract vertices
            vertices = {}
            for coord_key, placed_mat in ui.vertices.items():
                mat_data = self._get_material_data(placed_mat.item_id)
                vertices[coord_key] = {
                    'materialId': placed_mat.item_id,
                    'materialName': mat_data.get('name', placed_mat.item_id),
                    'materialTier': mat_data.get('tier', 1),
                    'materialRarity': mat_data.get('rarity', 'common'),
                    'materialTags': mat_data.get('tags', [])
                }
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
                    mat_data = self._get_material_data(placed_mat.item_id)
                    ingredients.append({
                        'slot': slot_idx + 1,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity,
                        'materialName': mat_data.get('name', placed_mat.item_id),
                        'materialTier': mat_data.get('tier', 1),
                        'materialRarity': mat_data.get('rarity', 'common'),
                        'materialTags': mat_data.get('tags', [])
                    })
            context['ingredients'] = ingredients

        elif discipline == 'refining':
            # Extract core and surrounding slots
            core_inputs = []
            for placed_mat in ui.core_slots:
                if placed_mat:
                    mat_data = self._get_material_data(placed_mat.item_id)
                    core_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity,
                        'materialName': mat_data.get('name', placed_mat.item_id),
                        'materialTier': mat_data.get('tier', 1),
                        'materialRarity': mat_data.get('rarity', 'common'),
                        'materialCategory': mat_data.get('category', 'unknown')
                    })
            context['coreInputs'] = core_inputs

            surrounding_inputs = []
            for placed_mat in ui.surrounding_slots:
                if placed_mat:
                    mat_data = self._get_material_data(placed_mat.item_id)
                    surrounding_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity,
                        'materialName': mat_data.get('name', placed_mat.item_id),
                        'materialTier': mat_data.get('tier', 1),
                        'materialRarity': mat_data.get('rarity', 'common'),
                        'materialCategory': mat_data.get('category', 'unknown')
                    })
            context['surroundingInputs'] = surrounding_inputs

        elif discipline == 'engineering':
            # Extract slot assignments
            slots = []
            for slot_type, materials in ui.slots.items():
                for placed_mat in materials:
                    mat_data = self._get_material_data(placed_mat.item_id)
                    slots.append({
                        'slotType': slot_type,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity,
                        'materialName': mat_data.get('name', placed_mat.item_id),
                        'materialTier': mat_data.get('tier', 1),
                        'materialRarity': mat_data.get('rarity', 'common')
                    })
            context['slots'] = slots

        # Add narrative
        context['narrative'] = "Player-invented recipe. Create an appropriate item."

        return context

    def _get_material_data(self, mat_id: str) -> Dict:
        """Get material data for prompt enrichment"""
        if hasattr(self.materials_db, 'get_material'):
            mat = self.materials_db.get_material(mat_id)
            if mat:
                tags = []
                if hasattr(mat, 'properties') and mat.properties:
                    tags = mat.properties.get('tags', [])
                return {
                    'name': mat.name if hasattr(mat, 'name') else mat_id,
                    'tier': mat.tier,
                    'rarity': getattr(mat, 'rarity', 'common'),
                    'narrative': getattr(mat, 'description', ''),
                    'category': mat.category if hasattr(mat, 'category') else 'unknown',
                    'tags': tags
                }
        return {'name': mat_id, 'tier': 1, 'rarity': 'common', 'narrative': '', 'category': 'unknown', 'tags': []}

    def _parse_response(self, response_text: str) -> Dict:
        """Parse LLM response into item data"""
        text = response_text.strip()

        # Try direct parse first
        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Find JSON block
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")

        raise ValueError("No valid JSON found in response")

    def _get_cache_key(self, discipline: str, recipe_context: Dict) -> str:
        """Generate cache key from recipe context"""
        context_str = json.dumps(recipe_context, sort_keys=True)
        return f"{discipline}:{hashlib.md5(context_str.encode()).hexdigest()}"

    def _extract_recipe_inputs(self, recipe_context: Dict) -> List[Dict]:
        """Extract recipe inputs from context in a unified format"""
        inputs = []
        for key in ['inputs', 'ingredients', 'coreInputs', 'surroundingInputs', 'slots']:
            if key in recipe_context:
                for item in recipe_context[key]:
                    mat_id = item.get('materialId')
                    qty = item.get('quantity', 1)
                    if mat_id:
                        inputs.append({'materialId': mat_id, 'quantity': qty})
        return inputs

    def extract_placement_data(self, discipline: str, ui) -> Dict:
        """
        Extract full placement data from interactive UI for saving/reloading.

        Returns a dict that can be used to recreate the recipe placement.
        """
        placement = {
            'discipline': discipline,
            'stationTier': getattr(ui, 'station_tier', 1)
        }

        if discipline == 'smithing':
            # Extract grid placement map {"x,y": "material_id"}
            placement_map = {}
            for (x, y), placed_mat in ui.grid.items():
                placement_map[f"{x},{y}"] = placed_mat.item_id
            placement['placementMap'] = placement_map
            placement['gridSize'] = f"{getattr(ui, 'grid_size', 3)}x{getattr(ui, 'grid_size', 3)}"

        elif discipline in ['adornments', 'enchanting']:
            # Extract vertices and shapes
            vertices = {}
            for coord_key, placed_mat in getattr(ui, 'vertices', {}).items():
                vertices[coord_key] = placed_mat.item_id
            placement['vertices'] = vertices
            placement['shapes'] = [
                {'type': s.get('type'), 'vertices': s.get('vertices', [])}
                for s in getattr(ui, 'shapes', [])
            ]
            placement['gridSize'] = f"{getattr(ui, 'grid_size', 8)}x{getattr(ui, 'grid_size', 8)}"

        elif discipline == 'alchemy':
            # Extract slot ingredients with positions
            ingredients = []
            for slot_idx, placed_mat in enumerate(getattr(ui, 'slots', [])):
                if placed_mat:
                    ingredients.append({
                        'slot': slot_idx,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            placement['ingredients'] = ingredients
            placement['numSlots'] = len(getattr(ui, 'slots', []))

        elif discipline == 'refining':
            # Extract core and surrounding slots
            core_inputs = []
            for idx, placed_mat in enumerate(getattr(ui, 'core_slots', [])):
                if placed_mat:
                    core_inputs.append({
                        'slot': idx,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            placement['coreInputs'] = core_inputs

            surrounding_inputs = []
            for idx, placed_mat in enumerate(getattr(ui, 'surrounding_slots', [])):
                if placed_mat:
                    surrounding_inputs.append({
                        'slot': idx,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            placement['surroundingInputs'] = surrounding_inputs
            placement['numCoreSlots'] = len(getattr(ui, 'core_slots', []))
            placement['numSurroundingSlots'] = len(getattr(ui, 'surrounding_slots', []))

        elif discipline == 'engineering':
            # Extract slot type assignments
            slots = []
            for slot_type, materials in getattr(ui, 'slots', {}).items():
                for idx, placed_mat in enumerate(materials):
                    slots.append({
                        'slotType': slot_type,
                        'index': idx,
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })
            placement['slots'] = slots
            placement['slotTypes'] = list(getattr(ui, 'slots', {}).keys())

        return placement

    def calculate_minimum_tier(self, discipline: str, ui) -> int:
        """
        Calculate the minimum station tier required for this recipe based on
        the discipline-specific rules.

        Returns the minimum tier (1-4) that can craft this recipe.
        """
        # Tier rules by discipline
        if discipline == 'smithing':
            # Smithing: based on grid size needed
            # T1: 3x3, T2: 5x5, T3: 7x7, T4: 9x9
            if not ui.grid:
                return 1
            max_x = max(x for (x, y) in ui.grid.keys()) if ui.grid else 0
            max_y = max(y for (x, y) in ui.grid.keys()) if ui.grid else 0
            min_x = min(x for (x, y) in ui.grid.keys()) if ui.grid else 0
            min_y = min(y for (x, y) in ui.grid.keys()) if ui.grid else 0
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            grid_needed = max(width, height)

            if grid_needed <= 3:
                return 1
            elif grid_needed <= 5:
                return 2
            elif grid_needed <= 7:
                return 3
            else:
                return 4

        elif discipline in ['adornments', 'enchanting']:
            # Adornments: based on grid size - T1: 8x8, T2: 10x10, T3: 12x12, T4: 14x14
            vertices = getattr(ui, 'vertices', {})
            if not vertices:
                return 1
            # Grid uses coordinates like "0,1", "-2,3", etc. around center
            coords = []
            for key in vertices.keys():
                if isinstance(key, str) and ',' in key:
                    parts = key.split(',')
                    coords.append((int(parts[0]), int(parts[1])))
                elif isinstance(key, tuple):
                    coords.append(key)
            if not coords:
                return 1
            max_coord = max(max(abs(x), abs(y)) for x, y in coords)
            grid_needed = max_coord * 2 + 1

            if grid_needed <= 8:
                return 1
            elif grid_needed <= 10:
                return 2
            elif grid_needed <= 12:
                return 3
            else:
                return 4

        elif discipline == 'refining':
            # Refining: T1: 1+2=3, T2: 1+4=5, T3: 2+5=7, T4: 3+6=9
            core_count = sum(1 for s in getattr(ui, 'core_slots', []) if s is not None)
            surrounding_count = sum(1 for s in getattr(ui, 'surrounding_slots', []) if s is not None)

            # Check which tier can support these counts
            tier_limits = {
                1: (1, 2),  # max 1 core, 2 surrounding
                2: (1, 4),  # max 1 core, 4 surrounding
                3: (2, 5),  # max 2 core, 5 surrounding
                4: (3, 6),  # max 3 core, 6 surrounding
            }
            for tier in [1, 2, 3, 4]:
                max_core, max_surr = tier_limits[tier]
                if core_count <= max_core and surrounding_count <= max_surr:
                    return tier
            return 4

        elif discipline == 'alchemy':
            # Alchemy: T1: 2 slots, T2: 3 slots, T3: 4 slots, T4: 6 slots
            slot_count = sum(1 for s in getattr(ui, 'slots', []) if s is not None)

            if slot_count <= 2:
                return 1
            elif slot_count <= 3:
                return 2
            elif slot_count <= 4:
                return 3
            else:
                return 4

        elif discipline == 'engineering':
            # Engineering: T1-2: 3 types, T3-4: 5 types
            slot_types_used = set()
            for slot_type, materials in getattr(ui, 'slots', {}).items():
                if materials:  # Has at least one material
                    slot_types_used.add(slot_type)

            if len(slot_types_used) <= 3:
                return 1
            else:
                return 3

        return 1  # Default

    def _generate_fallback(self, discipline: str, recipe_context: Dict, narrative: str = "") -> GeneratedItem:
        """Generate a simple fallback item when LLM fails"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Determine tier from materials
        max_tier = 1
        all_materials = []

        for key in ['inputs', 'ingredients', 'coreInputs', 'surroundingInputs', 'slots']:
            if key in recipe_context:
                for item in recipe_context[key]:
                    mat_id = item.get('materialId')
                    if mat_id:
                        all_materials.append(mat_id)
                        mat = self.materials_db.get_material(mat_id) if hasattr(self.materials_db, 'get_material') else None
                        if mat:
                            max_tier = max(max_tier, mat.tier)

        if discipline == 'smithing':
            item_data = {
                "metadata": {
                    "narrative": "A unique invention crafted with unusual techniques.",
                    "tags": ["invented", "melee", "weapon"]
                },
                "itemId": f"invented_weapon_{timestamp}",
                "name": "Invented Weapon",
                "category": "equipment",
                "type": "weapon",
                "subtype": "sword",
                "tier": max_tier,
                "rarity": "uncommon",
                "range": 1,
                "slot": "mainHand",
                "effectTags": ["physical", "slashing", "single"],
                "effectParams": {"baseDamage": 15 * max_tier},
                "statMultipliers": {"damage": 1.0, "attackSpeed": 1.0, "durability": 1.0, "weight": 1.0},
                "requirements": {"level": max(1, (max_tier - 1) * 5), "stats": {}},
                "flags": {"stackable": False, "equippable": True, "repairable": True}
            }
        elif discipline == 'engineering':
            item_data = {
                "metadata": {
                    "narrative": "A mechanical device of unusual design.",
                    "tags": ["device", "invented", "mechanical"]
                },
                "itemId": f"invented_device_{timestamp}",
                "name": "Invented Device",
                "category": "device",
                "type": "turret",
                "subtype": "projectile",
                "tier": max_tier,
                "rarity": "uncommon",
                "stackSize": 5,
                "effectTags": ["physical", "piercing", "single"],
                "effectParams": {"baseDamage": 20 * max_tier, "range": 8},
                "requirements": {"level": max(1, (max_tier - 1) * 5), "stats": {}},
                "flags": {"stackable": True, "placeable": True, "repairable": False}
            }
        elif discipline == 'alchemy':
            item_data = {
                "metadata": {
                    "narrative": "A mysterious potion with unknown properties.",
                    "tags": ["potion", "consumable", "invented"]
                },
                "itemId": f"invented_potion_{timestamp}",
                "name": "Mysterious Potion",
                "category": "consumable",
                "type": "potion",
                "subtype": "utility",
                "tier": max_tier,
                "rarity": "uncommon",
                "stackSize": 10,
                "effect": "Unknown effect",
                "effectTags": ["healing", "instant", "self"],
                "effectParams": {"healing": {"heal_amount": 50 * max_tier}},
                "duration": 0,
                "statMultipliers": {"weight": 0.3},
                "requirements": {"level": max(1, (max_tier - 1) * 5), "stats": {}},
                "flags": {"stackable": True, "consumable": True, "repairable": False}
            }
        elif discipline == 'refining':
            item_data = {
                "metadata": {
                    "narrative": "A refined material with unique properties.",
                    "tags": ["refined", "material", "invented"]
                },
                "materialId": f"invented_material_{timestamp}",
                "itemId": f"invented_material_{timestamp}",
                "name": "Refined Material",
                "category": "metal",
                "type": "material",
                "subtype": "ingot",
                "tier": max_tier,
                "rarity": "uncommon",
                "stackSize": 99,
                "statMultipliers": {"weight": 1.0},
                "requirements": {"level": 1, "stats": {}},
                "flags": {"stackable": True, "consumable": False, "repairable": False}
            }
        else:  # adornments/enchanting
            item_data = {
                "metadata": {
                    "narrative": "A magical accessory with mysterious enchantments.",
                    "tags": ["accessory", "enchanted", "invented"]
                },
                "itemId": f"invented_accessory_{timestamp}",
                "name": "Mysterious Accessory",
                "category": "equipment",
                "type": "accessory",
                "subtype": "ring",
                "tier": max_tier,
                "rarity": "uncommon",
                "slot": "accessory",
                "enchantments": [],
                "stats": {},
                "requirements": {"level": max(1, (max_tier - 1) * 5), "stats": {}},
                "flags": {"stackable": False, "equippable": True, "repairable": True}
            }

        # Extract recipe inputs for persistence
        recipe_inputs = self._extract_recipe_inputs(recipe_context)
        station_tier = recipe_context.get('stationTier', 1)

        return GeneratedItem(
            success=True,
            item_data=item_data,
            item_id=item_data.get('itemId', item_data.get('materialId')),
            item_name=item_data.get('name'),
            discipline=discipline,
            error="Used fallback generation (LLM unavailable)",
            recipe_inputs=recipe_inputs,
            station_tier=station_tier,
            narrative=narrative
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
