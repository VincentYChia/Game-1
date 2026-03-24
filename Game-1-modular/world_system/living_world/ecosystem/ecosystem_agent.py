"""EcosystemAgent — tracks resource pressure and scarcity across biomes.

Monitors RESOURCE_GATHERED events from the GameEventBus and maintains
per-biome resource state. When depletion crosses configurable thresholds
(70% scarce, 90% critical), scarcity flags are set and events published.

Resources regenerate over time at configurable rates (quick=120s, normal=300s,
slow=600s, very_slow=1200s).

Usage:
    agent = EcosystemAgent.get_instance()
    agent.initialize()
    # In game loop:
    agent.tick(game_time_delta)
    # Query:
    report = agent.get_scarcity_report()
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from events.event_bus import get_event_bus


@dataclass
class ResourceState:
    """Tracks a single resource within a biome."""
    resource_id: str
    initial_total: int = 100
    current_total: float = 100.0       # Regeneration can be fractional
    total_gathered: int = 0
    regeneration_rate: float = 300.0    # Game-seconds per unit regeneration
    is_scarce: bool = False
    is_critical: bool = False


@dataclass
class BiomeResourceState:
    """Tracks all resources within a single biome."""
    biome_type: str
    resources: Dict[str, ResourceState] = field(default_factory=dict)

    def get_depletion_ratio(self, resource_id: str) -> float:
        """Get depletion ratio (0.0 = full, 1.0 = empty)."""
        state = self.resources.get(resource_id)
        if not state or state.initial_total <= 0:
            return 0.0
        remaining = max(0.0, state.current_total)
        return 1.0 - (remaining / state.initial_total)

    def get_resource_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all resources in this biome."""
        result = {}
        for rid, state in self.resources.items():
            result[rid] = {
                "initial": state.initial_total,
                "current": round(state.current_total, 1),
                "gathered": state.total_gathered,
                "depletion": round(self.get_depletion_ratio(rid), 3),
                "scarce": state.is_scarce,
                "critical": state.is_critical,
                "regen_rate": state.regeneration_rate,
            }
        return result


class EcosystemAgent:
    """Singleton agent monitoring resource pressure across all biomes.

    Subscribes to RESOURCE_GATHERED on the GameEventBus.
    Publishes RESOURCE_SCARCITY and RESOURCE_RECOVERED events.
    """

    _instance: ClassVar[Optional[EcosystemAgent]] = None

    def __init__(self):
        self._biomes: Dict[str, BiomeResourceState] = {}
        self._config: Dict[str, Any] = {}
        self._scarce_threshold: float = 0.7
        self._critical_threshold: float = 0.9
        self._regen_rates: Dict[str, float] = {}
        self._default_regen: str = "normal"
        self._tick_interval: float = 60.0
        self._last_tick_time: float = 0.0
        self._initialized: bool = False
        self._bus_connected: bool = False

    @classmethod
    def get_instance(cls) -> EcosystemAgent:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance and cls._instance._bus_connected:
            cls._instance._disconnect_bus()
        cls._instance = None

    def initialize(self, config_path: Optional[str] = None) -> None:
        """Load ecosystem config and subscribe to events."""
        if self._initialized:
            return

        config = self._load_config(config_path)
        self._config = config

        # Thresholds
        thresholds = config.get("scarcity_thresholds", {})
        self._scarce_threshold = thresholds.get("scarce", 0.7)
        self._critical_threshold = thresholds.get("critical", 0.9)

        # Regeneration rates (name → seconds per unit)
        self._regen_rates = {
            k: v for k, v in config.get("regeneration_rates", {}).items()
            if isinstance(v, (int, float))
        }
        self._default_regen = config.get("default_regeneration", "normal")
        self._tick_interval = config.get("tick_interval_game_seconds", 60.0)

        # Initialize biome resources from defaults
        biome_defaults = config.get("biome_resource_defaults", {})
        for biome_type, bdata in biome_defaults.items():
            biome_state = BiomeResourceState(biome_type=biome_type)
            for res_id, rdata in bdata.get("resources", {}).items():
                initial = rdata.get("initial", 100)
                regen_name = rdata.get("regeneration", self._default_regen)
                regen_rate = self._regen_rates.get(regen_name, 300.0)
                biome_state.resources[res_id] = ResourceState(
                    resource_id=res_id,
                    initial_total=initial,
                    current_total=float(initial),
                    total_gathered=0,
                    regeneration_rate=regen_rate,
                )
            self._biomes[biome_type] = biome_state

        self._connect_bus()
        self._initialized = True
        print(f"[EcosystemAgent] Initialized with {len(self._biomes)} biomes, "
              f"{sum(len(b.resources) for b in self._biomes.values())} resource types")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)

        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
        default_path = os.path.join(
            project_root, "world_system", "config", "ecosystem-config.json"
        )
        if os.path.exists(default_path):
            with open(default_path, "r") as f:
                return json.load(f)
        return {}

    def _connect_bus(self) -> None:
        bus = get_event_bus()
        bus.subscribe("RESOURCE_GATHERED", self._on_resource_gathered, priority=5)
        self._bus_connected = True

    def _disconnect_bus(self) -> None:
        bus = get_event_bus()
        bus.unsubscribe("RESOURCE_GATHERED", self._on_resource_gathered)
        self._bus_connected = False

    # ── Event Handler ─────────────────────────────────────────────────

    def _on_resource_gathered(self, event) -> None:
        """Handle RESOURCE_GATHERED events from GameEventBus."""
        data = event.data
        resource_id = data.get("resource_id", "")
        quantity = data.get("quantity", 1)
        biome = data.get("biome", "unknown")

        if not resource_id:
            return

        # Ensure biome exists
        if biome not in self._biomes:
            self._biomes[biome] = BiomeResourceState(biome_type=biome)

        biome_state = self._biomes[biome]

        # Ensure resource tracked
        if resource_id not in biome_state.resources:
            regen_rate = self._regen_rates.get(self._default_regen, 300.0)
            biome_state.resources[resource_id] = ResourceState(
                resource_id=resource_id,
                initial_total=100,  # Dynamic discovery
                current_total=100.0,
                regeneration_rate=regen_rate,
            )

        state = biome_state.resources[resource_id]
        state.total_gathered += quantity
        state.current_total = max(0.0, state.current_total - quantity)

        # Check thresholds
        self._check_thresholds(biome, resource_id)

    # ── Tick (Regeneration + Threshold Checks) ────────────────────────

    def tick(self, game_time: float) -> None:
        """Process regeneration and threshold checks.

        Should be called from the game loop. Only processes once
        per tick_interval to avoid excessive computation.
        """
        if not self._initialized:
            return

        if game_time - self._last_tick_time < self._tick_interval:
            return

        elapsed = game_time - self._last_tick_time if self._last_tick_time > 0 else self._tick_interval
        self._last_tick_time = game_time

        # Regenerate resources
        for biome_type, biome_state in self._biomes.items():
            for res_id, state in biome_state.resources.items():
                if state.regeneration_rate <= 0:
                    continue
                if state.current_total >= state.initial_total:
                    continue

                # Regenerate: units = elapsed / rate
                regen_amount = elapsed / state.regeneration_rate
                old_total = state.current_total
                state.current_total = min(
                    state.initial_total,
                    state.current_total + regen_amount,
                )

                # Check if recovered from scarcity
                if old_total != state.current_total:
                    self._check_thresholds(biome_type, res_id)

    def _check_thresholds(self, biome_type: str, resource_id: str) -> None:
        """Check scarcity thresholds and publish events if crossed."""
        biome_state = self._biomes.get(biome_type)
        if not biome_state:
            return

        state = biome_state.resources.get(resource_id)
        if not state:
            return

        depletion = biome_state.get_depletion_ratio(resource_id)
        bus = get_event_bus()

        was_scarce = state.is_scarce
        was_critical = state.is_critical

        state.is_critical = depletion >= self._critical_threshold
        state.is_scarce = depletion >= self._scarce_threshold

        # Publish scarcity event if newly scarce/critical
        if state.is_critical and not was_critical:
            bus.publish("RESOURCE_SCARCITY", {
                "biome": biome_type,
                "resource_id": resource_id,
                "depletion": round(depletion, 3),
                "severity": "critical",
            }, source="EcosystemAgent")
        elif state.is_scarce and not was_scarce:
            bus.publish("RESOURCE_SCARCITY", {
                "biome": biome_type,
                "resource_id": resource_id,
                "depletion": round(depletion, 3),
                "severity": "scarce",
            }, source="EcosystemAgent")

        # Publish recovery event if no longer scarce
        if was_scarce and not state.is_scarce:
            bus.publish("RESOURCE_RECOVERED", {
                "biome": biome_type,
                "resource_id": resource_id,
                "depletion": round(depletion, 3),
            }, source="EcosystemAgent")

    # ── Query API ─────────────────────────────────────────────────────

    def get_scarcity_report(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all scarce/critical resources grouped by biome.

        Returns:
            Dict of biome_type → list of {resource_id, depletion, severity}.
        """
        report: Dict[str, List[Dict[str, Any]]] = {}
        for biome_type, biome_state in self._biomes.items():
            scarce = []
            for res_id, state in biome_state.resources.items():
                if state.is_scarce or state.is_critical:
                    scarce.append({
                        "resource_id": res_id,
                        "depletion": round(biome_state.get_depletion_ratio(res_id), 3),
                        "severity": "critical" if state.is_critical else "scarce",
                        "remaining": round(state.current_total, 1),
                        "initial": state.initial_total,
                    })
            if scarce:
                report[biome_type] = scarce
        return report

    def get_biome_state(self, biome_type: str) -> Optional[BiomeResourceState]:
        """Get full resource state for a biome."""
        return self._biomes.get(biome_type)

    def get_resource_info(self, biome_type: str,
                          resource_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific resource in a biome."""
        biome = self._biomes.get(biome_type)
        if not biome:
            return None
        state = biome.resources.get(resource_id)
        if not state:
            return None
        return {
            "resource_id": resource_id,
            "biome": biome_type,
            "initial": state.initial_total,
            "current": round(state.current_total, 1),
            "gathered": state.total_gathered,
            "depletion": round(biome.get_depletion_ratio(resource_id), 3),
            "scarce": state.is_scarce,
            "critical": state.is_critical,
            "regeneration_rate": state.regeneration_rate,
        }

    # ── Serialization ─────────────────────────────────────────────────

    def save(self) -> Dict[str, Any]:
        """Serialize ecosystem state for persistence."""
        biomes_data = {}
        for biome_type, biome_state in self._biomes.items():
            resources_data = {}
            for res_id, state in biome_state.resources.items():
                resources_data[res_id] = {
                    "initial_total": state.initial_total,
                    "current_total": round(state.current_total, 2),
                    "total_gathered": state.total_gathered,
                    "regeneration_rate": state.regeneration_rate,
                    "is_scarce": state.is_scarce,
                    "is_critical": state.is_critical,
                }
            biomes_data[biome_type] = resources_data
        return {
            "biomes": biomes_data,
            "last_tick_time": self._last_tick_time,
        }

    def load(self, data: Dict[str, Any]) -> None:
        """Restore ecosystem state from saved data."""
        self._last_tick_time = data.get("last_tick_time", 0.0)
        biomes_data = data.get("biomes", {})
        for biome_type, resources_data in biomes_data.items():
            if biome_type not in self._biomes:
                self._biomes[biome_type] = BiomeResourceState(biome_type=biome_type)
            biome_state = self._biomes[biome_type]
            for res_id, rdata in resources_data.items():
                if res_id in biome_state.resources:
                    state = biome_state.resources[res_id]
                else:
                    state = ResourceState(resource_id=res_id)
                    biome_state.resources[res_id] = state
                state.initial_total = rdata.get("initial_total", state.initial_total)
                state.current_total = rdata.get("current_total", float(state.initial_total))
                state.total_gathered = rdata.get("total_gathered", 0)
                state.regeneration_rate = rdata.get("regeneration_rate", 300.0)
                state.is_scarce = rdata.get("is_scarce", False)
                state.is_critical = rdata.get("is_critical", False)

    @property
    def stats(self) -> Dict[str, Any]:
        total_scarce = sum(
            1 for b in self._biomes.values()
            for r in b.resources.values()
            if r.is_scarce
        )
        total_critical = sum(
            1 for b in self._biomes.values()
            for r in b.resources.values()
            if r.is_critical
        )
        return {
            "initialized": self._initialized,
            "biome_count": len(self._biomes),
            "resource_types": sum(len(b.resources) for b in self._biomes.values()),
            "scarce_resources": total_scarce,
            "critical_resources": total_critical,
            "last_tick_time": self._last_tick_time,
        }
