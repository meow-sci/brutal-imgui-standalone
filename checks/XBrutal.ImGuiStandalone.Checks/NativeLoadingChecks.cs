using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Brutal.GlfwApi;
using Brutal.ImGuiApi;
using Brutal.Numerics;
using XBrutal.ImGuiStandalone;

internal static unsafe class NativeLoadingChecks
{
    private static readonly string[] Names = ["GetWindowFramebufferScale", "GetWindowPos", "GetWindowSize"];
    private static void Require(bool value, string message)
    {
        if (!value) throw new Exception(message);
    }
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate float2 ViewportCallback(ImGuiViewportPtr viewport);

    private sealed class Target(nint expected, float x, float y)
    {
        internal nint Seen;
        internal int Calls;
        internal float2 Invoke(ImGuiViewportPtr viewport)
        {
            Seen = (nint)viewport.Ptr;
            ++Calls;
            // No exception may cross reverse P/Invoke; assertions follow the native call.
            return Seen == expected ? new(x, y) : new(float.NaN, float.NaN);
        }
    }

    internal static void Run()
    {
        typeof(StandaloneHost).Module.GetPEKind(out var kind, out var machine);
        Require((kind & System.Reflection.PortableExecutableKinds.ILOnly) != 0 && (kind & System.Reflection.PortableExecutableKinds.Required32Bit) == 0 && machine == System.Reflection.ImageFileMachine.I386, "portable AnyCPU library PE contract");
        nint image = StandaloneHost.PrepareNativeLibraryForChecks();
        Require(ImGui.GetVersion().ToString() == "1.92.2", "ordinary BRUTAL P/Invoke");
        int frames = 0;
        StandaloneHost.Capture(() =>
        {
            if (++frames == 1)
            {
                CheckBridges(image, (nint)ImGui.GetMainViewport().Ptr);
                CheckHelpers();
                GuardChecks.Reject<InvalidOperationException>(() => StandaloneHost.Capture(() => { }));
                CheckLoadedGlfw();
            }
            ImGui.SetNextWindowPos(new float2(1, 1));
            ImGui.SetNextWindowSize(new float2(180, 90));
            ImGui.Begin("Production manual ABI"u8);
            try
            {
                fixed (byte* text = "literal%%\0"u8) ImGui.PInvoke.Text(text);
                ImGui.Button("Direct BRUTAL"u8);
            }
            finally { ImGui.End(); }
        }, 200, 120);
        Console.WriteLine(JsonSerializer.Serialize(new { status = "passed", gate = "package-loading", rid = NativeAssets.SelectRid(), imgui = NativeAssets.ImGuiPath, imguiHash = NativeAssets.HashFile(NativeAssets.ImGuiPath), glfw = NativeAssets.GlfwPath, glfwHash = NativeAssets.HashFile(NativeAssets.GlfwPath), bridges = 3, helperIdentity = NativeFieldAccessors.ExpectedIdentity }));
    }

    private static void CheckBridges(nint image, nint viewport)
    {
        foreach (string name in Names)
        {
            nint* slot = (nint*)NativeLibrary.GetExport(image, "Platform_" + name + "_ManagedFunctionPointer");
            var getter = (delegate* unmanaged[Cdecl]<nint>)NativeLibrary.GetExport(image, "Get_" + name + "_InteropPointer");
            nint trampoline = getter();
            Require(*slot == 0 && trampoline != 0, "inactive bridge/getter");
            var first = new Target(viewport, -17.25f, 98.5f);
            var second = new Target(viewport, 35.125f, -0.75f);
            ViewportCallback a = first.Invoke, b = second.Invoke;
            GCHandle aRoot = GCHandle.Alloc(a), bRoot = GCHandle.Alloc(b);
            try
            {
                nint pointer = Marshal.GetFunctionPointerForDelegate(a);
                Require(Interop.CreateTrampoline((delegate* unmanaged[Cdecl]<ImGuiViewportPtr, float2>)pointer, name) == trampoline && *slot == pointer, "explicit Interop loader must write THIS image's slot and return THIS getter");
                foreach (string neighbor in Names.Where(n => n != name))
                    Require(*(nint*)NativeLibrary.GetExport(image, "Platform_" + neighbor + "_ManagedFunctionPointer") == 0, "neighbor slot corruption");
                GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
                var invoke = (delegate* unmanaged[Cdecl]<ImGuiViewportPtr, float2>)trampoline;
                float2 value = invoke(new ImGuiViewportPtr((ImGuiViewport*)viewport));
                Require(value == new float2(-17.25f, 98.5f) && first.Seen == viewport && first.Calls == 1, "rooted first bridge callback identity/value");
                pointer = Marshal.GetFunctionPointerForDelegate(b);
                Require(Interop.CreateTrampoline((delegate* unmanaged[Cdecl]<ImGuiViewportPtr, float2>)pointer, name) == trampoline && *slot == pointer, "bridge replacement");
                value = invoke(new ImGuiViewportPtr((ImGuiViewport*)viewport));
                Require(value == new float2(35.125f, -0.75f) && second.Calls == 1 && first.Calls == 1, "replacement value/identity");
                *slot = 0;
                Require(getter() == trampoline && *slot == 0, "stable getter after unregister");
            }
            finally { *slot = 0; aRoot.Free(); bRoot.Free(); GC.KeepAlive(a); GC.KeepAlive(b); }
        }
    }

    private static void CheckHelpers()
    {
        using var accessors = StandaloneHost.CreateNativeFieldAccessors();
        Require(accessors.StyleCount == (int)ImGuiStyleVar.COUNT && accessors.StyleAt(0).Count > 0, "style metadata");
        Require(accessors.EmptyStringByte == 0, "manual empty-string native helper");
        GuardChecks.Reject<ArgumentOutOfRangeException>(() => accessors.StyleAt(accessors.StyleCount));
        using var scope = accessors.CreateBorrowScope();
        var context = scope.BorrowRecord(NativeRecordKind.ImGuiContext, (nint)ImGui.GetCurrentContext().Ptr);
        Require(context.Get(NativePackedField.ImGuiContext_ActiveIdMouseButton) >= -1, "live packed read");
        var style = scope.BorrowRecord(NativeRecordKind.ImGuiStyleVarInfo, (nint)ImGui.Internal.GetStyleVarInfo(ImGuiStyleVar.Alpha).Ptr);
        Require(style.Get(NativePackedField.ImGuiStyleVarInfo_Count) == accessors.StyleAt(0).Count, "native style read avoids CLR stride defect");
        GuardChecks.Reject<NotSupportedException>(() => style.Set(NativePackedField.ImGuiStyleVarInfo_Count, 1));
        // This is a real live shared draw-list record, not a fixture or arbitrary memory.
        var shared = scope.BorrowOpaque(NativeOpaqueShape.DrawListSharedData, (nint)(ImDrawListSharedData*)ImGui.GetDrawListSharedData());
        Require(shared.SharedData().FontSize > 0, "live helper snapshot");
        Task.Run(() => GuardChecks.Reject<InvalidOperationException>(() => _ = accessors.StyleCount)).GetAwaiter().GetResult();
        scope.Invalidate();
        GuardChecks.Reject<InvalidOperationException>(() => context.Get(NativePackedField.ImGuiContext_ActiveIdMouseButton));
        accessors.Dispose();
        GuardChecks.Reject<ObjectDisposedException>(() => _ = accessors.StyleCount);
        GuardChecks.Reject<ObjectDisposedException>(() => scope.BorrowRecord(NativeRecordKind.ImGuiContext, (nint)ImGui.GetCurrentContext().Ptr));
    }

    internal static void CheckLoadedGlfw()
    {
        // GLFW's own resolver has run after Glfw.Init; enumerate actual images rather
        // than assuming a handle loaded by this test proves its resolver path.
        Require(Images("glfw") is [var image] && Path.GetFullPath(image) == NativeAssets.GlfwPath, "actual GLFW own-loader image attribution");
        NativeAssets.ValidateHash(NativeAssets.GlfwPath, NativeAssets.Pins(NativeAssets.SelectRid()).GlfwHash);
    }

    internal static void ExpectStartupRejection(string diagnostic, bool beforeNative = false)
    {
        try { StandaloneHost.Capture(() => throw new Exception("callback must not run")); }
        catch (Exception error) when (error.Message.Contains(diagnostic, StringComparison.OrdinalIgnoreCase))
        {
            if (beforeNative)
                Require(Images("imgui").Length == 0 && Images("glfw").Length == 0, "rejection must precede native loading/ABI calls");
            Console.WriteLine("PASS startup rejection: " + error.Message);
            return;
        }
        throw new Exception("Expected startup rejection: " + diagnostic);
    }

    private static string[] Images(string token)
    {
        if (OperatingSystem.IsMacOS())
            return Enumerable.Range(0, (int)ImageCount()).Select(i => Marshal.PtrToStringUTF8(ImageName((uint)i))!).Where(p => IsNativeImage(Path.GetFileName(p), token)).ToArray();
        using var process = Process.GetCurrentProcess();
        return process.Modules.Cast<ProcessModule>().Select(m => m.FileName).Where(p => IsNativeImage(Path.GetFileName(p), token)).Distinct().ToArray();
    }
    private static bool IsNativeImage(string name, string token) => token == "imgui"
        ? name == "imgui.dll" || name.StartsWith("libimgui", StringComparison.Ordinal)
        : name == "glfw3.dll" || name.StartsWith("libglfw", StringComparison.Ordinal);

    [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "_dyld_image_count")]
    private static extern uint ImageCount();
    [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "_dyld_get_image_name")]
    private static extern nint ImageName(uint index);
}
