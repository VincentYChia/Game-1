"""Determinism smoke for the patched geography pipeline (run twice, same seed)."""
import hashlib
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "Game-1-modular"
sys.path.insert(0, str(SRC))
import os
os.chdir(SRC)

from systems.geography.world_generator import WorldGenerator


def canon(seed):
    wm = WorldGenerator(seed=seed).generate()
    rows = []
    for (cx, cy) in sorted(wm.chunk_data):
        g = wm.chunk_data[(cx, cy)]
        rows.append(",".join(str(v) for v in (
            cx, cy, g.nation_id, g.region_id, g.province_id, g.district_id,
            g.chunk_type.value, g.biome_id, g.ecosystem_id,
            g.danger_level.value, g.locality_id)))
    names = ([wm.nations[k].name for k in sorted(wm.nations)]
             + [wm.regions[k].name for k in sorted(wm.regions)]
             + [wm.localities[k].name for k in sorted(wm.localities)])
    digest = hashlib.sha256(
        (";".join(rows) + "|" + "|".join(names)).encode()).hexdigest()
    return (digest, len(wm.nations), len(wm.regions), len(wm.provinces),
            len(wm.districts), len(wm.localities))


a = canon(777)
b = canon(777)
print("run1:", a)
print("run2:", b)
print("DETERMINISTIC:", a == b)
