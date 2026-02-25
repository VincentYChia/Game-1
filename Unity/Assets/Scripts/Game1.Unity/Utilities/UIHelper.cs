// ============================================================================
// Game1.Unity.Utilities.UIHelper
// Created: 2026-02-25
//
// Static utility class for programmatic UI construction.
// Creates Canvas hierarchies, panels, buttons, sliders, grids, and text
// elements entirely from code — no prefabs or scene file required.
// Used by SceneBootstrapper and individual UI scripts' _buildUI() methods.
// ============================================================================

using System;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

namespace Game1.Unity.Utilities
{
    /// <summary>
    /// Programmatic UI element factory. Every method returns the created
    /// component so callers can chain or cache references.
    /// </summary>
    public static class UIHelper
    {
        // ====================================================================
        // Color Palette (matches Python game's color scheme)
        // ====================================================================

        public static readonly Color COLOR_BG_DARK      = new Color(0.08f, 0.08f, 0.12f, 0.95f);
        public static readonly Color COLOR_BG_PANEL      = new Color(0.12f, 0.12f, 0.18f, 0.95f);
        public static readonly Color COLOR_BG_HEADER     = new Color(0.15f, 0.15f, 0.22f, 1f);
        public static readonly Color COLOR_BG_SLOT       = new Color(0.18f, 0.20f, 0.28f, 1f);
        public static readonly Color COLOR_BG_SLOT_HOVER = new Color(0.25f, 0.28f, 0.38f, 1f);
        public static readonly Color COLOR_BG_BUTTON     = new Color(0.20f, 0.25f, 0.35f, 1f);
        public static readonly Color COLOR_BG_BUTTON_HOVER = new Color(0.28f, 0.35f, 0.50f, 1f);
        public static readonly Color COLOR_BORDER        = new Color(0.35f, 0.38f, 0.50f, 1f);
        public static readonly Color COLOR_TEXT_PRIMARY   = new Color(0.90f, 0.90f, 0.90f, 1f);
        public static readonly Color COLOR_TEXT_SECONDARY = new Color(0.65f, 0.65f, 0.70f, 1f);
        public static readonly Color COLOR_TEXT_GOLD      = new Color(1f, 0.84f, 0f, 1f);
        public static readonly Color COLOR_TEXT_GREEN     = new Color(0.30f, 0.85f, 0.30f, 1f);
        public static readonly Color COLOR_TEXT_RED       = new Color(0.85f, 0.25f, 0.25f, 1f);
        public static readonly Color COLOR_HP_FULL        = new Color(0.20f, 0.80f, 0.20f, 1f);
        public static readonly Color COLOR_HP_LOW         = new Color(0.80f, 0.15f, 0.15f, 1f);
        public static readonly Color COLOR_MANA           = new Color(0.25f, 0.50f, 0.90f, 1f);
        public static readonly Color COLOR_EXP            = new Color(0.70f, 0.55f, 0.90f, 1f);
        public static readonly Color COLOR_COOLDOWN       = new Color(0f, 0f, 0f, 0.65f);
        public static readonly Color COLOR_TRANSPARENT    = new Color(0f, 0f, 0f, 0f);

        // ====================================================================
        // Cached Font
        // ====================================================================

        private static Font _cachedFont;

        /// <summary>
        /// Get a usable font, trying multiple builtin resource names across Unity versions.
        /// Cached after first successful lookup.
        /// </summary>
        public static Font GetFont()
        {
            if (_cachedFont != null) return _cachedFont;

            // Unity 2023+: LegacyRuntime.ttf
            _cachedFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (_cachedFont != null) return _cachedFont;

            // Unity 2019-2022: Arial.ttf
            _cachedFont = Resources.GetBuiltinResource<Font>("Arial.ttf");
            if (_cachedFont != null) return _cachedFont;

            // OS font fallback
            _cachedFont = Font.CreateDynamicFontFromOSFont("Arial", 14);
            if (_cachedFont != null) return _cachedFont;

            // Last resort: any available OS font
            string[] available = Font.GetOSInstalledFontNames();
            if (available != null && available.Length > 0)
                _cachedFont = Font.CreateDynamicFontFromOSFont(available[0], 14);

            return _cachedFont;
        }

        // Rarity colors
        public static readonly Color COLOR_COMMON    = new Color(0.60f, 0.60f, 0.60f, 1f);
        public static readonly Color COLOR_UNCOMMON  = new Color(0.20f, 0.80f, 0.20f, 1f);
        public static readonly Color COLOR_RARE      = new Color(0.20f, 0.45f, 1f, 1f);
        public static readonly Color COLOR_EPIC      = new Color(0.70f, 0.25f, 1f, 1f);
        public static readonly Color COLOR_LEGENDARY = new Color(1f, 0.65f, 0f, 1f);

        // ====================================================================
        // Canvas Creation
        // ====================================================================

        /// <summary>Create a Screen Space Overlay canvas with sorting order.</summary>
        public static Canvas CreateCanvas(string name, int sortOrder, Transform parent = null)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);

            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = sortOrder;

            var scaler = go.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;

            go.AddComponent<GraphicRaycaster>();
            return canvas;
        }

        /// <summary>Create a World Space canvas (for health bars, labels).</summary>
        public static Canvas CreateWorldCanvas(string name, Transform parent, Vector2 size)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = Vector3.up * 1.2f;

            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = size;
            rt.localScale = Vector3.one * 0.01f;

            go.AddComponent<GraphicRaycaster>();
            return canvas;
        }

        /// <summary>Ensure an EventSystem exists in the scene.</summary>
        public static void EnsureEventSystem()
        {
            if (UnityEngine.EventSystems.EventSystem.current != null) return;

            var go = new GameObject("EventSystem");
            go.AddComponent<EventSystem>();
            go.AddComponent<StandaloneInputModule>();
        }

        // ====================================================================
        // Panel / Container
        // ====================================================================

        /// <summary>Create a panel with background image.</summary>
        public static RectTransform CreatePanel(Transform parent, string name, Color bgColor,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin = default, Vector2 offsetMax = default)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = offsetMin;
            rt.offsetMax = offsetMax;

            var img = go.AddComponent<Image>();
            img.color = bgColor;
            img.raycastTarget = true;

            return rt;
        }

        /// <summary>Create a panel with explicit size and anchored position.</summary>
        public static RectTransform CreateSizedPanel(Transform parent, string name, Color bgColor,
            Vector2 size, Vector2 anchoredPosition, Vector2 pivot = default)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.sizeDelta = size;
            rt.anchoredPosition = anchoredPosition;
            if (pivot != default) rt.pivot = pivot;

            var img = go.AddComponent<Image>();
            img.color = bgColor;
            img.raycastTarget = true;

            return rt;
        }

        /// <summary>Create an empty container (no background).</summary>
        public static RectTransform CreateContainer(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            return rt;
        }

        /// <summary>Stretch a RectTransform to fill its parent.</summary>
        public static void StretchFill(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }

        // ====================================================================
        // Text
        // ====================================================================

        /// <summary>Create a UI Text element.</summary>
        public static Text CreateText(Transform parent, string name, string text,
            int fontSize, Color color, TextAnchor alignment = TextAnchor.MiddleLeft)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            StretchFill(rt);

            var txt = go.AddComponent<Text>();
            txt.text = text;
            txt.fontSize = fontSize;
            txt.color = color;
            txt.alignment = alignment;
            txt.font = GetFont();
            txt.supportRichText = true;
            txt.raycastTarget = false;

            return txt;
        }

        /// <summary>Create a text element with explicit size and position.</summary>
        public static Text CreateSizedText(Transform parent, string name, string text,
            int fontSize, Color color, Vector2 size, Vector2 anchoredPosition,
            TextAnchor alignment = TextAnchor.MiddleLeft)
        {
            var txt = CreateText(parent, name, text, fontSize, color, alignment);
            var rt = txt.rectTransform;
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = anchoredPosition;
            return txt;
        }

        // ====================================================================
        // Image
        // ====================================================================

        /// <summary>Create a simple colored image.</summary>
        public static Image CreateImage(Transform parent, string name, Color color,
            Vector2 size = default)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            if (size != default) rt.sizeDelta = size;
            else StretchFill(rt);

            var img = go.AddComponent<Image>();
            img.color = color;

            return img;
        }

        /// <summary>Create a filled image (for progress bars).</summary>
        public static Image CreateFilledImage(Transform parent, string name, Color color,
            Image.FillMethod fillMethod = Image.FillMethod.Horizontal)
        {
            var img = CreateImage(parent, name, color);
            img.type = Image.Type.Filled;
            img.fillMethod = fillMethod;
            img.fillAmount = 1f;
            return img;
        }

        // ====================================================================
        // Button
        // ====================================================================

        /// <summary>Create a button with text label.</summary>
        public static Button CreateButton(Transform parent, string name, string label,
            Color bgColor, Color textColor, int fontSize = 16, Action onClick = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            StretchFill(rt);

            var img = go.AddComponent<Image>();
            img.color = bgColor;

            var btn = go.AddComponent<Button>();
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
            colors.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
            btn.colors = colors;

            if (onClick != null)
                btn.onClick.AddListener(() => onClick());

            // Label text
            var txtGo = new GameObject("Label");
            txtGo.transform.SetParent(go.transform, false);
            var txtRt = txtGo.AddComponent<RectTransform>();
            StretchFill(txtRt);
            var txt = txtGo.AddComponent<Text>();
            txt.text = label;
            txt.fontSize = fontSize;
            txt.color = textColor;
            txt.alignment = TextAnchor.MiddleCenter;
            txt.font = GetFont();
            txt.raycastTarget = false;

            return btn;
        }

        /// <summary>Create a button with explicit size.</summary>
        public static Button CreateSizedButton(Transform parent, string name, string label,
            Color bgColor, Color textColor, Vector2 size, Vector2 anchoredPosition,
            int fontSize = 16, Action onClick = null)
        {
            var btn = CreateButton(parent, name, label, bgColor, textColor, fontSize, onClick);
            var rt = btn.GetComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = anchoredPosition;
            return btn;
        }

        // ====================================================================
        // Slider / Progress Bar
        // ====================================================================

        /// <summary>Create a progress bar (background + fill).</summary>
        public static (RectTransform root, Image background, Image fill, Text label)
            CreateProgressBar(Transform parent, string name, Color bgColor, Color fillColor,
                Vector2 size, Vector2 anchoredPosition)
        {
            // Root
            var rootGo = new GameObject(name);
            rootGo.transform.SetParent(parent, false);
            var rootRt = rootGo.AddComponent<RectTransform>();
            rootRt.anchorMin = new Vector2(0.5f, 0.5f);
            rootRt.anchorMax = new Vector2(0.5f, 0.5f);
            rootRt.sizeDelta = size;
            rootRt.anchoredPosition = anchoredPosition;

            // Background
            var bgImg = rootGo.AddComponent<Image>();
            bgImg.color = bgColor;

            // Fill area
            var fillGo = new GameObject("Fill");
            fillGo.transform.SetParent(rootGo.transform, false);
            var fillRt = fillGo.AddComponent<RectTransform>();
            fillRt.anchorMin = Vector2.zero;
            fillRt.anchorMax = Vector2.one;
            fillRt.offsetMin = new Vector2(2, 2);
            fillRt.offsetMax = new Vector2(-2, -2);

            var fillImg = fillGo.AddComponent<Image>();
            fillImg.color = fillColor;
            fillImg.type = Image.Type.Filled;
            fillImg.fillMethod = Image.FillMethod.Horizontal;
            fillImg.fillAmount = 1f;

            // Label
            var labelTxt = CreateText(rootGo.transform, "Label", "",
                Mathf.Max(10, (int)(size.y * 0.6f)), COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);

            return (rootRt, bgImg, fillImg, labelTxt);
        }

        // ====================================================================
        // Grid Layout
        // ====================================================================

        /// <summary>Create a grid layout container.</summary>
        public static GridLayoutGroup CreateGridLayout(Transform parent, string name,
            int columns, Vector2 cellSize, Vector2 spacing, RectOffset padding = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            StretchFill(rt);

            var grid = go.AddComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = columns;
            grid.cellSize = cellSize;
            grid.spacing = spacing;
            grid.childAlignment = TextAnchor.UpperLeft;
            if (padding != null) grid.padding = padding;

            return grid;
        }

        // ====================================================================
        // Scroll View
        // ====================================================================

        /// <summary>Create a scrollable content area.</summary>
        public static (ScrollRect scrollRect, RectTransform content)
            CreateScrollView(Transform parent, string name, Color bgColor = default)
        {
            // Viewport
            var viewportGo = new GameObject(name);
            viewportGo.transform.SetParent(parent, false);
            var viewportRt = viewportGo.AddComponent<RectTransform>();
            StretchFill(viewportRt);
            var viewportImg = viewportGo.AddComponent<Image>();
            viewportImg.color = bgColor == default ? COLOR_TRANSPARENT : bgColor;
            var mask = viewportGo.AddComponent<Mask>();
            mask.showMaskGraphic = bgColor != default;

            // Content
            var contentGo = new GameObject("Content");
            contentGo.transform.SetParent(viewportGo.transform, false);
            var contentRt = contentGo.AddComponent<RectTransform>();
            contentRt.anchorMin = new Vector2(0, 1);
            contentRt.anchorMax = new Vector2(1, 1);
            contentRt.pivot = new Vector2(0.5f, 1);
            contentRt.offsetMin = new Vector2(0, 0);
            contentRt.offsetMax = new Vector2(0, 0);

            var csf = contentGo.AddComponent<ContentSizeFitter>();
            csf.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var vlg = contentGo.AddComponent<VerticalLayoutGroup>();
            vlg.childForceExpandWidth = true;
            vlg.childForceExpandHeight = false;
            vlg.spacing = 4;
            vlg.padding = new RectOffset(4, 4, 4, 4);

            // ScrollRect
            var scrollRect = viewportGo.AddComponent<ScrollRect>();
            scrollRect.content = contentRt;
            scrollRect.viewport = viewportRt;
            scrollRect.horizontal = false;
            scrollRect.vertical = true;
            scrollRect.movementType = ScrollRect.MovementType.Clamped;
            scrollRect.scrollSensitivity = 30f;

            return (scrollRect, contentRt);
        }

        // ====================================================================
        // Inventory / Equipment Slot
        // ====================================================================

        /// <summary>Create an inventory-style slot with icon, quantity badge, and border.</summary>
        public static (RectTransform root, Image background, Image icon, Text quantity, Image border)
            CreateItemSlot(Transform parent, string name, float size)
        {
            // Root
            var rootGo = new GameObject(name);
            rootGo.transform.SetParent(parent, false);
            var rootRt = rootGo.AddComponent<RectTransform>();
            rootRt.sizeDelta = new Vector2(size, size);

            // Background
            var bgImg = rootGo.AddComponent<Image>();
            bgImg.color = COLOR_BG_SLOT;
            bgImg.raycastTarget = true;

            // Icon
            var iconGo = new GameObject("Icon");
            iconGo.transform.SetParent(rootGo.transform, false);
            var iconRt = iconGo.AddComponent<RectTransform>();
            iconRt.anchorMin = Vector2.zero;
            iconRt.anchorMax = Vector2.one;
            iconRt.offsetMin = new Vector2(4, 4);
            iconRt.offsetMax = new Vector2(-4, -4);
            var iconImg = iconGo.AddComponent<Image>();
            iconImg.color = Color.white;
            iconImg.preserveAspect = true;
            iconImg.raycastTarget = false;
            iconImg.enabled = false;

            // Quantity badge (bottom-right)
            var qtyGo = new GameObject("Quantity");
            qtyGo.transform.SetParent(rootGo.transform, false);
            var qtyRt = qtyGo.AddComponent<RectTransform>();
            qtyRt.anchorMin = new Vector2(1, 0);
            qtyRt.anchorMax = new Vector2(1, 0);
            qtyRt.pivot = new Vector2(1, 0);
            qtyRt.sizeDelta = new Vector2(size * 0.5f, size * 0.3f);
            qtyRt.anchoredPosition = new Vector2(-2, 2);
            var qtyTxt = qtyGo.AddComponent<Text>();
            qtyTxt.fontSize = Mathf.Max(10, (int)(size * 0.22f));
            qtyTxt.color = COLOR_TEXT_PRIMARY;
            qtyTxt.alignment = TextAnchor.LowerRight;
            qtyTxt.font = GetFont();
            qtyTxt.raycastTarget = false;

            // Border (overlay, initially invisible)
            var borderGo = new GameObject("Border");
            borderGo.transform.SetParent(rootGo.transform, false);
            var borderRt = borderGo.AddComponent<RectTransform>();
            StretchFill(borderRt);
            var borderImg = borderGo.AddComponent<Image>();
            borderImg.color = COLOR_TRANSPARENT;
            borderImg.raycastTarget = false;
            // Use outline component for border effect
            var outline = borderGo.AddComponent<Outline>();
            outline.effectColor = COLOR_BORDER;
            outline.effectDistance = new Vector2(2, 2);

            return (rootRt, bgImg, iconImg, qtyTxt, borderImg);
        }

        // ====================================================================
        // Input Field
        // ====================================================================

        /// <summary>Create a text input field.</summary>
        public static InputField CreateInputField(Transform parent, string name,
            string placeholder, Vector2 size, Vector2 anchoredPosition, int fontSize = 16)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = anchoredPosition;

            var bgImg = go.AddComponent<Image>();
            bgImg.color = new Color(0.15f, 0.15f, 0.20f, 1f);

            // Text
            var textGo = new GameObject("Text");
            textGo.transform.SetParent(go.transform, false);
            var textRt = textGo.AddComponent<RectTransform>();
            textRt.anchorMin = Vector2.zero;
            textRt.anchorMax = Vector2.one;
            textRt.offsetMin = new Vector2(8, 2);
            textRt.offsetMax = new Vector2(-8, -2);
            var textComp = textGo.AddComponent<Text>();
            textComp.fontSize = fontSize;
            textComp.color = COLOR_TEXT_PRIMARY;
            textComp.font = GetFont();
            textComp.supportRichText = false;

            // Placeholder
            var phGo = new GameObject("Placeholder");
            phGo.transform.SetParent(go.transform, false);
            var phRt = phGo.AddComponent<RectTransform>();
            phRt.anchorMin = Vector2.zero;
            phRt.anchorMax = Vector2.one;
            phRt.offsetMin = new Vector2(8, 2);
            phRt.offsetMax = new Vector2(-8, -2);
            var phTxt = phGo.AddComponent<Text>();
            phTxt.text = placeholder;
            phTxt.fontSize = fontSize;
            phTxt.color = COLOR_TEXT_SECONDARY;
            phTxt.fontStyle = FontStyle.Italic;
            phTxt.font = textComp.font;

            var input = go.AddComponent<InputField>();
            input.textComponent = textComp;
            input.placeholder = phTxt;

            return input;
        }

        // ====================================================================
        // Layout Helpers
        // ====================================================================

        /// <summary>Add a VerticalLayoutGroup to an existing RectTransform.</summary>
        public static VerticalLayoutGroup AddVerticalLayout(RectTransform rt,
            float spacing = 4f, RectOffset padding = null, bool childForceExpand = false)
        {
            var vlg = rt.gameObject.AddComponent<VerticalLayoutGroup>();
            vlg.spacing = spacing;
            vlg.padding = padding ?? new RectOffset(8, 8, 8, 8);
            vlg.childForceExpandWidth = true;
            vlg.childForceExpandHeight = childForceExpand;
            vlg.childControlWidth = true;
            vlg.childControlHeight = true;
            return vlg;
        }

        /// <summary>Add a HorizontalLayoutGroup to an existing RectTransform.</summary>
        public static HorizontalLayoutGroup AddHorizontalLayout(RectTransform rt,
            float spacing = 4f, RectOffset padding = null, bool childForceExpand = false)
        {
            var hlg = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            hlg.spacing = spacing;
            hlg.padding = padding ?? new RectOffset(4, 4, 4, 4);
            hlg.childForceExpandWidth = childForceExpand;
            hlg.childForceExpandHeight = true;
            hlg.childControlWidth = true;
            hlg.childControlHeight = true;
            return hlg;
        }

        /// <summary>Set a preferred height on a layout element.</summary>
        public static LayoutElement SetPreferredHeight(GameObject go, float height)
        {
            var le = go.GetComponent<LayoutElement>();
            if (le == null) le = go.AddComponent<LayoutElement>();
            le.preferredHeight = height;
            return le;
        }

        /// <summary>Set a preferred size on a layout element.</summary>
        public static LayoutElement SetPreferredSize(GameObject go, float width, float height)
        {
            var le = go.GetComponent<LayoutElement>();
            if (le == null) le = go.AddComponent<LayoutElement>();
            le.preferredWidth = width;
            le.preferredHeight = height;
            return le;
        }

        // ====================================================================
        // Composite Helpers
        // ====================================================================

        /// <summary>Create a header row: title + close hint.</summary>
        public static (RectTransform row, Text title, Text hint) CreateHeaderRow(
            Transform parent, string titleText, string hintText, float height = 40f)
        {
            var rowRt = CreatePanel(parent, "Header", COLOR_BG_HEADER,
                Vector2.zero, Vector2.one);
            SetPreferredHeight(rowRt.gameObject, height);

            var title = CreateText(rowRt, "Title", titleText, 20, COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            var titleRt = title.rectTransform;
            titleRt.anchorMin = new Vector2(0, 0);
            titleRt.anchorMax = new Vector2(0.7f, 1);
            titleRt.offsetMin = new Vector2(12, 0);
            titleRt.offsetMax = Vector2.zero;
            title.alignment = TextAnchor.MiddleLeft;

            var hint = CreateText(rowRt, "Hint", hintText, 13, COLOR_TEXT_SECONDARY, TextAnchor.MiddleRight);
            var hintRt = hint.rectTransform;
            hintRt.anchorMin = new Vector2(0.7f, 0);
            hintRt.anchorMax = new Vector2(1, 1);
            hintRt.offsetMin = Vector2.zero;
            hintRt.offsetMax = new Vector2(-12, 0);

            return (rowRt, title, hint);
        }

        /// <summary>Create a labeled row: "Label:  Value".</summary>
        public static (Text label, Text value) CreateLabeledRow(
            Transform parent, string labelText, string valueText, int fontSize = 15)
        {
            var rowGo = new GameObject("Row_" + labelText.Replace(" ", ""));
            rowGo.transform.SetParent(parent, false);
            var rowRt = rowGo.AddComponent<RectTransform>();
            StretchFill(rowRt);
            SetPreferredHeight(rowGo, fontSize + 8);

            var label = CreateText(rowGo.transform, "Label", labelText, fontSize,
                COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            var labelRt = label.rectTransform;
            labelRt.anchorMin = new Vector2(0, 0);
            labelRt.anchorMax = new Vector2(0.45f, 1);
            labelRt.offsetMin = Vector2.zero;
            labelRt.offsetMax = Vector2.zero;

            var value = CreateText(rowGo.transform, "Value", valueText, fontSize,
                COLOR_TEXT_PRIMARY, TextAnchor.MiddleRight);
            var valueRt = value.rectTransform;
            valueRt.anchorMin = new Vector2(0.45f, 0);
            valueRt.anchorMax = new Vector2(1, 1);
            valueRt.offsetMin = Vector2.zero;
            valueRt.offsetMax = Vector2.zero;

            return (label, value);
        }

        /// <summary>Create a divider line.</summary>
        public static Image CreateDivider(Transform parent, float height = 2f)
        {
            var img = CreateImage(parent, "Divider", COLOR_BORDER);
            SetPreferredHeight(img.gameObject, height);
            var rt = img.rectTransform;
            StretchFill(rt);
            return img;
        }

        /// <summary>Create a tab bar with multiple tabs.</summary>
        public static (RectTransform bar, Button[] tabs) CreateTabBar(
            Transform parent, string[] tabNames, float height = 36f)
        {
            var barGo = new GameObject("TabBar");
            barGo.transform.SetParent(parent, false);
            var barRt = barGo.AddComponent<RectTransform>();
            StretchFill(barRt);
            SetPreferredHeight(barGo, height);

            AddHorizontalLayout(barRt, 2f, new RectOffset(4, 4, 2, 2), true);

            var tabs = new Button[tabNames.Length];
            for (int i = 0; i < tabNames.Length; i++)
            {
                tabs[i] = CreateButton(barRt, "Tab_" + tabNames[i], tabNames[i],
                    COLOR_BG_BUTTON, COLOR_TEXT_PRIMARY, 14);
            }

            return (barRt, tabs);
        }
    }
}
