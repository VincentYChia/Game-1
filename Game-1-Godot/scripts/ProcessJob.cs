using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;

namespace Game1.Godot;

/// <summary>
/// Ties spawned child processes (the Python sidecars) to the lifetime of THIS game
/// process on Windows, via a Job Object created with KILL_ON_JOB_CLOSE.
///
/// Windows does NOT auto-reap grandchildren: if the game process dies without first
/// killing a child it spawned, that child is orphaned and keeps running. For a
/// heavyweight sidecar (TensorFlow / LightGBM / pygame / the LLM stack) that means a
/// process left spinning in the background after the game window closes — burning CPU
/// and battery. By assigning every child to a job the game holds open for its whole
/// life, the OS force-kills the child the instant the game exits for ANY reason:
/// clean quit, the editor "Stop" button, Ctrl+C, or a crash (none of which run C#
/// cleanup). No-op on non-Windows platforms — graceful <c>Shutdown()</c> is the
/// fallback there.
/// </summary>
internal static class ProcessJob
{
    private static readonly object _gate = new();
    private static IntPtr _job = IntPtr.Zero;
    private static bool _tried;
    private static bool _ok;

    /// <summary>Enrol an already-started process so it can never outlive this one.</summary>
    public static void Register(Process proc)
    {
        if (!OperatingSystem.IsWindows()) return;   // POSIX relies on Shutdown()
        try
        {
            lock (_gate)
            {
                if (!_tried) { _tried = true; _ok = TryCreateJob(); }
                if (_ok) AssignProcessToJobObject(_job, proc.Handle);
            }
        }
        catch { /* best-effort — never break spawning over reaper setup */ }
    }

    [SupportedOSPlatform("windows")]
    private static bool TryCreateJob()
    {
        _job = CreateJobObject(IntPtr.Zero, null);
        if (_job == IntPtr.Zero) return false;

        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        int len = Marshal.SizeOf<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>();
        IntPtr ptr = Marshal.AllocHGlobal(len);
        try
        {
            Marshal.StructureToPtr(info, ptr, false);
            // The job handle is deliberately never closed: keeping it open for the
            // whole process lifetime is exactly what makes KILL_ON_JOB_CLOSE fire
            // when this process terminates.
            return SetInformationJobObject(_job, JobObjectExtendedLimitInformation, ptr, (uint)len);
        }
        finally { Marshal.FreeHGlobal(ptr); }
    }

    private const int JobObjectExtendedLimitInformation = 9;
    private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(
        IntPtr hJob, int infoClass, IntPtr lpInfo, uint cbInfo);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }
}
