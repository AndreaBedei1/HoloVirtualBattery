# Patched HoloOcean 2.3.0 backend: reproducible build

This document records how the separate HoloOcean 2.3.0 Ocean builds used by the
verified-backend campaign were produced, and how to reproduce them:

```text
checkout source -> apply patch -> build -> assemble package -> run audit
```

The installed Ocean package (`%LOCALAPPDATA%/holoocean/2.3.0/worlds/Ocean`) is the
**ORIGINAL / BEFORE** reference. It is only read; its executable, cooked content and
Python environment are never modified. Two separate packages are produced:

| Variant | Source | Purpose |
| --- | --- | --- |
| `rebuilt-before` | tag `v2.3.0`, unmodified | control: proves that the rebuild reproduces the official binary |
| `patched-after` | tag `v2.3.0` + `patches/holoocean-2.3-drag-units.patch` | corrected drag backend |

Results and hashes of the run recorded on 2026-10-07 are in
[`sources/verified_backend/build_provenance`](../sources/verified_backend/build_provenance) and in the
[verified backend report](verified_backend_report.md).

## Why a code-only rebuild

The Ocean worlds (`engine/Content/Worlds`) are not in the public HoloOcean
repository (`.gitignore`, and the docker README cites licensing). A full Ocean
cook is therefore impossible outside the HoloOcean team. The patch changes one
function body and no reflected type, so the **official cooked containers are reused
unchanged** (NTFS hard links) next to a rebuilt `Holodeck.exe`. Whether the rebuilt
executable reproduces the official one is not assumed: the `rebuilt-before` control
must reproduce the official binary's audit numbers before the `patched-after`
results are interpreted.

## Identity of the official binary (from its PDB and strings)

The official package ships `Holodeck.pdb`. Its paths and the executable strings show:

| Item | Official 2.3.0 Ocean binary |
| --- | --- |
| Engine | Unreal Engine 5.3.2 Launcher build (`++UE5+Release-5.3-CL-29314046`, `C:\Program Files\Epic Games\UE_5.3`) |
| Project source | `C:\Users\frost_server_windows\Builds\Develop\holoocean\engine` (a develop checkout; exact commit not embedded) |
| Compiler/linker | MSVC 14.44.35207 (VS 2022 Community) |
| Windows SDK | 10.0.22621.0 |
| Configuration | Development (`DefaultGame.ini`, CI script `ue4 package Development`) |
| SHA256 | `8c206c9cc05c640fb2efea6bd43bda33c585536ab16a931c55780855e7602253` |

## Toolchain used for the rebuild

| Component | Version | Notes |
| --- | --- | --- |
| Unreal Engine | 5.3.2, GitHub tag `5.3.2-release`, commit `072300df18a94f18077ca20a14224b5d99fee872` | Requires a GitHub account linked to Epic Games. Same release as the official Launcher build; `Build.version` has `Changelist 0` (source build). |
| Engine dependencies | `GitDependencies.exe`, Win64 only | Excluded folders listed below; no prerequisite installer, no engine registration |
| MSVC | 14.44.35207 (VS 2022 Build Tools 17.14) | Same toolset as the official binary |
| Windows SDK | 10.0.22621.0 | Same SDK as the official binary |
| .NET SDK (UnrealBuildTool) | 6.0.302 bundled with UE | Telemetry/first-run disabled by environment variables |
| HoloOcean | tag `v2.3.0`, commit `49e70552dfd97273b7dfbe755fbe65d7738b24b7` | Cloned with `core.autocrlf=false` |

UnrealBuildTool 5.3 prefers MSVC 14.34–14.36 and SDK 10.0.18362; the toolset and SDK
are therefore pinned explicitly to those of the official binary.

### Engine compatibility fixes (syntax only)

The official binary did not compile engine modules: Epic's precompiled Launcher
engine was built with MSVC 14.36, and only the Holodeck module was compiled with
14.44. A source build compiles every engine module with 14.44, which exposes two
known UE 5.3 incompatibilities with MSVC >= 14.38/14.40. The build script fixes
both in the local engine copy, each only after verifying the original file hash:

| File (UE 5.3.2) | Failure with MSVC 14.44 | Fix | SHA256 before → after |
| --- | --- | --- | --- |
| `Core/Public/Experimental/ConcurrentLinearAllocator.h` | MSVC now ships `sanitizer/asan_interface.h`, so `#elif __has_feature(address_sanitizer)` is evaluated; MSVC does not define `__has_feature`; C4668/C4067 are errors in engine modules | nest the test under `#elif defined(__has_feature)`; `IS_ASAN_ENABLED` stays `0` | `d97c1ccb…` → `92e5803d…` |
| `D3D12RHI/Private/D3D12CommandContext.h` | `FD3D12DynamicRHI::ResourceCast<RHIType, ObjectType>(…)`: the class is incomplete at that point and the stricter two-phase lookup parses `<` as a comparison (C3878/C2760) | standard `template` disambiguator: `FD3D12DynamicRHI::template ResourceCast<…>(…)`, same function | `8726657d…` → `6877d6ad…` |

Neither fix changes semantics. The `__has_feature` failure is reported on the
Unreal forums for UE 5.2–5.5 with MSVC 14.40+; Epic's guidance is to use an
older toolset (14.38), which would require modifying the installed Build Tools.
No Epic source file is redistributed by this repository: the script performs the
replacement locally. Whether the rebuilt engine behaves like Epic's binary is
tested by the `rebuilt-before` control campaign, not assumed.

### Excluded engine dependency folders

`Android IOS TVOS Linux LinuxArm64 Mac osx osx64 HoloLens Win32 VisionOS Lumin
Content Samples Documentation Maya_AnimationRiggingTools P4VUtils
UnrealEngineLauncher` — 20.5 GB instead of 60.9 GB. Engine/plugin `Content` is not
needed to compile the game target; the packaged game uses the official cooked
engine content.

## Procedure

Run from the repository root with the HoloOcean Python environment (any Python
>= 3.10 works for the build script itself). Each step is idempotent and verifies
its inputs; `--dry-run` prints the commands.

```powershell
$py = 'C:/Users/Andrea/miniconda3/envs/holoocean_joystick/python.exe'
# 1. Engine source (5.3.2-release) + Win64 dependencies + compatibility fix
& $py tools/build_patched_holoocean.py --steps engine
# 2. HoloOcean v2.3.0: build tree (src/before) and patched reference (src/after)
& $py tools/build_patched_holoocean.py --steps source
# 3. Build: pristine tree -> rebuilt-before, same tree + patch -> patched-after
& $py tools/build_patched_holoocean.py --steps build
# 4. Separate packages next to the official cooked containers, 5. manifests
& $py tools/build_patched_holoocean.py --steps assemble manifest
```

Defaults: work root `C:/HOB`, engine root `C:/UE532` (short paths: Windows long
paths are disabled on the audited machine), original package under
`%LOCALAPPDATA%/holoocean/2.3.0/worlds/Ocean`.

The underlying UnrealBuildTool command (for both variants, on the same tree) is:

```text
C:\UE532\Engine\Build\BatchFiles\Build.bat Holodeck Win64 Development
  -Project=C:\HOB\src\before\engine\Holodeck.uproject -WaitMutex -NoHotReload
  -DisableAdaptiveUnity -CompilerVersion=14.44.35207 -WindowsSDKVersion=10.0.22621.0
  -EnablePlugin=EOSShared -MaxParallelActions=10 -Log=C:\HOB\logs\ubt_<variant>.log
```

In PowerShell quote the `-CompilerVersion=` and `-WindowsSDKVersion=` arguments:
unquoted, PowerShell splits `14.44.35207` into two batch arguments.

### Plugin set of the official build

A cooked game mounts the plugins listed in its cooked plugin manifest and exits if a
listed plugin's module is not compiled into the executable. The official package
mounts 114 plugins (its own `HolodeckLog.txt`); the first rebuild contained 114
plugins as well but differed by one each way: the official set has `EOSShared`
(the official executable initializes EOS SDK 1.16.1), the source build has
`PlanarCut` instead (pulled in by the default-enabled `ChaosEditor` plugin of the
GitHub engine). The rebuilt game therefore stopped at startup with
`Plugin 'EOSShared' failed to load because module 'EOSShared' could not be found`.
`-EnablePlugin=EOSShared` (UBT target option) compiles the missing module without
touching the HoloOcean project files. `PlanarCut` is left compiled in: it is not
mounted by the cooked manifest, so it is never loaded. HoloOcean's `.uproject` did
not change between 2025-10-14 and 2026-04-09 (upstream history), so the difference
comes from the Launcher engine build, not from the project.

### One build tree

HoloOcean's targets keep legacy build settings (`DefaultBuildSettings` V1, the
`[Upgrade]` notes printed by UBT apply to the official build too), so UBT uses a
*unique* build environment: the whole engine is compiled into the project's
`Intermediate` directory (~20 GB, ~35 min with 10 parallel actions on an
i7-12700H/16 GB). The `after` variant is therefore built by applying the patch to
the same tree and rebuilding incrementally (only the Holodeck module and the link
change); the tree is restored to the pristine tag afterwards. `src/after` is a
separate read-only checkout with the patch applied, used by the audits; the build
script checks that its patched file is byte-identical to the one built.

### Package layout

```text
C:/HOB/packages/<variant>/Ocean/
  config.json, *.json, materials.csv          copied from the official package
  Windows/Holodeck.exe, Engine/**, Manifest_*  copied
  Windows/Holodeck/Binaries/Win64/Holodeck.exe|.pdb   rebuilt
  Windows/Holodeck/Binaries/Win64/*.dll, D3D12/*      copied
  Windows/Holodeck/Content/Paks/*              NTFS hard links to the official files
  holoenergy_build_manifest.json               provenance (commands, versions, hashes)
```

`Saved/` folders (logs and crash-reporter state of earlier runs) are not copied.
Hard links share the official bytes without a second 5.4 GB copy; the runtime only
reads them, and their SHA256 is checked against the archived original values.

## Using a separate build

Every native tool accepts the package executable:

```powershell
$after = 'C:/HOB/packages/patched-after/Ocean/Windows/Holodeck/Binaries/Win64/Holodeck.exe'
& $py tools/check_holoocean_backend.py --binary $after
& $py examples/verify_holoocean_drag_units.py --source-dir C:/HOB/src/after --binary $after --ticks-per-sec 60 100 200 --repeats 3 --steps-per-case 8 --output-dir logs/verified_backend/drag_after
& $py tools/audit_holoocean_timestep.py --source-dir C:/HOB/src/after --binary $after --drag-stability --output-dir logs/verified_backend/timestep_after
& $py examples/native_current_energy_study.py --holoocean-binary $after --output-dir logs/verified_backend/energy_after --label after
```

`tools/holoocean_backend.py` starts any package with the same parameters as
`holoocean.make` (world `pre_start_steps`, bounds), so the installed, rebuilt and
patched binaries differ only in the executable.

## Side effects on the build machine

* New directories `C:\UE532` (engine source, dependencies, intermediates) and
  `C:\HOB` (HoloOcean checkouts, logs, outputs, packages).
* The first run of the bundled .NET 6 SDK (before the environment variables were
  set) printed its first-run notice and created an untrusted ASP.NET Core HTTPS
  development certificate in the current user's store; it is not trusted unless
  `dotnet dev-certs https --trust` is run. Later runs set
  `DOTNET_CLI_TELEMETRY_OPTOUT=1`, `DOTNET_NOLOGO=1`,
  `DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1`, `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`.
* No system setting, Visual Studio installation, registry engine registration or
  installed HoloOcean file was changed.

## Revert

Delete `C:\HOB\packages\patched-after` (or point tools back to the installed
package by omitting `--binary`). The patch itself is reversed with
`git apply --reverse patches/holoocean-2.3-drag-units.patch` in a source checkout.
