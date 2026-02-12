// Game1.Entities.Character
// Migrated from: entities/character.py (1,008 lines)
// Phase: 3 - Entity Layer
// Implements ICharacterState, ICharacterEconomy from Phase 1.

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Data.Interfaces;
using Game1.Data.Models;
using Game1.Entities.Components;
using Game1.Entities.StatusEffects;

namespace Game1.Entities
{
    /// <summary>
    /// Main player character class integrating all components.
    /// Implements Phase 1 interfaces (ICharacterState, ICharacterEconomy)
    /// so that Phase 1/2 code can evaluate conditions against the character.
    /// </summary>
    public class Character : ICharacterState, ICharacterEconomy, IStatusTarget
    {
        // === Position & Movement ===
        public GamePosition Position { get; set; }
        public string Facing { get; set; } = "down";
        public float MovementSpeed { get; set; }
        public float InteractionRange { get; set; }

        // Knockback
        public float KnockbackVelocityX { get; set; }
        public float KnockbackVelocityY { get; set; }
        public float KnockbackDurationRemaining { get; set; }

        // === Components ===
        public CharacterStats Stats { get; set; }
        public LevelingSystem Leveling { get; set; }
        public SkillManager Skills { get; set; }
        public BuffManager Buffs { get; set; }
        public ActivityTracker Activities { get; set; }
        public StatTracker StatTracker { get; set; }
        public EquipmentManager Equipment { get; set; }
        public Inventory Inventory { get; set; }

        // Title, Class, Quest, Encyclopedia, SkillUnlock — Phase 4 system references
        // Stored as objects until those systems are ported.
        // Phase 3 provides stubs via ICharacterState.
        private readonly HashSet<string> _earnedTitleIds = new();
        private readonly HashSet<string> _knownSkillIds = new();
        private readonly HashSet<string> _completedQuests = new();
        private string _currentClassId;

        // === Health / Mana / Shield ===
        public int BaseMaxHealth { get; set; } = 100;
        public int BaseMaxMana { get; set; } = 100;
        public float MaxHealth { get; set; } = 100;
        public float Health { get; set; } = 100;
        public float MaxMana { get; set; } = 100;
        public float Mana { get; set; } = 100;
        public float ShieldAmount { get; set; }

        // Player-invented recipes (persisted across saves)
        public List<Dictionary<string, object>> InventedRecipes { get; set; } = new();

        // Tools (legacy — replaced by equipment slots)
        public List<Tool> Tools { get; set; } = new();
        public Tool SelectedTool { get; set; }
        public EquipmentItem SelectedWeapon { get; set; }
        public string SelectedSlot { get; set; } = "mainHand";

        // Status effect system
        public StatusEffectManager StatusManager { get; private set; }
        public string Category { get; set; } = "player";

        // UI state flags (Phase 6 will use these)
        public bool CraftingUiOpen { get; set; }
        public bool StatsUiOpen { get; set; }
        public bool EquipmentUiOpen { get; set; }
        public bool SkillsUiOpen { get; set; }
        public bool ClassSelectionOpen { get; set; }

        // Combat state
        public float AttackCooldown { get; set; }
        public float MainhandCooldown { get; set; }
        public float OffhandCooldown { get; set; }
        public bool IsBlocking { get; set; }

        // Health regen tracking
        public float TimeSinceLastDamageTaken { get; set; }
        public float TimeSinceLastDamageDealt { get; set; }
        public float HealthRegenThreshold { get; set; } = 5.0f;
        public float HealthRegenRate { get; set; } = 5.0f;

        // Economy
        public int Gold { get; set; }
        public int SkillPoints { get; set; }

        // === IStatusTarget backing fields ===
        private float _damageMultiplier = 1.0f;
        private float _damageTakenMultiplier = 1.0f;
        private bool _isFrozen;
        private bool _isStunned;
        private bool _isRooted;
        private readonly HashSet<string> _visualEffects = new();

        // === IStatusTarget ===
        string IStatusTarget.Name => "Player";
        float IStatusTarget.CurrentHealth { get => Health; set => Health = value; }
        float IStatusTarget.MaxHealth => MaxHealth;
        bool IStatusTarget.IsAlive => Health > 0;
        float IStatusTarget.DamageMultiplier { get => _damageMultiplier; set => _damageMultiplier = value; }
        float IStatusTarget.DamageTakenMultiplier { get => _damageTakenMultiplier; set => _damageTakenMultiplier = value; }
        float IStatusTarget.ShieldHealth { get => ShieldAmount; set => ShieldAmount = value; }
        bool IStatusTarget.IsFrozen { get => _isFrozen; set => _isFrozen = value; }
        bool IStatusTarget.IsStunned { get => _isStunned; set => _isStunned = value; }
        bool IStatusTarget.IsRooted { get => _isRooted; set => _isRooted = value; }
        HashSet<string> IStatusTarget.VisualEffects => _visualEffects;

        // === ICharacterStats (from Phase 1) ===
        int ICharacterStats.Level => Leveling.Level;
        int ICharacterStats.Strength => Stats.Strength;
        int ICharacterStats.Defense => Stats.Defense;
        int ICharacterStats.Vitality => Stats.Vitality;
        int ICharacterStats.Luck => Stats.Luck;
        int ICharacterStats.Agility => Stats.Agility;
        int ICharacterStats.Intelligence => Stats.Intelligence;

        // === ICharacterState (from Phase 1) ===
        int ICharacterState.GetActivityCount(string activityType) => Activities.GetCount(activityType);
        bool ICharacterState.HasTitle(string titleId) => _earnedTitleIds.Contains(titleId);
        bool ICharacterState.HasSkill(string skillId) => Skills.KnownSkills.ContainsKey(skillId);
        bool ICharacterState.IsQuestCompleted(string questId) => _completedQuests.Contains(questId);
        string ICharacterState.CurrentClassId => _currentClassId;
        float ICharacterState.GetStatTrackerValue(string statPath) => StatTracker.GetValue(statPath);

        // === ICharacterEconomy (from Phase 1) ===
        int ICharacterEconomy.Gold { get => Gold; set => Gold = value; }
        int ICharacterEconomy.SkillPoints { get => SkillPoints; set => SkillPoints = value; }
        bool ICharacterEconomy.HasItem(string materialId, int quantity) => Inventory.HasItem(materialId, quantity);
        void ICharacterEconomy.RemoveItem(string materialId, int quantity) => Inventory.RemoveItem(materialId, quantity);

        // === Constructor ===
        public Character(GamePosition startPosition)
        {
            Position = startPosition;
            MovementSpeed = GameConfig.PLAYER_SPEED;
            InteractionRange = GameConfig.INTERACTION_RANGE;

            // Initialize components
            Stats = new CharacterStats();
            Leveling = new LevelingSystem();
            Skills = new SkillManager();
            Buffs = new BuffManager();
            Activities = new ActivityTracker();
            StatTracker = new StatTracker();
            StatTracker.StartSession();
            Equipment = new EquipmentManager();
            Inventory = new Inventory(30);

            // Status effects
            StatusManager = new StatusEffectManager(this);

            // Set initial health/mana
            MaxHealth = BaseMaxHealth;
            Health = MaxHealth;
            MaxMana = BaseMaxMana;
            Mana = MaxMana;

            // Give starting tools
            GiveStartingTools();

            if (GameConfig.DEBUG_INFINITE_RESOURCES)
                GiveDebugItems();
        }

        // === Public methods matching Python Character API ===

        /// <summary>
        /// Check if this character has a specific title.
        /// Public method for SkillManager and other components.
        /// </summary>
        public bool HasTitle(string titleId) => _earnedTitleIds.Contains(titleId);

        /// <summary>
        /// Add a title to earned titles.
        /// </summary>
        public void AddTitle(string titleId)
        {
            _earnedTitleIds.Add(titleId);
        }

        /// <summary>
        /// Set the character's current class.
        /// </summary>
        public void SetClass(string classId)
        {
            _currentClassId = classId;
        }

        /// <summary>
        /// Mark a quest as completed.
        /// </summary>
        public void CompleteQuest(string questId)
        {
            _completedQuests.Add(questId);
        }

        /// <summary>
        /// Recalculate max health and max mana from all sources.
        /// Formula: base + VIT*15 + class_bonus + equipment_bonus
        /// </summary>
        public void RecalculateStats()
        {
            float statHealth = Stats.GetFlatBonus("vitality", "max_health");
            float statMana = Stats.GetFlatBonus("intelligence", "mana");

            // Equipment bonuses
            var equipBonuses = Equipment.GetStatBonuses();
            float equipHealth = equipBonuses.GetValueOrDefault("max_health", 0f);
            float equipMana = equipBonuses.GetValueOrDefault("max_mana", 0f);

            // Class bonuses — Phase 4 will integrate ClassSystem.GetBonus()
            float classHealth = 0f;
            float classMana = 0f;

            float oldMaxHealth = MaxHealth;
            float oldMaxMana = MaxMana;

            MaxHealth = BaseMaxHealth + statHealth + classHealth + equipHealth;
            MaxMana = BaseMaxMana + statMana + classMana + equipMana;

            // Scale current values proportionally
            if (oldMaxHealth > 0)
            {
                float ratio = Health / oldMaxHealth;
                Health = Math.Min(MaxHealth, (int)(MaxHealth * ratio));
            }
            if (oldMaxMana > 0)
            {
                float ratio = Mana / oldMaxMana;
                Mana = Math.Min(MaxMana, (int)(MaxMana * ratio));
            }
        }

        /// <summary>
        /// Allocate a stat point.
        /// </summary>
        public bool AllocateStatPoint(string statName)
        {
            if (Leveling.UnallocatedStatPoints <= 0) return false;
            int current = Stats.GetStatByName(statName);
            if (current < 0) return false; // Invalid stat name

            Stats.SetStatByName(statName, current + 1);
            Leveling.UnallocatedStatPoints--;
            RecalculateStats();
            return true;
        }

        /// <summary>
        /// Get equipped tool for an action type.
        /// Returns the best matching equipped item for axe/pickaxe/fishing_rod.
        /// </summary>
        public EquipmentItem GetEquippedTool(string toolType)
        {
            // If player has explicitly selected a slot via Tab, use that
            if (!string.IsNullOrEmpty(SelectedSlot))
            {
                var selected = Equipment.Slots.GetValueOrDefault(SelectedSlot);
                if (selected != null) return selected;
            }

            // Default to correct tool type
            if (toolType == "axe" || toolType == "pickaxe" || toolType == "fishing_rod")
            {
                var tool = Equipment.Slots.GetValueOrDefault(toolType);
                if (tool != null) return tool;
            }

            // Fallback to mainHand
            return Equipment.Slots.GetValueOrDefault("mainHand");
        }

        /// <summary>
        /// Get tool effectiveness for an action type.
        /// Tools are 100% for their intended use, 25% for other uses.
        /// </summary>
        public float GetToolEffectiveness(EquipmentItem item, string actionType)
        {
            if (item == null) return 0f;
            string slot = item.Slot;

            if (slot == "axe") return actionType == "forestry" ? 1.0f : 0.25f;
            if (slot == "pickaxe") return actionType == "mining" ? 1.0f : 0.25f;
            if (slot == "fishing_rod") return actionType == "fishing" ? 1.0f : 0.25f;
            if (slot == "mainHand" || slot == "offHand") return actionType == "combat" ? 1.0f : 0.25f;

            return 1.0f; // Unknown tool type
        }

        /// <summary>
        /// Get effective luck including stat, titles, and equipment bonuses.
        /// </summary>
        public float GetEffectiveLuck()
        {
            float baseLuck = Stats.Luck;
            // Phase 4: Add title and equipment luck bonuses
            return baseLuck;
        }

        /// <summary>
        /// Get encumbrance speed penalty based on inventory weight.
        /// </summary>
        public float GetEncumbranceSpeedPenalty()
        {
            // Phase 4: Calculate based on total inventory weight vs capacity
            return 1.0f; // No penalty by default
        }

        /// <summary>
        /// Check if character is in range of a position.
        /// </summary>
        public bool IsInRange(GamePosition targetPosition)
        {
            return Position.DistanceTo(targetPosition) <= InteractionRange;
        }

        /// <summary>
        /// Take damage. Returns actual damage after defenses.
        /// </summary>
        public float TakeDamage(float rawDamage, string damageType = "physical")
        {
            // Defense reduction: max 75%
            float defReduction = Math.Min(0.75f, Stats.Defense * 0.02f);
            float afterDefense = rawDamage * (1.0f - defReduction);

            // Shield absorption
            if (ShieldAmount > 0)
            {
                if (ShieldAmount >= afterDefense)
                {
                    ShieldAmount -= afterDefense;
                    return 0f;
                }
                afterDefense -= ShieldAmount;
                ShieldAmount = 0;
            }

            Health -= afterDefense;
            TimeSinceLastDamageTaken = 0;

            // Track
            StatTracker.RecordDamageTaken(afterDefense, damageType);

            if (Health <= 0)
            {
                Health = 0;
                OnDeath();
            }

            return afterDefense;
        }

        /// <summary>
        /// Heal the character.
        /// </summary>
        public float Heal(float amount)
        {
            float actual = Math.Min(amount, MaxHealth - Health);
            Health += actual;
            return actual;
        }

        /// <summary>
        /// Restore mana.
        /// </summary>
        public float RestoreMana(float amount)
        {
            float actual = Math.Min(amount, MaxMana - Mana);
            Mana += actual;
            return actual;
        }

        private void OnDeath()
        {
            StatTracker.RecordDeath();
            StatusManager.ClearAll();
            // Phase 4: Respawn logic, item drop, etc.
        }

        /// <summary>
        /// Update character systems each frame.
        /// </summary>
        public void Update(float dt)
        {
            // Update status effects
            StatusManager.Update(dt);

            // Update buffs
            Buffs.Update(dt);

            // Update skill cooldowns
            Skills.UpdateCooldowns(dt);

            // Update attack cooldowns
            if (AttackCooldown > 0) AttackCooldown -= dt;
            if (MainhandCooldown > 0) MainhandCooldown -= dt;
            if (OffhandCooldown > 0) OffhandCooldown -= dt;

            // Track damage timers
            TimeSinceLastDamageTaken += dt;
            TimeSinceLastDamageDealt += dt;

            // Health regen (5 HP/s after 5s without taking damage)
            if (TimeSinceLastDamageTaken >= HealthRegenThreshold && Health < MaxHealth && Health > 0)
            {
                float regenAmount = HealthRegenRate * dt;
                Health = Math.Min(MaxHealth, Health + regenAmount);
            }

            // Update knockback
            if (KnockbackDurationRemaining > 0)
            {
                KnockbackDurationRemaining -= dt;
                if (KnockbackDurationRemaining <= 0)
                {
                    KnockbackVelocityX = 0;
                    KnockbackVelocityY = 0;
                    KnockbackDurationRemaining = 0;
                }
            }
        }

        // === Equipment helpers ===

        private void GiveStartingTools()
        {
            var equipDb = EquipmentDatabase.GetInstance();
            if (!equipDb.Loaded) return;

            var copperAxe = equipDb.CreateEquipmentFromId("copper_axe");
            if (copperAxe != null)
                Equipment.Slots["axe"] = copperAxe;

            var copperPickaxe = equipDb.CreateEquipmentFromId("copper_pickaxe");
            if (copperPickaxe != null)
                Equipment.Slots["pickaxe"] = copperPickaxe;
        }

        private void GiveDebugItems()
        {
            Leveling.Level = LevelingSystem.MaxLevel;
            Leveling.UnallocatedStatPoints = 100;
            Inventory.AddItem("copper_ore", 50);
            Inventory.AddItem("iron_ore", 50);
            Inventory.AddItem("oak_log", 50);
            Inventory.AddItem("birch_log", 50);
        }

        // === Save/Load ===

        /// <summary>
        /// Serialize character to save data dictionary.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "version", "1.0" },
                { "position", new Dictionary<string, float>
                    {
                        { "x", Position.X }, { "y", Position.Y }, { "z", Position.Z }
                    }
                },
                { "facing", Facing },
                { "stats", Stats.ToSaveData() },
                { "leveling", Leveling.ToSaveData() },
                { "health", Health },
                { "mana", Mana },
                { "gold", Gold },
                { "class", _currentClassId },
                { "inventory", SerializeInventory() },
                { "equipment", SerializeEquipment() },
                { "equipped_skills", Skills.EquippedSkills.ToList() },
                { "known_skills", Skills.KnownSkills.ToDictionary(
                    kv => kv.Key,
                    kv => (object)new Dictionary<string, object>
                    {
                        { "level", kv.Value.Level },
                        { "experience", kv.Value.Experience }
                    })
                },
                { "titles", _earnedTitleIds.ToList() },
                { "activities", Activities.ToSaveData() },
                { "stat_tracker", StatTracker.ToSaveData() },
                { "invented_recipes", InventedRecipes },
            };
        }

        /// <summary>
        /// Restore character from save data.
        /// </summary>
        public void RestoreFromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return;

            // Position
            if (data.TryGetValue("position", out var posObj) && posObj is Dictionary<string, object> posData)
            {
                Position = new GamePosition(
                    Convert.ToSingle(posData.GetValueOrDefault("x", 0f)),
                    Convert.ToSingle(posData.GetValueOrDefault("y", 0f)),
                    Convert.ToSingle(posData.GetValueOrDefault("z", 0f))
                );
            }
            if (data.TryGetValue("facing", out var fObj)) Facing = fObj?.ToString() ?? "down";

            // Stats
            if (data.TryGetValue("stats", out var statsObj) && statsObj is Dictionary<string, object> statsData)
            {
                var intStats = statsData.ToDictionary(kv => kv.Key, kv => Convert.ToInt32(kv.Value));
                Stats.RestoreFromSaveData(intStats);
            }

            // Leveling
            if (data.TryGetValue("leveling", out var lvlObj) && lvlObj is Dictionary<string, object> lvlData)
                Leveling.RestoreFromSaveData(lvlData);

            // Class
            if (data.TryGetValue("class", out var classObj) && classObj != null)
                _currentClassId = classObj.ToString();

            // Recalculate before restoring health/mana
            RecalculateStats();

            // Health/Mana
            if (data.TryGetValue("health", out var hObj)) Health = Convert.ToSingle(hObj);
            if (data.TryGetValue("mana", out var mObj)) Mana = Convert.ToSingle(mObj);
            if (data.TryGetValue("gold", out var gObj)) Gold = Convert.ToInt32(gObj);

            // Activities
            if (data.TryGetValue("activities", out var actObj) && actObj is Dictionary<string, object> actData)
            {
                var intAct = actData.ToDictionary(kv => kv.Key, kv => Convert.ToInt32(kv.Value));
                Activities.RestoreFromSaveData(intAct);
            }

            // Titles
            if (data.TryGetValue("titles", out var titlesObj) && titlesObj is List<object> titlesList)
            {
                _earnedTitleIds.Clear();
                foreach (var tid in titlesList)
                    _earnedTitleIds.Add(tid.ToString());
            }

            // Known skills
            if (data.TryGetValue("known_skills", out var ksObj) && ksObj is Dictionary<string, object> ksData)
            {
                Skills.KnownSkills.Clear();
                foreach (var (skillId, infoObj) in ksData)
                {
                    Skills.LearnSkill(skillId, skipChecks: true);
                    if (infoObj is Dictionary<string, object> info && Skills.KnownSkills.TryGetValue(skillId, out var ps))
                    {
                        if (info.TryGetValue("level", out var lv)) ps.Level = Convert.ToInt32(lv);
                        if (info.TryGetValue("experience", out var ex)) ps.Experience = Convert.ToInt32(ex);
                    }
                }
            }

            // Equipped skills
            if (data.TryGetValue("equipped_skills", out var esObj) && esObj is List<object> esList)
            {
                for (int i = 0; i < Math.Min(5, esList.Count); i++)
                {
                    if (esList[i] != null)
                        Skills.EquipSkill(esList[i].ToString(), i);
                }
            }

            // Stat tracker
            if (data.TryGetValue("stat_tracker", out var stObj) && stObj is Dictionary<string, object> stData)
                StatTracker = StatTracker.FromSaveData(stData);
            else
            {
                StatTracker = new StatTracker();
                StatTracker.StartSession();
            }

            // Invented recipes
            if (data.TryGetValue("invented_recipes", out var irObj) && irObj is List<object> irList)
            {
                InventedRecipes.Clear();
                foreach (var item in irList)
                {
                    if (item is Dictionary<string, object> recipe)
                        InventedRecipes.Add(recipe);
                }
            }

            // Final recalculation
            RecalculateStats();
        }

        private List<object> SerializeInventory()
        {
            var result = new List<object>();
            foreach (var slot in Inventory.Slots)
            {
                if (slot == null) { result.Add(null); continue; }
                var slotData = new Dictionary<string, object>
                {
                    { "item_id", slot.ItemId },
                    { "quantity", slot.Quantity },
                    { "max_stack", slot.MaxStack },
                    { "rarity", slot.Rarity }
                };

                if (slot.EquipmentData != null)
                    slotData["equipment_data"] = slot.EquipmentData.ToSaveData();
                if (slot.CraftedStats != null)
                    slotData["crafted_stats"] = slot.CraftedStats.ToSaveData();

                result.Add(slotData);
            }
            return result;
        }

        private Dictionary<string, object> SerializeEquipment()
        {
            var result = new Dictionary<string, object>();
            foreach (var (slotName, item) in Equipment.Slots)
            {
                result[slotName] = item?.ToSaveData();
            }
            return result;
        }
    }
}
