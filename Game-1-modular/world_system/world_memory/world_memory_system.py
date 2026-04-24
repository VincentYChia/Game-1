"""World Memory System — main facade coordinating all memory subsystems.

This is the single entry point for the GameEngine. It initializes, updates,
saves, and loads all memory-related subsystems.

Usage:
    memory = WorldMemorySystem()
    memory.initialize(save_dir="saves/", character=character, world=world)
    # In game loop:
    memory.update(dt, game_time, character)
    # On save:
    memory.save()
    # On load:
    memory.load(save_dir)
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, ClassVar, Dict, Optional

from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.event_recorder import EventRecorder
from world_system.world_memory.trigger_manager import TriggerManager
from world_system.world_memory.interpreter import WorldInterpreter
from world_system.world_memory.query import WorldQuery
from world_system.world_memory.retention import EventRetentionManager
from world_system.world_memory.position_sampler import PositionSampler
from world_system.world_memory.stat_store import StatStore
from world_system.world_memory.daily_ledger import DailyLedgerManager
from world_system.world_memory.layer3_manager import Layer3Manager
from world_system.world_memory.layer4_manager import Layer4Manager
from world_system.world_memory.layer5_manager import Layer5Manager
from world_system.world_memory.layer6_manager import Layer6Manager
from world_system.world_memory.layer7_manager import Layer7Manager
from world_system.world_memory.trigger_registry import TriggerRegistry


class WorldMemorySystem:
    """Facade for the entire World Memory System. Singleton."""

    _instance: ClassVar[Optional[WorldMemorySystem]] = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.stat_store: Optional[StatStore] = None
        self.layer_store = None  # LayerStore for per-layer tag-indexed storage
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.trigger_manager: Optional[TriggerManager] = None
        self.event_recorder: Optional[EventRecorder] = None
        self.interpreter: Optional[WorldInterpreter] = None
        self.world_query: Optional[WorldQuery] = None
        self.retention_manager: Optional[EventRetentionManager] = None
        self.position_sampler: Optional[PositionSampler] = None
        self.daily_ledger_manager: Optional[DailyLedgerManager] = None
        self.layer3_manager: Optional[Layer3Manager] = None
        self.layer4_manager: Optional[Layer4Manager] = None
        self.layer5_manager: Optional[Layer5Manager] = None
        self.layer6_manager: Optional[Layer6Manager] = None
        self.layer7_manager: Optional[Layer7Manager] = None
        self.trigger_registry: Optional[TriggerRegistry] = None

        self._initialized: bool = False
        self._game_time: float = 0.0
        self._session_id: str = str(uuid.uuid4())[:8]

    @classmethod
    def get_instance(cls) -> WorldMemorySystem:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        if cls._instance:
            cls._instance.shutdown()
        cls._instance = None

    # ── Initialization ───────────────────────────────────────────────

    def initialize(self, save_dir: str,
                   character=None,
                   world=None,
                   geo_map_path: Optional[str] = None) -> None:
        """Initialize all subsystems.

        Args:
            save_dir: Path to save directory (for SQLite database).
            character: Player Character instance (optional, for entity registration).
            world: WorldSystem instance (optional, for biome data).
            geo_map_path: Path to geographic-map.json (optional).
        """
        if self._initialized:
            return

        print("[WorldMemory] Initializing...")

        # 1. Event Store (SQLite)
        self.event_store = EventStore(save_dir=save_dir)

        # 1b. Stat Store (shares the same SQLite connection)
        self.stat_store = StatStore(conn=self.event_store.connection)

        # Load stat manifest (tags + descriptions for stat name patterns)
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "stat-key-manifest.json"
        )
        loaded = self.stat_store.load_manifest(manifest_path)
        if loaded > 0:
            print(f"[WorldMemory] Loaded {loaded} stat tag patterns from manifest")

        # 1c. Layer Store (per-layer tag-indexed storage for Layers 2-7)
        try:
            from world_system.world_memory.layer_store import LayerStore
            layer_db_path = os.path.join(save_dir, "layer_store.db")
            self.layer_store = LayerStore(db_path=layer_db_path)
            print(f"[WorldMemory] LayerStore initialized: {layer_db_path}")
        except Exception as e:
            print(f"[WorldMemory] LayerStore init failed (non-fatal): {e}")
            self.layer_store = None

        # 2. Geographic Registry
        self.geo_registry = GeographicRegistry.get_instance()
        # Prefer new geographic system's WorldMap if available
        if world and hasattr(world, 'geographic_map') and world.geographic_map:
            self.geo_registry.load_from_world_map(world.geographic_map)
        elif geo_map_path and os.path.exists(geo_map_path):
            self.geo_registry.load_base_map(geo_map_path)
        elif world:
            # Generate from world biome data if available
            self._generate_geography_from_world(world)

        # If still empty, create a minimal default
        if not self.geo_registry.regions:
            self._create_default_geography()

        # 3. Entity Registry
        self.entity_registry = EntityRegistry.get_instance()
        # Register regions as entities
        self.entity_registry.load_from_regions(self.geo_registry)
        # Register NPCs if database is loaded
        self._register_npcs()
        # Register player and wire stat store
        if character:
            self.entity_registry.register_player(character)
            # Wire SQL-backed stat store into the character's stat tracker
            if hasattr(character, 'stat_tracker') and self.stat_store:
                character.stat_tracker.set_store(self.stat_store)

        # 4. Trigger Manager (threshold-based dual-track counting)
        self.trigger_manager = TriggerManager.get_instance()

        # 5. Event Recorder (subscribes to bus)
        self.event_recorder = EventRecorder.get_instance()
        # Pass world_map for setting/population/resource tag enrichment
        _world_map = None
        if world and hasattr(world, 'geographic_map'):
            _world_map = world.geographic_map
        self.event_recorder.initialize(
            self.event_store, self.geo_registry,
            self.entity_registry, self.trigger_manager, self._session_id,
            world_map=_world_map,
        )

        # 6. WMS AI (LLM narration for Layer 2+)
        self.wms_ai = None
        try:
            from world_system.world_memory.wms_ai import WmsAI
            self.wms_ai = WmsAI.get_instance()
            self.wms_ai.initialize()
            print(f"[WorldMemory] WmsAI initialized — {self.wms_ai.stats}")
        except Exception as e:
            print(f"[WorldMemory] WmsAI init failed (non-fatal, templates used): {e}")

        # 7. Interpreter
        self.interpreter = WorldInterpreter.get_instance()
        self.interpreter.initialize(
            self.event_store, self.geo_registry, self.entity_registry,
            layer_store=self.layer_store,
            wms_ai=self.wms_ai,
        )
        # Wire interpreter to recorder
        self.event_recorder.set_interpreter_callback(self.interpreter.on_trigger)

        # 7b. Layer 3 Manager (cross-domain consolidation)
        try:
            self.layer3_manager = Layer3Manager.get_instance()
            self.layer3_manager.initialize(
                layer_store=self.layer_store,
                geo_registry=self.geo_registry,
                wms_ai=self.wms_ai,
            )
            # Wire L3 callback to interpreter so it gets notified of L2 events
            self.interpreter.set_layer3_callback(self.layer3_manager.on_layer2_created)
            print(f"[WorldMemory] Layer3Manager initialized — {self.layer3_manager.stats}")
        except Exception as e:
            print(f"[WorldMemory] Layer3Manager init failed (non-fatal): {e}")
            self.layer3_manager = None

        # 7c. Layer 4 Manager (province summarization)
        try:
            self.trigger_registry = TriggerRegistry.get_instance()
            self.layer4_manager = Layer4Manager.get_instance()
            self.layer4_manager.initialize(
                layer_store=self.layer_store,
                geo_registry=self.geo_registry,
                wms_ai=self.wms_ai,
                trigger_registry=self.trigger_registry,
            )
            # Wire L4 callback to L3 manager so it gets notified of L3 events
            if self.layer3_manager:
                self.layer3_manager.set_layer4_callback(
                    self.layer4_manager.on_layer3_created)
            print(f"[WorldMemory] Layer4Manager initialized — {self.layer4_manager.stats}")
        except Exception as e:
            print(f"[WorldMemory] Layer4Manager init failed (non-fatal): {e}")
            self.layer4_manager = None

        # 7d. Layer 5 Manager (region summarization — game Region tier)
        try:
            if self.trigger_registry is None:
                self.trigger_registry = TriggerRegistry.get_instance()
            self.layer5_manager = Layer5Manager.get_instance()
            self.layer5_manager.initialize(
                layer_store=self.layer_store,
                geo_registry=self.geo_registry,
                wms_ai=self.wms_ai,
                trigger_registry=self.trigger_registry,
            )
            # Wire L5 callback to L4 manager so it gets notified of L4 events
            if self.layer4_manager:
                self.layer4_manager.set_layer5_callback(
                    self.layer5_manager.on_layer4_created)
            print(f"[WorldMemory] Layer5Manager initialized — {self.layer5_manager.stats}")
        except Exception as e:
            print(f"[WorldMemory] Layer5Manager init failed (non-fatal): {e}")
            self.layer5_manager = None

        # 7e. Layer 6 Manager (nation summarization — game Nation tier)
        try:
            if self.trigger_registry is None:
                self.trigger_registry = TriggerRegistry.get_instance()
            self.layer6_manager = Layer6Manager.get_instance()
            self.layer6_manager.initialize(
                layer_store=self.layer_store,
                geo_registry=self.geo_registry,
                wms_ai=self.wms_ai,
                trigger_registry=self.trigger_registry,
            )
            # Wire L6 callback to L5 manager so it gets notified of L5 events
            if self.layer5_manager:
                self.layer5_manager.set_layer6_callback(
                    self.layer6_manager.on_layer5_created)
            print(f"[WorldMemory] Layer6Manager initialized — {self.layer6_manager.stats}")
        except Exception as e:
            print(f"[WorldMemory] Layer6Manager init failed (non-fatal): {e}")
            self.layer6_manager = None

        # 7f. Layer 7 Manager (world summarization — game World tier, singleton)
        try:
            if self.trigger_registry is None:
                self.trigger_registry = TriggerRegistry.get_instance()
            self.layer7_manager = Layer7Manager.get_instance()
            self.layer7_manager.initialize(
                layer_store=self.layer_store,
                geo_registry=self.geo_registry,
                wms_ai=self.wms_ai,
                trigger_registry=self.trigger_registry,
            )
            # Wire L7 callback to L6 manager so it gets notified of L6 events
            if self.layer6_manager:
                self.layer6_manager.set_layer7_callback(
                    self.layer7_manager.on_layer6_created)
            print(f"[WorldMemory] Layer7Manager initialized — {self.layer7_manager.stats}")
        except Exception as e:
            print(f"[WorldMemory] Layer7Manager init failed (non-fatal): {e}")
            self.layer7_manager = None

        # 8. Query Interface
        self.world_query = WorldQuery.get_instance()
        self.world_query.initialize(
            self.entity_registry, self.geo_registry, self.event_store
        )

        # 8. Retention Manager
        self.retention_manager = EventRetentionManager()

        # 9. Position Sampler
        self.position_sampler = PositionSampler()

        # 10. Daily Ledger Manager (tracks game-day boundaries)
        self.daily_ledger_manager = DailyLedgerManager()

        # Restore persisted state
        self._restore_persisted_state()

        self._initialized = True
        print(f"[WorldMemory] Initialized — session {self._session_id}, "
              f"{len(self.geo_registry.regions)} regions, "
              f"{len(self.entity_registry.entities)} entities, "
              f"{self.event_store.get_event_count()} events in store")

    def _generate_geography_from_world(self, world) -> None:
        """Generate geographic regions from WorldSystem biome data."""
        chunk_biomes = {}
        if hasattr(world, "loaded_chunks"):
            for (cx, cy), chunk in world.loaded_chunks.items():
                if hasattr(chunk, "chunk_type"):
                    biome = chunk.chunk_type
                    if hasattr(biome, "value"):
                        biome = biome.value
                    chunk_biomes[(cx, cy)] = str(biome)

        if chunk_biomes:
            chunk_size = 16
            try:
                from core.config import Config
                chunk_size = Config.CHUNK_SIZE
            except ImportError:
                pass
            self.geo_registry.generate_from_biomes(chunk_biomes, chunk_size)

    def _create_default_geography(self) -> None:
        """Create a minimal default geography when no other source is available.

        This fallback is used when no WorldMap exists (e.g. early
        boot, tests). It produces a 3-tier hierarchy (WORLD → PROVINCE
        quadrants → LOCALITY chunks) that skips Nation/Region/District.
        Real gameplay always goes through `load_from_world_map`.
        """
        from world_system.world_memory.geographic_registry import Region, RegionLevel

        world = Region(
            region_id="known_lands",
            name="The Known Lands",
            level=RegionLevel.WORLD,
            bounds_x1=-800, bounds_y1=-800,
            bounds_x2=800, bounds_y2=800,
            description="The explored world.",
        )
        self.geo_registry.regions[world.region_id] = world
        self.geo_registry.world = world

        # Create four provinces covering the quadrants
        provinces = [
            ("province_nw", "Northwestern Reaches", -800, -800, 0, 0),
            ("province_ne", "Northeastern Highlands", 0, -800, 800, 0),
            ("province_sw", "Southwestern Lowlands", -800, 0, 0, 800),
            ("province_se", "Southeastern Frontier", 0, 0, 800, 800),
        ]
        for pid, name, x1, y1, x2, y2 in provinces:
            prov = Region(
                region_id=pid, name=name, level=RegionLevel.PROVINCE,
                bounds_x1=x1, bounds_y1=y1, bounds_x2=x2, bounds_y2=y2,
                parent_id="known_lands",
            )
            self.geo_registry.regions[pid] = prov
            world.child_ids.append(pid)

        # Create basic localities around spawn
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                loc_id = f"loc_{dx}_{dy}"
                tile_x = dx * 16
                tile_y = dy * 16
                loc = Region(
                    region_id=loc_id,
                    name=f"Area ({dx},{dy})",
                    level=RegionLevel.LOCALITY,
                    bounds_x1=tile_x, bounds_y1=tile_y,
                    bounds_x2=tile_x + 15, bounds_y2=tile_y + 15,
                    parent_id=self._province_for_pos(tile_x, tile_y),
                    biome_primary="unknown",
                    tags=["terrain:unknown"],
                )
                self.geo_registry.regions[loc_id] = loc
                # Add to parent
                parent = self.geo_registry.regions.get(loc.parent_id)
                if parent:
                    parent.child_ids.append(loc_id)

        self.geo_registry._invalidate_cache()

    def _province_for_pos(self, x: float, y: float) -> str:
        if x < 0 and y < 0:
            return "province_nw"
        if x >= 0 and y < 0:
            return "province_ne"
        if x < 0 and y >= 0:
            return "province_sw"
        return "province_se"

    def _register_npcs(self) -> None:
        """Register NPCs from the game's NPC database."""
        try:
            from data.databases.npc_db import NPCDatabase
            npc_db = NPCDatabase.get_instance()
            if npc_db.loaded:
                count = self.entity_registry.load_from_npcs(
                    npc_db, self.geo_registry
                )
                print(f"[WorldMemory] Registered {count} NPCs")
        except (ImportError, Exception) as e:
            print(f"[WorldMemory] NPC registration skipped: {e}")

    def _restore_persisted_state(self) -> None:
        """Restore entity and region states from SQLite."""
        if not self.event_store:
            return
        # Restore region states
        region_states = self.event_store.load_all_region_states()
        for region_id, state_data in region_states.items():
            if region_id in self.geo_registry.regions:
                from world_system.world_memory.geographic_registry import RegionState
                self.geo_registry.regions[region_id].state = RegionState.from_dict(state_data)

    # ── Per-frame update ─────────────────────────────────────────────

    def update(self, dt: float, game_time: float, character=None) -> None:
        """Called each frame from the game loop.

        Args:
            dt: Delta time in seconds.
            game_time: Current game time.
            character: Player character (for position tracking).
        """
        if not self._initialized:
            return

        self._game_time = game_time
        self.event_recorder.set_game_time(game_time)

        # Update player position in entity registry
        if character and hasattr(character, "position"):
            self.entity_registry.update_player_position(
                character.position.x, character.position.y
            )

            # Position sampling
            health_pct = character.health / max(character.max_health, 1)
            self.position_sampler.update(
                time.time(),
                character.position.x,
                character.position.y,
                health_pct=health_pct,
            )

        # Check game-day boundary for daily ledger computation
        if self.daily_ledger_manager:
            ended_day = self.daily_ledger_manager.check_day_boundary(game_time)
            if ended_day is not None:
                try:
                    day_events = self.event_store.query(
                        since_game_time=ended_day,
                        before_game_time=ended_day + 1.0,
                        limit=10000,
                    )
                    ledger = self.daily_ledger_manager.compute_ledger(
                        ended_day, day_events
                    )
                    self.daily_ledger_manager.save_ledger(ledger, self.event_store)

                    # Update meta-daily stats
                    all_ledgers = self.daily_ledger_manager.load_ledgers(
                        self.event_store
                    )
                    meta = self.daily_ledger_manager.update_meta_stats(all_ledgers)
                    self.event_store.store_meta_daily_stats(meta.to_json())
                except Exception as e:
                    print(f"[WorldMemory] Daily ledger error: {e}")

        # Layer 3 consolidation check
        if self.layer3_manager and self.layer3_manager.should_run():
            try:
                self.layer3_manager.run_consolidation(game_time)
            except Exception as e:
                print(f"[WorldMemory] Layer 3 consolidation error: {e}")

        # Layer 4 province summarization check
        if self.layer4_manager and self.layer4_manager.should_run():
            try:
                self.layer4_manager.run_summarization(game_time)
            except Exception as e:
                print(f"[WorldMemory] Layer 4 summarization error: {e}")

        # Layer 5 region summarization check
        if self.layer5_manager and self.layer5_manager.should_run():
            try:
                self.layer5_manager.run_summarization(game_time)
            except Exception as e:
                print(f"[WorldMemory] Layer 5 summarization error: {e}")

        # Layer 6 nation summarization check
        if self.layer6_manager and self.layer6_manager.should_run():
            try:
                self.layer6_manager.run_summarization(game_time)
            except Exception as e:
                print(f"[WorldMemory] Layer 6 summarization error: {e}")

        # Layer 7 world summarization check
        if self.layer7_manager and self.layer7_manager.should_run():
            try:
                self.layer7_manager.run_summarization(game_time)
            except Exception as e:
                print(f"[WorldMemory] Layer 7 summarization error: {e}")

        # Periodic retention pruning
        if self.retention_manager.should_prune(game_time):
            self.retention_manager.prune(self.event_store, game_time)

        # Expire old interpretations
        self.event_store.expire_old_interpretations(game_time)

        # Periodic stat store flush (batch writes)
        if self.stat_store:
            self.stat_store.flush()

    # ── Save/Load ────────────────────────────────────────────────────

    def save(self) -> Dict[str, Any]:
        """Get save data for the memory system.

        Returns a dict to be stored in the save file. SQLite data is
        already auto-committed; this handles the JSON-serializable state.
        """
        if not self._initialized:
            return {}

        # Flush SQLite
        self.event_store.flush()

        # Save entity states to SQLite
        for eid, entity in self.entity_registry.entities.items():
            self.event_store.save_entity_state(
                eid, entity.tags, entity.activity_log, {}
            )

        # Save region states to SQLite
        for rid, region in self.geo_registry.regions.items():
            self.event_store.save_region_state(
                rid,
                region.state.active_conditions,
                region.state.recent_events,
                region.state.summary_text,
                region.state.last_updated,
            )

        # Save trigger manager state
        trigger_state = {}
        if self.trigger_manager:
            trigger_state = self.trigger_manager.get_state()

        return {
            "memory_db_path": self.event_store.db_path,
            "session_id": self._session_id,
            "game_time": self._game_time,
            "trigger_state": trigger_state,
        }

    def load(self, save_data: Dict[str, Any], save_dir: str,
             character=None, world=None,
             geo_map_path: Optional[str] = None) -> None:
        """Load memory system from save data.

        If the SQLite database exists, it's reopened. On schema version
        mismatch (e.g. an old v1 database), the stale DB is deleted
        and a fresh v2 database is regenerated — the game continues,
        losing only WMS history (stats, raw events, higher layers)
        but preserving the save file itself. This matches the
        cautious migration policy: fail loud, recover gracefully, do
        not write compat shims.
        """
        db_path = save_data.get("memory_db_path", "")
        target_dir = os.path.dirname(db_path) if db_path else save_dir

        def _try_init(directory: str) -> None:
            self.initialize(
                save_dir=directory,
                character=character,
                world=world,
                geo_map_path=geo_map_path,
            )

        if db_path and os.path.exists(db_path):
            try:
                _try_init(target_dir)
                return
            except RuntimeError as e:
                # Schema mismatch: delete the stale DB and start fresh.
                # Log clearly so a developer can see what happened.
                print(f"[WorldMemory] Stale WMS database at {db_path}: {e}")
                print("[WorldMemory] Deleting old DB and regenerating.")
                try:
                    os.remove(db_path)
                    # Also clean up WAL/SHM sidecars if present
                    for suffix in ("-wal", "-shm"):
                        p = db_path + suffix
                        if os.path.exists(p):
                            os.remove(p)
                except OSError as rm_err:
                    print(f"[WorldMemory] Could not remove old DB: {rm_err}")
                _try_init(target_dir)
                return

        # No existing DB — fresh init
        _try_init(save_dir)

    # ── Shutdown ─────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Clean up resources."""
        if self.event_recorder:
            self.event_recorder.disconnect()
        if self.event_store:
            self.event_store.close()
        self._initialized = False

        # Reset singletons
        GeographicRegistry.reset()
        EntityRegistry.reset()
        EventRecorder.reset()
        TriggerManager.reset()
        WorldInterpreter.reset()
        WorldQuery.reset()
        StatStore.reset()
        Layer3Manager.reset()
        Layer4Manager.reset()
        Layer5Manager.reset()
        Layer6Manager.reset()
        Layer7Manager.reset()
        TriggerRegistry.reset()

    # ── Queries ──────────────────────────────────────────────────────

    def get_world_summary(self, game_time: Optional[float] = None) -> Dict[str, Any]:
        """High-level world state for narrative/NPC consumers.

        Returns the current ``ongoing_conditions`` set plus aggregate
        counts. Thin passthrough to :class:`WorldQuery`; exists so
        consumers can depend on the facade rather than reaching into
        ``world_memory.world_query`` directly.
        """
        if not self._initialized or not self.world_query:
            return {"ongoing_conditions": [], "total_events_recorded": 0,
                    "regions_with_activity": 0}
        t = self._game_time if game_time is None else game_time
        return self.world_query.get_world_summary(t)

    # ── Debug / Stats ────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        if not self._initialized:
            return {"initialized": False}
        return {
            "initialized": True,
            "session_id": self._session_id,
            "game_time": self._game_time,
            "regions": len(self.geo_registry.regions),
            "entities": len(self.entity_registry.entities),
            "recorder": self.event_recorder.stats,
            "interpreter": self.interpreter.stats,
            "query": self.world_query.get_world_summary(self._game_time),
        }
