"""
PlaytestHarness — drives the real GameEngine like a player would.

Input goes through the same surfaces the player's hardware hits:
- key/mouse events are posted to the pygame event queue and consumed by
  the engine's own handle_events() dispatch;
- frames advance through the engine's own update() (with controlled dt via
  last_tick) and optionally render() — rendering under the dummy driver
  still executes the full Renderer code path, which is exactly where UI
  state bugs live.

High-level actions (move, craft, save) compose those primitives plus the
engine's real handler methods, never re-implementing game logic.
"""
import pygame

FRAME_MS = 16  # ~60 FPS simulation step


class PlaytestHarness:
    def __init__(self, engine):
        self.engine = engine

    # ── frame driving ────────────────────────────────────────────────

    def tick(self, frames: int = 1, dt_ms: int = FRAME_MS, render_every: int = 0):
        """Advance N frames through the real per-frame sequence.

        dt is controlled by back-dating engine.last_tick, the exact value
        update() differences against — no monkeypatching of pygame time.
        render_every=N also runs the full Renderer every Nth frame
        (0 = never; rendering is ~10x the cost of update).
        """
        eng = self.engine
        for i in range(frames):
            eng.handle_events()
            eng.last_tick = pygame.time.get_ticks() - dt_ms
            eng.update()
            if render_every and (i % render_every) == 0:
                eng.render()

    def settle(self, frames: int = 3):
        """Drain queued events / pending UI state transitions."""
        self.tick(frames)

    # ── input primitives (real event-queue injection) ────────────────

    def key_down(self, key: int):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0,
                                             unicode=''))

    def key_up(self, key: int):
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0))

    def key_tap(self, key: int, frames_between: int = 1):
        """Press and release a key, ticking so both events are consumed."""
        self.key_down(key)
        self.tick(frames_between)
        self.key_up(key)
        self.tick(1)

    def click(self, pos, button: int = 1):
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
        self.tick(1)
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONUP, pos=pos, button=button))
        self.tick(1)

    # ── player movement ──────────────────────────────────────────────

    DIRECTION_KEYS = {
        'up': pygame.K_w, 'down': pygame.K_s,
        'left': pygame.K_a, 'right': pygame.K_d,
    }

    def move(self, direction: str, frames: int = 30):
        """Hold a WASD key for N frames through the real event pipeline."""
        key = self.DIRECTION_KEYS[direction]
        self.key_down(key)
        self.tick(frames)
        self.key_up(key)
        self.tick(1)

    def position(self):
        pos = self.engine.character.position
        return (pos.x, pos.y)

    # ── inventory helpers ────────────────────────────────────────────

    def give(self, item_id: str, qty: int = 1) -> bool:
        return self.engine.character.inventory.add_item(item_id, qty)

    def count(self, item_id: str) -> int:
        total = 0
        for slot in self.engine.character.inventory.slots:
            if slot and slot.item_id == item_id:
                total += slot.quantity
        return total

    # ── crafting (real completion pipeline) ──────────────────────────

    def craft(self, discipline: str, recipe_id: str, minigame_result: dict):
        """Run a craft through the engine's real completion path.

        Creates the real minigame object via the discipline's crafter,
        installs it as the active minigame (as the station UI does), sets
        its result as if the player just finished playing, then ticks so
        update() detects completion and runs _complete_minigame() — the
        full pipeline: crafter, material consumption, inventory add,
        title/stat hooks, ITEM_CRAFTED publish.
        """
        eng = self.engine
        from data.databases.recipe_db import RecipeDatabase
        recipe = RecipeDatabase.get_instance().recipes.get(recipe_id)
        assert recipe is not None, f"Unknown recipe: {recipe_id}"

        crafter = eng.get_crafter_for_station(discipline)
        assert crafter is not None, f"No crafter for discipline: {discipline}"

        minigame = crafter.create_minigame(recipe_id)
        assert minigame is not None, f"create_minigame failed for {recipe_id}"

        eng.active_minigame = minigame
        eng.minigame_type = discipline
        eng.minigame_recipe = recipe
        minigame.result = minigame_result

        self.tick(2)  # update() sees result -> _complete_minigame()
        return recipe

    # ── save/load (real SaveManager calls, as the pause menu makes) ──

    def save(self, filename: str = 'autosave.json') -> bool:
        eng = self.engine
        return eng.save_manager.save_game(
            eng.character, eng.world, eng.character.quests, eng.npcs,
            filename, eng.dungeon_manager, eng.game_time, eng.map_system,
        )

    def load_raw(self, filename: str = 'autosave.json'):
        return self.engine.save_manager.load_game(filename)
