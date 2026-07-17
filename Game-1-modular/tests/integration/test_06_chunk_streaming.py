"""
Playtest scenario 6: chunk streaming behavior (2026-06-10 Track A).

Pins the boundary-hitch fix:
- the 3x3 around the player ALWAYS loads in the same frame (the ground
  being walked onto is never deferred);
- the outer prefetch ring streams in over subsequent frames (budgeted),
  reaching the full load radius;
- hysteresis: chunks just outside the load radius are retained (no
  load/unload thrash while walking along a boundary).
"""
from core.config import Config
from data.models.world import Position


def _chunk_of(pos):
    return (int(pos.x) // Config.CHUNK_SIZE, int(pos.y) // Config.CHUNK_SIZE)


def test_chunk_streaming_and_hysteresis(play):
    eng = play.engine
    world = eng.world
    original = Position(eng.character.position.x,
                        eng.character.position.y,
                        eng.character.position.z)

    from data.databases.world_generation_db import WorldGenerationConfig
    load_radius = WorldGenerationConfig.get_instance().chunk_loading.load_radius

    try:
        # Teleport somewhere far with no chunks loaded yet.
        eng.character.position.x = original.x + 40 * Config.CHUNK_SIZE
        eng.character.position.y = original.y + 40 * Config.CHUNK_SIZE
        pcx, pcy = _chunk_of(eng.character.position)

        world.update_loaded_chunks(eng.character.position)

        # 1. The player's 3x3 is loaded IMMEDIATELY — never deferred.
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                assert (pcx + dx, pcy + dy) in world.loaded_chunks, (
                    f"Critical chunk ({pcx+dx},{pcy+dy}) was deferred"
                )

        # 2. The full radius was NOT loaded in that single frame (budget).
        full_set = {(pcx + dx, pcy + dy)
                    for dx in range(-load_radius, load_radius + 1)
                    for dy in range(-load_radius, load_radius + 1)}
        loaded_now = full_set & set(world.loaded_chunks.keys())
        assert len(loaded_now) < len(full_set), (
            "Entire load radius generated in one frame — budget not applied"
        )

        # 3. Streaming completes over subsequent frames.
        for _ in range(120):
            world.update_loaded_chunks(eng.character.position)
        missing = full_set - set(world.loaded_chunks.keys())
        assert not missing, f"Prefetch never finished: {sorted(missing)[:5]}"

        # 4. Hysteresis: step one chunk east — chunks now exactly one ring
        #    behind must STAY loaded (old behavior unloaded them instantly,
        #    thrashing on every boundary wobble).
        west_edge = {(pcx - load_radius, pcy + dy)
                     for dy in range(-load_radius, load_radius + 1)}
        eng.character.position.x += Config.CHUNK_SIZE
        world.update_loaded_chunks(eng.character.position)
        still_loaded = west_edge & set(world.loaded_chunks.keys())
        assert still_loaded == west_edge, (
            "Hysteresis ring was unloaded immediately on a 1-chunk step"
        )
    finally:
        eng.character.position.x = original.x
        eng.character.position.y = original.y
        eng.character.position.z = original.z
        world.update_loaded_chunks(eng.character.position)
        play.settle()
