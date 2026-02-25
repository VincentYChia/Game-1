// ============================================================================
// Game1.Unity.World.PrimitiveShapeFactory
// Created: 2026-02-25
//
// Creates low-fidelity 3D primitive shapes for world entities.
// Trees = cone+cylinder, Ores = cubes, Enemies = capsules, etc.
// All shapes are vertex-colored with no textures required.
// Provides a visual placeholder until proper 3D models are added.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Factory for creating colored 3D primitive GameObjects.
    /// Each method returns a ready-to-place GameObject with appropriate
    /// shape, color, scale, and optional child labels.
    /// </summary>
    public static class PrimitiveShapeFactory
    {
        // ====================================================================
        // Tier Colors
        // ====================================================================

        private static readonly Color[] TIER_COLORS = {
            new Color(0.65f, 0.65f, 0.65f), // T0 fallback
            new Color(0.55f, 0.75f, 0.55f), // T1 - green-gray
            new Color(0.45f, 0.65f, 0.85f), // T2 - blue
            new Color(0.70f, 0.45f, 0.85f), // T3 - purple
            new Color(0.90f, 0.70f, 0.20f), // T4 - gold
        };

        private static readonly Color[] ENEMY_TIER_COLORS = {
            new Color(0.70f, 0.35f, 0.35f), // T0 fallback
            new Color(0.78f, 0.40f, 0.40f), // T1 - red
            new Color(1.00f, 0.60f, 0.00f), // T2 - orange
            new Color(0.78f, 0.40f, 1.00f), // T3 - purple
            new Color(1.00f, 0.20f, 0.20f), // T4 - bright red
        };

        // Resource type colors
        private static readonly Dictionary<string, Color> RESOURCE_COLORS = new()
        {
            // Trees
            { "oak",       new Color(0.25f, 0.55f, 0.15f) },
            { "pine",      new Color(0.15f, 0.45f, 0.15f) },
            { "ash",       new Color(0.45f, 0.50f, 0.30f) },
            { "birch",     new Color(0.60f, 0.70f, 0.45f) },
            { "maple",     new Color(0.70f, 0.35f, 0.15f) },
            { "ironwood",  new Color(0.30f, 0.35f, 0.25f) },
            { "ebony",     new Color(0.15f, 0.12f, 0.10f) },
            { "worldtree", new Color(0.80f, 0.90f, 0.40f) },

            // Ores
            { "copper",      new Color(0.72f, 0.45f, 0.20f) },
            { "iron",        new Color(0.55f, 0.55f, 0.55f) },
            { "tin",         new Color(0.75f, 0.75f, 0.70f) },
            { "steel",       new Color(0.60f, 0.62f, 0.65f) },
            { "mithril",     new Color(0.60f, 0.75f, 0.90f) },
            { "adamantine",  new Color(0.30f, 0.35f, 0.50f) },
            { "orichalcum",  new Color(0.85f, 0.55f, 0.25f) },
            { "etherion",    new Color(0.55f, 0.30f, 0.80f) },

            // Stone
            { "limestone",  new Color(0.80f, 0.78f, 0.70f) },
            { "granite",    new Color(0.55f, 0.50f, 0.50f) },
            { "marble",     new Color(0.90f, 0.88f, 0.85f) },
            { "obsidian",   new Color(0.12f, 0.10f, 0.15f) },
            { "quartz",     new Color(0.85f, 0.85f, 0.90f) },
            { "diamond",    new Color(0.75f, 0.90f, 0.95f) },
            { "voidstone",  new Color(0.20f, 0.05f, 0.30f) },
        };

        // Station colors
        private static readonly Dictionary<string, Color> STATION_COLORS = new()
        {
            { "smithing",    new Color(0.75f, 0.35f, 0.15f) },
            { "alchemy",     new Color(0.30f, 0.65f, 0.45f) },
            { "refining",    new Color(0.65f, 0.55f, 0.30f) },
            { "engineering", new Color(0.45f, 0.50f, 0.60f) },
            { "enchanting",  new Color(0.55f, 0.30f, 0.75f) },
            { "adornments",  new Color(0.55f, 0.30f, 0.75f) },
        };

        // ====================================================================
        // Resource Nodes
        // ====================================================================

        /// <summary>Create a tree (cone crown + cylinder trunk).</summary>
        public static GameObject CreateTree(string resourceType, int tier)
        {
            var root = new GameObject($"Tree_{resourceType}");
            Color crownColor = GetResourceColor(resourceType);
            float scale = 0.8f + tier * 0.2f;

            // Trunk (cylinder)
            var trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            trunk.name = "Trunk";
            trunk.transform.SetParent(root.transform, false);
            trunk.transform.localScale = new Vector3(0.15f * scale, 0.5f * scale, 0.15f * scale);
            trunk.transform.localPosition = new Vector3(0, 0.5f * scale, 0);
            SetPrimitiveColor(trunk, new Color(0.40f, 0.28f, 0.15f));
            RemoveCollider(trunk);

            // Crown (sphere for soft look)
            var crown = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            crown.name = "Crown";
            crown.transform.SetParent(root.transform, false);
            crown.transform.localScale = new Vector3(0.7f * scale, 0.9f * scale, 0.7f * scale);
            crown.transform.localPosition = new Vector3(0, 1.2f * scale, 0);
            SetPrimitiveColor(crown, crownColor);
            RemoveCollider(crown);

            // Main collider on root
            var col = root.AddComponent<CapsuleCollider>();
            col.center = new Vector3(0, 0.8f * scale, 0);
            col.height = 2f * scale;
            col.radius = 0.35f * scale;

            return root;
        }

        /// <summary>Create an ore node (angular cube cluster).</summary>
        public static GameObject CreateOre(string resourceType, int tier)
        {
            var root = new GameObject($"Ore_{resourceType}");
            Color oreColor = GetResourceColor(resourceType);
            float scale = 0.4f + tier * 0.1f;

            // Main rock
            var main = GameObject.CreatePrimitive(PrimitiveType.Cube);
            main.name = "MainRock";
            main.transform.SetParent(root.transform, false);
            main.transform.localScale = new Vector3(0.5f * scale, 0.4f * scale, 0.45f * scale);
            main.transform.localPosition = new Vector3(0, 0.2f * scale, 0);
            main.transform.localRotation = Quaternion.Euler(0, 25, 8);
            SetPrimitiveColor(main, oreColor);
            RemoveCollider(main);

            // Secondary rock
            var secondary = GameObject.CreatePrimitive(PrimitiveType.Cube);
            secondary.name = "SecondaryRock";
            secondary.transform.SetParent(root.transform, false);
            secondary.transform.localScale = new Vector3(0.35f * scale, 0.3f * scale, 0.3f * scale);
            secondary.transform.localPosition = new Vector3(0.15f * scale, 0.15f * scale, 0.1f * scale);
            secondary.transform.localRotation = Quaternion.Euler(10, -15, 5);
            SetPrimitiveColor(secondary, oreColor * 0.85f);
            RemoveCollider(secondary);

            // Glint on higher tiers
            if (tier >= 3)
            {
                var glint = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                glint.name = "Glint";
                glint.transform.SetParent(root.transform, false);
                glint.transform.localScale = Vector3.one * 0.08f * scale;
                glint.transform.localPosition = new Vector3(0.1f, 0.35f * scale, 0.1f);
                SetPrimitiveColor(glint, Color.white);
                RemoveCollider(glint);
            }

            var col = root.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 0.2f * scale, 0);
            col.size = new Vector3(0.6f * scale, 0.5f * scale, 0.5f * scale);

            return root;
        }

        /// <summary>Create a stone outcrop.</summary>
        public static GameObject CreateStone(string resourceType, int tier)
        {
            var root = new GameObject($"Stone_{resourceType}");
            Color stoneColor = GetResourceColor(resourceType);
            float scale = 0.5f + tier * 0.15f;

            var rock = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            rock.name = "Rock";
            rock.transform.SetParent(root.transform, false);
            rock.transform.localScale = new Vector3(0.6f * scale, 0.4f * scale, 0.55f * scale);
            rock.transform.localPosition = new Vector3(0, 0.2f * scale, 0);
            SetPrimitiveColor(rock, stoneColor);
            RemoveCollider(rock);

            var col = root.AddComponent<SphereCollider>();
            col.center = new Vector3(0, 0.2f * scale, 0);
            col.radius = 0.3f * scale;

            return root;
        }

        /// <summary>Create a fishing spot indicator (flat disc on water).</summary>
        public static GameObject CreateFishingSpot(int tier)
        {
            var root = new GameObject($"FishingSpot_T{tier}");

            var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            disc.name = "WaterDisc";
            disc.transform.SetParent(root.transform, false);
            disc.transform.localScale = new Vector3(0.8f, 0.02f, 0.8f);
            disc.transform.localPosition = new Vector3(0, 0.01f, 0);

            Color spotColor = new Color(0.2f, 0.5f + tier * 0.1f, 0.9f, 0.5f);
            SetPrimitiveColor(disc, spotColor);
            RemoveCollider(disc);

            var col = root.AddComponent<CapsuleCollider>();
            col.center = Vector3.zero;
            col.radius = 0.5f;
            col.height = 0.1f;

            return root;
        }

        /// <summary>Auto-detect resource category and create appropriate shape.</summary>
        public static GameObject CreateResource(string resourceId, int tier)
        {
            string lower = resourceId.ToLowerInvariant();

            if (lower.Contains("tree") || lower.Contains("sapling"))
                return CreateTree(resourceId, tier);
            if (lower.Contains("vein") || lower.Contains("deposit") || lower.Contains("seam") ||
                lower.Contains("node") || lower.Contains("cache") || lower.Contains("lode") ||
                lower.Contains("trove") || lower.Contains("nexus"))
                return CreateOre(resourceId, tier);
            if (lower.Contains("outcrop") || lower.Contains("formation") || lower.Contains("bed") ||
                lower.Contains("column") || lower.Contains("quarry") || lower.Contains("cluster") ||
                lower.Contains("flow") || lower.Contains("shard") || lower.Contains("geode") ||
                lower.Contains("monolith") || lower.Contains("structure"))
                return CreateStone(resourceId, tier);
            if (lower.Contains("fish") || lower.Contains("carp") || lower.Contains("fin") ||
                lower.Contains("koi") || lower.Contains("leviathan"))
                return CreateFishingSpot(tier);

            // Fallback: small sphere
            return CreateStone(resourceId, tier);
        }

        // ====================================================================
        // Enemies
        // ====================================================================

        /// <summary>Create an enemy (colored capsule with "eyes").</summary>
        public static GameObject CreateEnemy(int tier, bool isBoss = false)
        {
            var root = new GameObject("Enemy");
            Color bodyColor = GetEnemyTierColor(tier);
            float scale = isBoss ? 1.5f : 0.8f + tier * 0.1f;

            // Body (capsule)
            var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            body.name = "Body";
            body.transform.SetParent(root.transform, false);
            body.transform.localScale = new Vector3(0.4f * scale, 0.5f * scale, 0.4f * scale);
            body.transform.localPosition = new Vector3(0, 0.5f * scale, 0);
            SetPrimitiveColor(body, bodyColor);
            RemoveCollider(body);

            // Eyes (two small white spheres)
            for (int i = 0; i < 2; i++)
            {
                var eye = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                eye.name = $"Eye{i}";
                eye.transform.SetParent(root.transform, false);
                float xOff = (i == 0 ? -0.08f : 0.08f) * scale;
                eye.transform.localScale = Vector3.one * 0.06f * scale;
                eye.transform.localPosition = new Vector3(xOff, 0.8f * scale, 0.17f * scale);
                SetPrimitiveColor(eye, Color.white);
                RemoveCollider(eye);

                // Pupil
                var pupil = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                pupil.name = "Pupil";
                pupil.transform.SetParent(eye.transform, false);
                pupil.transform.localScale = Vector3.one * 0.5f;
                pupil.transform.localPosition = new Vector3(0, 0, 0.4f);
                SetPrimitiveColor(pupil, Color.black);
                RemoveCollider(pupil);
            }

            // Boss crown
            if (isBoss)
            {
                var crown = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                crown.name = "Crown";
                crown.transform.SetParent(root.transform, false);
                crown.transform.localScale = new Vector3(0.25f * scale, 0.06f * scale, 0.25f * scale);
                crown.transform.localPosition = new Vector3(0, 1.05f * scale, 0);
                SetPrimitiveColor(crown, new Color(1f, 0.84f, 0f));
                RemoveCollider(crown);
            }

            var col = root.AddComponent<CapsuleCollider>();
            col.center = new Vector3(0, 0.5f * scale, 0);
            col.height = 1f * scale;
            col.radius = 0.25f * scale;

            return root;
        }

        // ====================================================================
        // Crafting Stations
        // ====================================================================

        /// <summary>Create a crafting station (colored box with label).</summary>
        public static GameObject CreateStation(string stationType, int tier)
        {
            var root = new GameObject($"Station_{stationType}_T{tier}");
            Color baseColor = GetStationColor(stationType);
            float scale = 0.7f + tier * 0.1f;

            // Base block
            var block = GameObject.CreatePrimitive(PrimitiveType.Cube);
            block.name = "Base";
            block.transform.SetParent(root.transform, false);
            block.transform.localScale = new Vector3(0.7f * scale, 0.5f * scale, 0.7f * scale);
            block.transform.localPosition = new Vector3(0, 0.25f * scale, 0);
            SetPrimitiveColor(block, baseColor);
            RemoveCollider(block);

            // Top surface (lighter)
            var top = GameObject.CreatePrimitive(PrimitiveType.Cube);
            top.name = "Top";
            top.transform.SetParent(root.transform, false);
            top.transform.localScale = new Vector3(0.75f * scale, 0.05f * scale, 0.75f * scale);
            top.transform.localPosition = new Vector3(0, 0.52f * scale, 0);
            SetPrimitiveColor(top, baseColor * 1.3f);
            RemoveCollider(top);

            // Tier indicator (small colored sphere)
            var indicator = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            indicator.name = "TierIndicator";
            indicator.transform.SetParent(root.transform, false);
            indicator.transform.localScale = Vector3.one * 0.08f;
            indicator.transform.localPosition = new Vector3(0, 0.6f * scale, 0);
            SetPrimitiveColor(indicator, GetTierColor(tier));
            RemoveCollider(indicator);

            var col = root.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 0.25f * scale, 0);
            col.size = new Vector3(0.75f * scale, 0.55f * scale, 0.75f * scale);

            return root;
        }

        // ====================================================================
        // NPCs
        // ====================================================================

        /// <summary>Create an NPC (blue capsule with name tag).</summary>
        public static GameObject CreateNPC()
        {
            var root = new GameObject("NPC");

            var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            body.name = "Body";
            body.transform.SetParent(root.transform, false);
            body.transform.localScale = new Vector3(0.35f, 0.5f, 0.35f);
            body.transform.localPosition = new Vector3(0, 0.5f, 0);
            SetPrimitiveColor(body, new Color(0.30f, 0.50f, 0.80f));
            RemoveCollider(body);

            // Head
            var head = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            head.name = "Head";
            head.transform.SetParent(root.transform, false);
            head.transform.localScale = new Vector3(0.25f, 0.25f, 0.25f);
            head.transform.localPosition = new Vector3(0, 1.1f, 0);
            SetPrimitiveColor(head, new Color(0.85f, 0.72f, 0.58f));
            RemoveCollider(head);

            var col = root.AddComponent<CapsuleCollider>();
            col.center = new Vector3(0, 0.6f, 0);
            col.height = 1.4f;
            col.radius = 0.25f;

            return root;
        }

        // ====================================================================
        // Dungeon Portals
        // ====================================================================

        /// <summary>Create a dungeon portal (glowing sphere).</summary>
        public static GameObject CreateDungeonPortal(Color rarityColor)
        {
            var root = new GameObject("DungeonPortal");

            // Outer glow
            var outer = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            outer.name = "Glow";
            outer.transform.SetParent(root.transform, false);
            outer.transform.localScale = Vector3.one * 0.9f;
            outer.transform.localPosition = new Vector3(0, 0.5f, 0);
            Color glowColor = rarityColor;
            glowColor.a = 0.4f;
            SetPrimitiveColor(outer, glowColor);
            RemoveCollider(outer);

            // Inner core
            var inner = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            inner.name = "Core";
            inner.transform.SetParent(root.transform, false);
            inner.transform.localScale = Vector3.one * 0.5f;
            inner.transform.localPosition = new Vector3(0, 0.5f, 0);
            SetPrimitiveColor(inner, new Color(0.12f, 0.12f, 0.15f));
            RemoveCollider(inner);

            // Ring
            var ring = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            ring.name = "Ring";
            ring.transform.SetParent(root.transform, false);
            ring.transform.localScale = new Vector3(1f, 0.03f, 1f);
            ring.transform.localPosition = new Vector3(0, 0.5f, 0);
            SetPrimitiveColor(ring, rarityColor);
            RemoveCollider(ring);

            var col = root.AddComponent<SphereCollider>();
            col.center = new Vector3(0, 0.5f, 0);
            col.radius = 0.5f;

            return root;
        }

        // ====================================================================
        // Chests
        // ====================================================================

        /// <summary>Create a chest (box with lid).</summary>
        public static GameObject CreateChest(Color chestColor)
        {
            var root = new GameObject("Chest");

            // Body
            var body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.name = "Body";
            body.transform.SetParent(root.transform, false);
            body.transform.localScale = new Vector3(0.5f, 0.3f, 0.35f);
            body.transform.localPosition = new Vector3(0, 0.15f, 0);
            SetPrimitiveColor(body, chestColor);
            RemoveCollider(body);

            // Lid
            var lid = GameObject.CreatePrimitive(PrimitiveType.Cube);
            lid.name = "Lid";
            lid.transform.SetParent(root.transform, false);
            lid.transform.localScale = new Vector3(0.52f, 0.08f, 0.37f);
            lid.transform.localPosition = new Vector3(0, 0.34f, 0);
            SetPrimitiveColor(lid, chestColor * 1.15f);
            RemoveCollider(lid);

            // Lock
            var lockObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            lockObj.name = "Lock";
            lockObj.transform.SetParent(root.transform, false);
            lockObj.transform.localScale = Vector3.one * 0.06f;
            lockObj.transform.localPosition = new Vector3(0, 0.28f, 0.18f);
            SetPrimitiveColor(lockObj, new Color(0.85f, 0.75f, 0.20f));
            RemoveCollider(lockObj);

            var col = root.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 0.2f, 0);
            col.size = new Vector3(0.55f, 0.4f, 0.4f);

            return root;
        }

        // ====================================================================
        // Dropped Items
        // ====================================================================

        /// <summary>Create a dropped item pickup (small glowing sphere).</summary>
        public static GameObject CreateDroppedItem()
        {
            var root = new GameObject("DroppedItem");

            var sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere.name = "ItemOrb";
            sphere.transform.SetParent(root.transform, false);
            sphere.transform.localScale = Vector3.one * 0.2f;
            sphere.transform.localPosition = new Vector3(0, 0.15f, 0);
            SetPrimitiveColor(sphere, new Color(1f, 0.84f, 0f, 0.9f));
            RemoveCollider(sphere);

            var col = root.AddComponent<SphereCollider>();
            col.center = new Vector3(0, 0.15f, 0);
            col.radius = 0.15f;
            col.isTrigger = true;

            return root;
        }

        // ====================================================================
        // World-Space Labels
        // ====================================================================

        /// <summary>Add a floating text label above an entity.</summary>
        public static void AddWorldLabel(GameObject entity, string text, Color color,
            float yOffset = 1.5f, float scale = 0.008f)
        {
            var canvasGo = new GameObject("LabelCanvas");
            canvasGo.transform.SetParent(entity.transform, false);
            canvasGo.transform.localPosition = new Vector3(0, yOffset, 0);

            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            var rt = canvasGo.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(200, 40);
            rt.localScale = Vector3.one * scale;

            var textGo = new GameObject("Text");
            textGo.transform.SetParent(canvasGo.transform, false);
            var textRt = textGo.AddComponent<RectTransform>();
            textRt.anchorMin = Vector2.zero;
            textRt.anchorMax = Vector2.one;
            textRt.offsetMin = Vector2.zero;
            textRt.offsetMax = Vector2.zero;

            var textComp = textGo.AddComponent<UnityEngine.UI.Text>();
            textComp.text = text;
            textComp.fontSize = 24;
            textComp.color = color;
            textComp.alignment = TextAnchor.MiddleCenter;
            textComp.font = Resources.GetBuiltinResource<Font>("LegacySRuntime.ttf");
            if (textComp.font == null)
                textComp.font = Font.CreateDynamicFontFromOSFont("Arial", 24);
            textComp.horizontalOverflow = HorizontalWrapMode.Overflow;
            textComp.raycastTarget = false;

            // Billboard behavior: face camera every frame
            canvasGo.AddComponent<BillboardLabel>();
        }

        /// <summary>Add a world-space health bar above an entity.</summary>
        public static (Canvas canvas, UnityEngine.UI.Image fill) AddWorldHealthBar(
            GameObject entity, float yOffset = 1.2f, float width = 0.8f)
        {
            var canvasGo = new GameObject("HealthBarCanvas");
            canvasGo.transform.SetParent(entity.transform, false);
            canvasGo.transform.localPosition = new Vector3(0, yOffset, 0);

            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            var rt = canvasGo.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(100, 12);
            rt.localScale = Vector3.one * (width / 100f);

            // Background
            var bgGo = new GameObject("Background");
            bgGo.transform.SetParent(canvasGo.transform, false);
            var bgRt = bgGo.AddComponent<RectTransform>();
            bgRt.anchorMin = Vector2.zero;
            bgRt.anchorMax = Vector2.one;
            bgRt.offsetMin = Vector2.zero;
            bgRt.offsetMax = Vector2.zero;
            var bgImg = bgGo.AddComponent<UnityEngine.UI.Image>();
            bgImg.color = new Color(0.15f, 0.15f, 0.15f, 0.8f);

            // Fill
            var fillGo = new GameObject("Fill");
            fillGo.transform.SetParent(canvasGo.transform, false);
            var fillRt = fillGo.AddComponent<RectTransform>();
            fillRt.anchorMin = Vector2.zero;
            fillRt.anchorMax = Vector2.one;
            fillRt.offsetMin = new Vector2(1, 1);
            fillRt.offsetMax = new Vector2(-1, -1);
            var fillImg = fillGo.AddComponent<UnityEngine.UI.Image>();
            fillImg.color = new Color(0.2f, 0.8f, 0.2f);
            fillImg.type = UnityEngine.UI.Image.Type.Filled;
            fillImg.fillMethod = UnityEngine.UI.Image.FillMethod.Horizontal;
            fillImg.fillAmount = 1f;

            canvasGo.AddComponent<BillboardLabel>();

            canvasGo.SetActive(false); // Hidden by default, show when damaged

            return (canvas, fillImg);
        }

        // ====================================================================
        // Helpers
        // ====================================================================

        /// <summary>Set a primitive's material color (creates unlit material).</summary>
        public static void SetPrimitiveColor(GameObject obj, Color color)
        {
            var renderer = obj.GetComponent<Renderer>();
            if (renderer == null) return;

            // Use URP Lit if available, otherwise Standard
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");

            var mat = new Material(shader);
            mat.color = color;
            mat.SetFloat("_Smoothness", 0.3f);
            mat.SetFloat("_Metallic", 0f);

            if (color.a < 1f)
            {
                mat.SetFloat("_Surface", 1f);
                mat.SetOverrideTag("RenderType", "Transparent");
                mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                mat.SetInt("_ZWrite", 0);
                mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
                mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            }

            renderer.material = mat;
        }

        private static void RemoveCollider(GameObject obj)
        {
            var col = obj.GetComponent<Collider>();
            if (col != null) Object.Destroy(col);
        }

        public static Color GetResourceColor(string resourceId)
        {
            string lower = resourceId.ToLowerInvariant();
            foreach (var kvp in RESOURCE_COLORS)
            {
                if (lower.Contains(kvp.Key)) return kvp.Value;
            }
            return new Color(0.5f, 0.6f, 0.4f); // Default green-gray
        }

        public static Color GetTierColor(int tier)
        {
            tier = Mathf.Clamp(tier, 0, TIER_COLORS.Length - 1);
            return TIER_COLORS[tier];
        }

        public static Color GetEnemyTierColor(int tier)
        {
            tier = Mathf.Clamp(tier, 0, ENEMY_TIER_COLORS.Length - 1);
            return ENEMY_TIER_COLORS[tier];
        }

        public static Color GetStationColor(string stationType)
        {
            if (stationType != null && STATION_COLORS.TryGetValue(stationType.ToLowerInvariant(), out var color))
                return color;
            return new Color(0.5f, 0.5f, 0.5f);
        }
    }

    /// <summary>
    /// Simple billboard component that rotates to face the main camera each frame.
    /// Used for world-space labels and health bars.
    /// </summary>
    public class BillboardLabel : MonoBehaviour
    {
        private void LateUpdate()
        {
            if (Camera.main != null)
            {
                transform.rotation = Camera.main.transform.rotation;
            }
        }
    }
}
