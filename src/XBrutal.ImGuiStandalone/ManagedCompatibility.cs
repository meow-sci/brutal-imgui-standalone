using System.Reflection;
using System.Runtime.InteropServices;
using Brutal.ImGuiApi;
using Brutal.Numerics;

namespace XBrutal.ImGuiStandalone;

internal static class ManagedCompatibility
{
    // The game re-signs code-identical Brutal assemblies, so identity (hash/MVID) is not pinned. The ABI is:
    // the native imports must resolve in our pinned image and the value types we touch must keep their layout.
    private static readonly (Type Type, int Size, string Offsets)[] Layouts =
    [
        (typeof(Brutal.Bool8), 1, ""),
        (typeof(float2), 8, ""),
        (typeof(float4), 16, ""),
        (typeof(ImGuiIO), 3064, "ConfigFlags=0 BackendFlags=4 DisplaySize=8 DisplayFramebufferScale=16 DeltaTime=24 IniFilename=32 LogFilename=40 Fonts=56 FontDefault=64 ConfigMacOSXBehaviors=92"),
        (typeof(ImGuiStyle), 1276, ""),
        (typeof(ImGuiPlatformIO), 328, "Platform_GetClipboardTextFn=0 Platform_SetClipboardTextFn=8"),
        (typeof(ImGuiViewport), 104, ""),
        (typeof(ImFontAtlas), 736, ""),
        (typeof(ImFont), 96, ""),
        (typeof(ImDrawVert), 20, "pos=0 uv=8 col=16"),
        (typeof(ImDrawCmd), 72, "ClipRect=0 VtxOffset=32 IdxOffset=36 ElemCount=40 UserCallback=48"),
        (typeof(ImDrawData), 72, "CmdLists=16 DisplayPos=32 FramebufferScale=48 Textures=64"),
        (typeof(ImDrawList), 224, "CmdBuffer=0 IdxBuffer=16 VtxBuffer=32"),
        (typeof(ImTextureData), 88, "Status=4 TexID=16 Format=24 Width=28 Height=32 Pixels=40 UnusedFrames=80"),
    ];

    // Runs before any native load or BRUTAL call.
    internal static void Validate()
    {
        foreach (var assembly in new[] { typeof(ImGui).Assembly, typeof(Brutal.Bool8).Assembly, typeof(float2).Assembly })
            if (assembly.IsDynamic || string.IsNullOrEmpty(assembly.Location) || !File.Exists(assembly.Location))
                throw Incompatible(assembly.GetName().Name!, "in-memory, dynamic or single-file assembly");
        foreach (var (type, size, offsets) in Layouts)
        {
            int actual = Marshal.SizeOf(type);
            if (actual != size) throw Incompatible(type.FullName!, $"size {actual}, expected {size}");
            foreach (string entry in offsets.Split(' ', StringSplitOptions.RemoveEmptyEntries))
            {
                string[] parts = entry.Split('=');
                int offset = (int)Marshal.OffsetOf(type, parts[0]);
                if (offset != int.Parse(parts[1])) throw Incompatible($"{type.FullName}.{parts[0]}", $"offset {offset}, expected {parts[1]}");
            }
        }
    }

    // Needs the loaded native image; must still precede the resolver install and the first P/Invoke.
    internal static void ValidateImports(nint imgui)
    {
        foreach (var type in typeof(ImGui).Assembly.GetTypes())
            foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly))
            {
                if (method.GetCustomAttribute<DllImportAttribute>() is not { Value: "imgui" } import) continue;
                string entry = string.IsNullOrEmpty(import.EntryPoint) ? method.Name : import.EntryPoint;
                if (!NativeLibrary.TryGetExport(imgui, entry, out _))
                    throw Incompatible($"{type.FullName}.{method.Name}", $"native import '{entry}' is not exported by the packaged ImGui image");
            }
    }

    private static NotSupportedException Incompatible(string name, string reason) =>
        new($"Incompatible loaded managed ABI input '{name}': {reason}. Supply BRUTAL assemblies whose imports and layouts match COMPATIBILITY.md; in-memory, single-file and ABI-changed builds are unsupported.");
}
