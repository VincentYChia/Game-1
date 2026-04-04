"""Procedural name generator with per-nation cultural banks.

5 naming flavors (pure fantasy, no real-world cultural baggage):
- Stoic: Heavy, northern, grim
- Flowing: Soft, musical, nature-touched
- Imperial: Formal, grand, structured
- Stoneworn: Weathered, ancient, deep
- Ethereal: Mystical, luminous, otherworldly

Names are deterministic from seed — same seed = same names always.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from systems.geography.models import (
    DistrictData,
    LocalityData,
    NamingFlavor,
    NationData,
    ProvinceData,
    RegionData,
    RegionIdentity,
)
from systems.geography.noise import hash_2d_int


# ══════════════════════════════════════════════════════════════════
# BUILT-IN NAME BANKS (fallback if JSON not found)
# ══════════════════════════════════════════════════════════════════

_BANKS: Dict[NamingFlavor, dict] = {
    NamingFlavor.STOIC: {
        "nation_names": [
            "Korsheim", "Nordhaven", "Grimwald", "Stonereach", "Drakmoor",
            "Ashgard", "Frostholm", "Ironmark", "Wraithgard", "Blackthorn",
        ],
        "adjectives": [
            "Ashen", "Iron", "Storm", "Grey", "Frost", "Dark", "Grim",
            "Stark", "Cold", "Dread", "Stone", "Black", "Hollow", "Bleak",
        ],
        "prefixes": [
            "Storm", "Iron", "Grey", "Frost", "Dark", "Stone", "Grim",
            "Ash", "Dread", "Cold", "Black", "Thorn", "Wolf", "Hawk",
        ],
        "suffixes": [
            "crest", "hold", "watch", "guard", "haven", "fall", "gate",
            "moor", "helm", "keep", "wall", "rock", "vale", "mark",
        ],
        "district_nouns": [
            "Quarter", "Ward", "Gate", "Reach", "Heights", "Depths",
            "Crossing", "Hollow", "Ridge", "Passage",
        ],
    },
    NamingFlavor.FLOWING: {
        "nation_names": [
            "Silvanel", "Brightmere", "Dewhollow", "Willowveil", "Faelind",
            "Glenmist", "Thornweald", "Moonhaven", "Riverbend", "Starfall",
        ],
        "adjectives": [
            "Verdant", "Silver", "Misty", "Wild", "Ancient", "Bright",
            "Gentle", "Wandering", "Woven", "Dappled", "Quiet", "Living",
        ],
        "prefixes": [
            "Silver", "Green", "Moon", "Star", "Willow", "Briar", "Glen",
            "Fern", "Dew", "Rose", "Lily", "Thorn", "Moss", "Rain",
        ],
        "suffixes": [
            "vale", "mere", "haven", "brook", "glade", "dell", "wood",
            "fall", "weald", "shire", "glen", "dale", "leaf", "song",
        ],
        "district_nouns": [
            "Glade", "Dell", "Hollow", "Bower", "Thicket", "Meadow",
            "Copse", "Grove", "Circle", "Clearing",
        ],
    },
    NamingFlavor.IMPERIAL: {
        "nation_names": [
            "Aurelium", "Corvanta", "Valdris", "Solareth", "Magistrum",
            "Imperion", "Regalis", "Dominara", "Luxenheim", "Gloriana",
        ],
        "adjectives": [
            "Grand", "Golden", "Crimson", "Noble", "Sacred", "Azure",
            "Royal", "Sovereign", "Exalted", "Pristine", "Gilded", "High",
        ],
        "prefixes": [
            "Sol", "Val", "Cor", "Rex", "Aur", "Lux", "Dom", "Mag",
            "Pax", "Gal", "Reg", "Cel", "Tri", "Vic",
        ],
        "suffixes": [
            "ium", "anta", "aris", "eth", "orium", "andria", "aven",
            "heim", "oria", "ence", "ium", "alis", "entus", "erra",
        ],
        "district_nouns": [
            "Plaza", "Terrace", "Forum", "Court", "Citadel", "Precinct",
            "Arcade", "Sanctum", "Promenade", "Quarter",
        ],
    },
    NamingFlavor.STONEWORN: {
        "nation_names": [
            "Duskmere", "Cindervault", "Bleakhaven", "Ashenmire", "Rustholm",
            "Emberfell", "Bonecrag", "Hollowdeep", "Grimstone", "Palereach",
        ],
        "adjectives": [
            "Bitter", "Deep", "Hollow", "Pale", "Ember", "Bleak",
            "Cinder", "Rust", "Dusk", "Worn", "Cracked", "Sunken",
        ],
        "prefixes": [
            "Dusk", "Cinder", "Bone", "Rust", "Ash", "Pale", "Hollow",
            "Deep", "Ember", "Grey", "Old", "Worn", "Bleak", "Dust",
        ],
        "suffixes": [
            "mere", "vault", "haven", "mire", "fell", "crag", "deep",
            "stone", "reach", "pit", "den", "barrow", "cairn", "forge",
        ],
        "district_nouns": [
            "Barrow", "Cairn", "Pit", "Undercroft", "Foundation",
            "Catacombs", "Ruins", "Cellar", "Burrow", "Vault",
        ],
    },
    NamingFlavor.ETHEREAL: {
        "nation_names": [
            "Aelindra", "Lumareth", "Orivane", "Twilindor", "Veyloria",
            "Silpharion", "Crysthaven", "Shimmerdeep", "Mythalore", "Celestine",
        ],
        "adjectives": [
            "Luminous", "Twilight", "Silent", "Opal", "Veiled", "Woven",
            "Shimmering", "Fading", "Dreamlit", "Prismatic", "Spectral", "Iridescent",
        ],
        "prefixes": [
            "Ael", "Lum", "Ori", "Twi", "Vey", "Sil", "Crys", "Myth",
            "Cel", "Neb", "Iri", "Pha", "Zeph", "Aur",
        ],
        "suffixes": [
            "indra", "areth", "vane", "indor", "oria", "arion", "haven",
            "deep", "alore", "estine", "iel", "anthe", "endra", "ilis",
        ],
        "district_nouns": [
            "Sanctum", "Spire", "Atrium", "Nexus", "Wellspring",
            "Observatory", "Reliquary", "Archive", "Threshold", "Mirage",
        ],
    },
}


def _get_bank(flavor: NamingFlavor) -> dict:
    """Get naming bank for a flavor, with fallback to Stoic."""
    return _BANKS.get(flavor, _BANKS[NamingFlavor.STOIC])


def _pick(items: List[str], idx: int) -> str:
    """Deterministically pick from a list using an index."""
    if not items:
        return "Unknown"
    return items[idx % len(items)]


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def name_nation(nation: NationData, seed: int) -> str:
    """Generate a name for a nation."""
    bank = _get_bank(nation.naming_flavor)
    names = bank.get("nation_names", ["Unknown"])
    idx = hash_2d_int(nation.nation_id, 0, seed + 900000, len(names))
    name = _pick(names, idx)
    nation.name = name
    return name


def name_region(
    region: RegionData,
    nation: NationData,
    seed: int,
) -> str:
    """Generate a name for a region: [Adjective] [Identity]."""
    bank = _get_bank(nation.naming_flavor)
    adjectives = bank.get("adjectives", ["Unknown"])
    adj_idx = hash_2d_int(region.region_id, 1, seed + 910000, len(adjectives))
    adj = _pick(adjectives, adj_idx)
    identity_name = region.identity.display_name
    name = f"{adj} {identity_name}"
    region.name = name
    return name


def name_province(
    province: ProvinceData,
    nation: NationData,
    seed: int,
) -> str:
    """Generate a name for a province: [Prefix][Suffix]."""
    bank = _get_bank(nation.naming_flavor)
    prefixes = bank.get("prefixes", ["Un"])
    suffixes = bank.get("suffixes", ["known"])
    p_idx = hash_2d_int(province.province_id, 2, seed + 920000, len(prefixes))
    s_idx = hash_2d_int(province.province_id, 3, seed + 930000, len(suffixes))
    prefix = _pick(prefixes, p_idx)
    suffix = _pick(suffixes, s_idx)
    name = f"{prefix}{suffix}"
    province.name = name
    return name


def name_district(
    district: DistrictData,
    nation: NationData,
    seed: int,
) -> str:
    """Generate a name for a district: [The] [Adjective] [Noun] or [Prefix][Suffix]."""
    bank = _get_bank(nation.naming_flavor)

    # 50/50 chance of "The [Adj] [Noun]" vs "[Prefix][Suffix]"
    style = hash_2d_int(district.district_id, 4, seed + 940000, 2)

    if style == 0:
        adjectives = bank.get("adjectives", ["Old"])
        nouns = bank.get("district_nouns", ["Quarter"])
        a_idx = hash_2d_int(district.district_id, 5, seed + 950000, len(adjectives))
        n_idx = hash_2d_int(district.district_id, 6, seed + 960000, len(nouns))
        adj = _pick(adjectives, a_idx)
        noun = _pick(nouns, n_idx)
        name = f"The {adj} {noun}"
    else:
        prefixes = bank.get("prefixes", ["Un"])
        suffixes = bank.get("suffixes", ["known"])
        p_idx = hash_2d_int(district.district_id, 7, seed + 970000, len(prefixes))
        s_idx = hash_2d_int(district.district_id, 8, seed + 980000, len(suffixes))
        prefix = _pick(prefixes, p_idx)
        suffix = _pick(suffixes, s_idx)
        name = f"{prefix}{suffix}"

    district.name = name
    return name


def name_locality(
    locality: LocalityData,
    nation: NationData,
    seed: int,
) -> str:
    """Generate a name for a locality based on its feature type."""
    bank = _get_bank(nation.naming_flavor)

    # Feature-specific naming
    feature_prefixes = {
        "dungeon": ["Forsaken", "Cursed", "Ancient", "Dark", "Lost"],
        "npc": ["Elder's", "Trader's", "Wanderer's", "Sage's", "Hunter's"],
        "station": ["Old", "Master's", "Grand", "Ruined", "Working"],
        "rare_resource": ["Hidden", "Rich", "Glowing", "Precious", "Deep"],
    }
    feature_suffixes = {
        "dungeon": ["Pit", "Maw", "Depths", "Tomb", "Lair", "Chasm"],
        "npc": ["Grove", "Corner", "Rest", "Camp", "Post", "Refuge"],
        "station": ["Forge", "Workshop", "Smeltery", "Bench", "Anvil"],
        "rare_resource": ["Vein", "Stand", "Deposit", "Spring", "Cache"],
    }

    ft = locality.feature_type
    prefixes = feature_prefixes.get(ft, bank.get("adjectives", ["Unknown"]))
    suffixes = feature_suffixes.get(ft, bank.get("district_nouns", ["Place"]))

    p_idx = hash_2d_int(locality.locality_id, 9, seed + 990000, len(prefixes))
    s_idx = hash_2d_int(locality.locality_id, 10, seed + 991000, len(suffixes))

    name = f"{_pick(prefixes, p_idx)} {_pick(suffixes, s_idx)}"
    locality.name = name
    return name


def name_all(
    nations: Dict[int, NationData],
    regions: Dict[int, RegionData],
    provinces: Dict[int, ProvinceData],
    districts: Dict[int, DistrictData],
    localities: Dict[int, LocalityData],
    seed: int,
) -> None:
    """Apply procedural names to all geographic tiers."""
    # Name nations first (needed for cultural bank lookups)
    for nid, nation in sorted(nations.items()):
        name_nation(nation, seed)

    # Name regions
    for rid, region in sorted(regions.items()):
        nation = nations.get(region.nation_id)
        if nation:
            name_region(region, nation, seed)

    # Name provinces
    for pid, province in sorted(provinces.items()):
        nation = nations.get(province.nation_id)
        if nation:
            name_province(province, nation, seed)

    # Name districts
    for did, district in sorted(districts.items()):
        nation = nations.get(district.nation_id)
        if nation:
            name_district(district, nation, seed)

    # Name localities
    for lid, locality in sorted(localities.items()):
        # Find nation for this locality's chunk
        nation = None
        for nid, n in nations.items():
            nation = n
            break
        if nation:
            name_locality(locality, nation, seed)
