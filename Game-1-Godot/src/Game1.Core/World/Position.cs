namespace Game1.Core.World;

/// <summary>
/// Port of data/models/world.py Position — 3D position, z defaults to 0.
/// distance_to is full 3D Euclidean (planar sim keeps z=0 today; True 3D
/// (P11) inherits the correct metric for free).
/// </summary>
public struct Position
{
    public double X;
    public double Y;
    public double Z;

    public Position(double x, double y, double z = 0.0)
    {
        X = x; Y = y; Z = z;
    }

    public double DistanceTo(Position other)
    {
        var dx = X - other.X;
        var dy = Y - other.Y;
        var dz = Z - other.Z;
        return Math.Sqrt(dx * dx + dy * dy + dz * dz);
    }

    /// <summary>world.py snap_to_grid — floor() so -0.5 snaps to -1.</summary>
    public Position SnapToGrid() =>
        new(Math.Floor(X), Math.Floor(Y), Math.Floor(Z));

    public override string ToString() => $"({X}, {Y}, {Z})";
}
