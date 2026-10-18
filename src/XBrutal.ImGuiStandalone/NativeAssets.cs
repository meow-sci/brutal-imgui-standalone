using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Brutal.GlfwApi;
using Brutal.ImGuiApi;

namespace XBrutal.ImGuiStandalone;

internal static class NativeAssets
{
    private static readonly object Gate = new();
    private static nint s_imgui;
    private static nint s_glfw;
    internal static string ImGuiPath { get; private set; } = "";
    internal static string GlfwPath { get; private set; } = "";

    internal static string SelectRid() => SelectRid(OperatingSystem.IsWindows() ? "win" :
        OperatingSystem.IsLinux() ? "linux" : OperatingSystem.IsMacOS() ? "osx" : "unknown", RuntimeInformation.ProcessArchitecture);

    internal static string SelectRid(string os, Architecture architecture) => (os, architecture) switch
    {
        ("win", Architecture.X64) => "win-x64",
        ("linux", Architecture.X64) => "linux-x64",
        ("osx", Architecture.Arm64) => "osx-arm64",
        _ => throw new PlatformNotSupportedException($"Unsupported OS/process architecture {os}/{architecture}. XBrutal.ImGuiStandalone supports only win-x64, linux-x64 and osx-arm64; architecture means the process, not the machine.")
    };

    internal static (string ImGui, string ImGuiHash, string Glfw, string GlfwHash) Pins(string rid) => rid switch
    {
        "osx-arm64" => ("libimgui.dylib", "048ce8fd55b30b86f9ea3c3c4531cf8be78763002a06d0a3e8d784c4e41f9c5a", "libglfw.dylib", "c2057028e3f9310b23c1b9a8da2e57839aa98066d1d6fa928d8cdfa7b4813258"),
        "linux-x64" => ("libimgui.so", "ba20d709f69b23928a1b5f7c65f47a8c5cab95e86644e3b86dd667dee16029ab", "libglfw.so", "abd1e55084037754c954e3a35db13744e939bdda7c42b235ba6466eb89bc88de"),
        "win-x64" => ("imgui.dll", "a57ce9a768466f99c2d3e66dd45ce0b6a5a03547aafa49217e92a9a5c2a3da08", "glfw3.dll", "a107a8e8378527897d5e99f3a53d01a7289ef5fda564952fbec2769386eccd58"),
        _ => throw new PlatformNotSupportedException($"Unsupported package RID '{rid}'.")
    };

    internal static string HashFile(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    internal static string ResolveAsset(string baseDirectory, string rid, string filename, string hash)
    {
        string flat = Path.GetFullPath(Path.Combine(baseDirectory, filename));
        string portable = Path.GetFullPath(Path.Combine(baseDirectory, "runtimes", rid, "native", filename));
        if (File.Exists(flat) && File.Exists(portable))
            throw new InvalidOperationException($"Ambiguous native assets for {rid}/{filename}. Remove stale deployment files; keep only the portable build or RID-publish layout.");
        string selected = File.Exists(flat) ? flat : portable;
        if (!File.Exists(selected))
            throw new FileNotFoundException($"Missing packaged native asset {rid}/{filename}. Restore/publish XBrutal.ImGuiStandalone runtime assets; no system/game-library fallback is permitted. Expected '{flat}' or '{portable}'.", selected);
        ValidateHash(selected, hash);
        return selected;
    }

    internal static void ValidateHash(string path, string expectedHash)
    {
        if (HashFile(path) != expectedHash)
            throw new InvalidOperationException($"Packaged asset SHA-256 mismatch: '{path}'. Restore the exact immutable package; do not substitute game or system libraries.");
    }

    internal static string FontPath()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "fonts", "JetBrainsMono-Regular.ttf");
        if (!File.Exists(path)) throw new FileNotFoundException("Bundled JetBrains Mono font is missing. Preserve the package's automatic contentFiles output when publishing.", path);
        ValidateHash(path, "a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f");
        return path;
    }

    internal static nint EnsureLoaded()
    {
        string rid = SelectRid();
        ManagedCompatibility.Validate(); // Must precede any assertion-capable BRUTAL ABI call.
        var pins = Pins(rid);
        string imguiPath = ResolveAsset(AppContext.BaseDirectory, rid, pins.ImGui, pins.ImGuiHash);
        string glfwPath = ResolveAsset(AppContext.BaseDirectory, rid, pins.Glfw, pins.GlfwHash);
        lock (Gate)
        {
            if (s_imgui != 0)
            {
                if (ImGuiPath != imguiPath || GlfwPath != glfwPath)
                    throw new InvalidOperationException("Native deployment changed after process-lifetime initialization.");
                return s_imgui;
            }
            nint imgui = NativeLibrary.Load(imguiPath);
            // Once loaded, retain handles even on initialization failure: external cached
            // P/Invoke/explicit-load addresses must never point at an unloaded image.
            RequireImage(imgui, "GetVersion", imguiPath);
            ManagedCompatibility.ValidateImports(imgui); // Still precedes the resolver and every BRUTAL P/Invoke.
            try
            {
                NativeLibrary.SetDllImportResolver(typeof(ImGui).Assembly, (name, _, _) => name == "imgui" ? imgui : 0);
            }
            catch (InvalidOperationException error)
            {
                throw new InvalidOperationException("XBrutal.ImGuiStandalone requires exclusive resolver ownership of Brutal.ImGui before its first P/Invoke. Do not initialize another ImGui backend/resolver in this process.", error);
            }
            RequireExplicitLoad("imgui", typeof(ImGui).Assembly, null, imgui, "GetVersion", imguiPath);
            nint glfw = NativeLibrary.Load(glfwPath);
            RequireImage(glfw, "glfwInit", glfwPath);
            // Brutal.Glfw owns its resolver. Verify its exact explicit-load route without
            // installing a competing resolver or touching GLFW initialization here.
            RequireExplicitLoad(OperatingSystem.IsWindows() ? "glfw3" : "glfw", typeof(Glfw).Assembly,
                DllImportSearchPath.AssemblyDirectory, glfw, "glfwInit", glfwPath);
            using var identity = new NativeFieldAccessors(imgui);
            s_glfw = glfw;
            ImGuiPath = imguiPath;
            GlfwPath = glfwPath;
            s_imgui = imgui;
            return s_imgui;
        }
    }

    private static void RequireExplicitLoad(string name, Assembly assembly, DllImportSearchPath? searchPath, nint expected, string symbol, string path)
    {
        nint handle = NativeLibrary.Load(name, assembly, searchPath);
        RequireImage(handle, symbol, path);
        if (NativeLibrary.GetExport(handle, symbol) != NativeLibrary.GetExport(expected, symbol))
            throw new InvalidOperationException($"External native load '{name}' selected a competing image. Use ordinary package build/publish probing and remove preloaded libraries.");
    }

    internal static nint GlfwHandle => s_glfw != 0 ? s_glfw : throw new InvalidOperationException("Host has not prepared GLFW.");

    internal static void RequireImage(nint handle, string symbol, string expectedPath)
    {
        string actual = ImagePath(handle, symbol);
        if (!string.Equals(Path.GetFullPath(actual), Path.GetFullPath(expectedPath), OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal))
            throw new InvalidOperationException($"Native loader selected '{actual}' instead of the validated packaged image '{expectedPath}'. Preloaded/system/game images are unsupported.");
    }

    internal static string ImagePath(nint handle, string symbol)
    {
        if (OperatingSystem.IsWindows())
        {
            var path = new char[32768];
            uint length = GetModuleFileNameW(handle, path, (uint)path.Length);
            if (length == 0 || length >= path.Length) throw new InvalidOperationException("Cannot identify loaded native module.");
            return new string(path, 0, (int)length);
        }
        nint address = NativeLibrary.GetExport(handle, symbol);
        int result = OperatingSystem.IsMacOS() ? MacDlAddr(address, out DlInfo info) : LinuxDlAddr(address, out info);
        if (result == 0 || info.FileName == 0) throw new InvalidOperationException("Cannot identify loaded native image.");
        return Marshal.PtrToStringUTF8(info.FileName)!;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct DlInfo { internal nint FileName, BaseAddress, SymbolName, SymbolAddress; }
    [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "dladdr")]
    private static extern int MacDlAddr(nint address, out DlInfo info);
    [DllImport("libdl.so.2", EntryPoint = "dladdr")]
    private static extern int LinuxDlAddr(nint address, out DlInfo info);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint GetModuleFileNameW(nint module, [Out] char[] path, uint size);
}
