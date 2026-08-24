namespace Game1.Godot;

/// <summary>
/// Shared UI state. While any popup screen (inventory, map) is open, world
/// input — attacks, gather, craft, camera orbit/zoom — is suppressed.
/// </summary>
public static class UiHub
{
    public static int OpenScreens;
    public static bool ScreenOpen => OpenScreens > 0;
}
