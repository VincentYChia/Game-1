namespace Game1.Core;

/// <summary>Python arithmetic semantics helpers shared by ports.</summary>
public static class PyMath
{
    /// <summary>Python's % for doubles: result has the sign of the divisor.
    /// C#'s % takes the dividend's sign, which breaks angle-wrapping like
    /// `(diff + 180) % 360 - 180` for negative diffs.</summary>
    public static double Mod(double a, double m)
    {
        var r = a % m;
        return r != 0 && (r < 0) != (m < 0) ? r + m : r;
    }

    public static double Radians(double degrees) => degrees * Math.PI / 180.0;

    public static double Degrees(double radians) => radians * 180.0 / Math.PI;
}
