using System.Runtime.InteropServices;
using XBrutal.ImGuiStandalone;

internal static class GuardChecks
{
    internal static void Reject<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new Exception("Expected rejection: " + typeof(T).Name);
    }

    internal static void Run()
    {
        Reject<PlatformNotSupportedException>(() => NativeAssets.SelectRid("osx", Architecture.X64));
        Reject<PlatformNotSupportedException>(() => NativeAssets.SelectRid("win", Architecture.Arm64));
        Reject<PlatformNotSupportedException>(() => NativeAssets.SelectRid("linux", Architecture.Arm64));
        Reject<PlatformNotSupportedException>(() => NativeAssets.SelectRid("unknown", Architecture.X64));
        Reject<InvalidOperationException>(() => StandaloneHost.CreateNativeFieldAccessors());
        Reject<ArgumentNullException>(() => StandaloneHost.Capture(null!));
        Reject<ArgumentOutOfRangeException>(() => StandaloneHost.Capture(() => { }, 0, 1));
        if (OperatingSystem.IsMacOS())
            Task.Run(() => Reject<InvalidOperationException>(() => StandaloneHost.Capture(() => { }))).GetAwaiter().GetResult();
        Console.WriteLine("PASS platform/argument/main-thread guards");
    }
}
