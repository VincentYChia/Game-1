// Game1.Data.Models.NPCDefinition
// Migrated from: data/models/npcs.py (17 lines)
// Phase: 1 - Foundation
// Depends on: GamePosition (intra-phase dependency)

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// NPC template from JSON. Pure data - no methods.
    /// </summary>
    [Serializable]
    public class NPCDefinition
    {
        [JsonProperty("npcId")]
        public string NpcId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("position")]
        public GamePosition Position { get; set; }

        [JsonProperty("spriteColor")]
        public int[] SpriteColor { get; set; } = new[] { 0, 0, 0 };

        [JsonProperty("interactionRadius")]
        public float InteractionRadius { get; set; }

        [JsonProperty("dialogueLines")]
        public List<string> DialogueLines { get; set; } = new();

        [JsonProperty("quests")]
        public List<string> Quests { get; set; } = new();

        // Helper for color tuple access
        public (int R, int G, int B) GetSpriteColor() =>
            (SpriteColor.Length > 0 ? SpriteColor[0] : 0,
             SpriteColor.Length > 1 ? SpriteColor[1] : 0,
             SpriteColor.Length > 2 ? SpriteColor[2] : 0);
    }
}
