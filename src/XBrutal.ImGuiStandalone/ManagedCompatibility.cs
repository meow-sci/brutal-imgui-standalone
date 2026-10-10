using System.Reflection;
using System.Security.Cryptography;
using Brutal.ImGuiApi;
using Brutal.Numerics;

namespace XBrutal.ImGuiStandalone;

internal static class ManagedCompatibility
{
    // Hashes qualify a specific external ABI, not just its assembly or ImGui version.
    internal static void Validate()
    {
        ValidateAssembly(typeof(ImGui).Assembly, "b76777a4ef3399d6353b9dba1982e3afb84b5da2aa2500da1c062db0bfad827c", new("be72af36-f552-460e-ab1c-cc0018ebd574"));
        ValidateAssembly(typeof(Brutal.Bool8).Assembly, "4cbae1473d6a3759345f1eec8e62e6c7da1e19f8d10db8d13c005203ec590de4", new("d0a4e4ad-480c-4cc8-a9bf-687b26cb8963"));
        ValidateAssembly(typeof(float2).Assembly, "a217a6098116a1895e965b3a1d4fdee931e59a7a55f326c7d710b0d7eeccd17a", new("e4190ee6-8291-49aa-9721-88111e32f2ba"));
    }

    internal static void ValidateAssembly(Assembly assembly, string expectedHash, Guid expectedMvid)
    {
        string location = assembly.Location;
        if (assembly.IsDynamic || string.IsNullOrEmpty(location) || !File.Exists(location) ||
            assembly.ManifestModule.ModuleVersionId != expectedMvid ||
            NativeAssets.HashFile(location) != expectedHash)
            throw new NotSupportedException($"Incompatible loaded managed ABI input '{assembly.GetName().Name}'. Supply the audited BRUTAL assemblies documented in COMPATIBILITY.md. Version equality is insufficient; in-memory, single-file and unqualified builds are unsupported.");
    }
}
