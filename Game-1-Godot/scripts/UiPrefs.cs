namespace Game1.Godot;

/// <summary>Session-wide UI preferences. Tooltips are ON everywhere by default;
/// ADVANCED tooltips (full stats / tags / requirements) are an opt-in toggle.</summary>
public static class UiPrefs
{
    /// <summary>Basic tooltips always show; advanced adds the full breakdown.</summary>
    public static bool AdvancedTooltips;
}
