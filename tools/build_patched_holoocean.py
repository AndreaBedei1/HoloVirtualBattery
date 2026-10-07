"""Reproducible separate builds of HoloOcean 2.3.0 Ocean, without and with the drag patch.

Steps (idempotent, each verifies its inputs; run on Windows):

  engine    clone EpicGames/UnrealEngine tag 5.3.2-release (needs a GitHub account linked
            to Epic Games) and download Win64 build dependencies only (no prerequisites
            installer, no engine registration)
  source    clone byu-holoocean/HoloOcean tag v2.3.0 twice with LF line endings:
            'src/before' is the build tree, 'src/after' is a read-only reference copy
            with patches/holoocean-2.3-drag-units.patch applied (used by the audits)
  build     compile the Holodeck Win64 Development game target with the toolchain recorded
            in the official PDB (MSVC 14.44.35207, Windows SDK 10.0.22621.0): first the
            pristine tree ('before'), then the same tree with the patch applied ('after',
            incremental: only the Holodeck module changes). The tree is restored to the
            pristine tag afterwards. Executables and PDBs are kept in outputs/<variant>.
  assemble  create separate packages: built executable and PDB, runtime files copied from
            the official package, NTFS hard links to the official cooked containers
  manifest  write holoenergy_build_manifest.json (commands, versions, hashes)

One build tree is used because the project's legacy build settings force a unique
build environment: UBT compiles the whole engine into the project's Intermediate
directory (~20 GB, ~1.5 h on 14 cores), so a second tree would double both.
The installed Ocean package is only read. The Ocean worlds are not in the public
repository, so the official cooked content is reused unchanged: this is a code-only
rebuild of Holodeck.exe. Use --dry-run to print the commands without running them.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UE_REPOSITORY = "https://github.com/EpicGames/UnrealEngine.git"
UE_TAG = "5.3.2-release"
UE_COMMIT = "072300df18a94f18077ca20a14224b5d99fee872"
HOLOOCEAN_REPOSITORY = "https://github.com/byu-holoocean/HoloOcean.git"
HOLOOCEAN_TAG = "v2.3.0"
HOLOOCEAN_COMMIT = "49e70552dfd97273b7dfbe755fbe65d7738b24b7"
ORIGINAL_EXE_SHA256 = "8c206c9cc05c640fb2efea6bd43bda33c585536ab16a931c55780855e7602253"
MSVC_TOOLSET = "14.44.35207"
WINDOWS_SDK = "10.0.22621.0"
GITDEPS_EXCLUDES = [
    "Android",
    "IOS",
    "TVOS",
    "Linux",
    "LinuxArm64",
    "Mac",
    "osx",
    "osx64",
    "HoloLens",
    "Win32",
    "VisionOS",
    "Lumin",
    "Content",
    "Samples",
    "Documentation",
    "Maya_AnimationRiggingTools",
    "P4VUtils",
    "UnrealEngineLauncher",
]
VARIANTS = {
    "before": {"name": "rebuilt-before", "patched": False},
    "after": {"name": "patched-after", "patched": True},
}
PACKAGE_EXE = Path("Windows/Holodeck/Binaries/Win64/Holodeck.exe")
PAKS = Path("Windows/Holodeck/Content/Paks")
SKIPPED = {Path("Windows/Holodeck/Saved"), Path("Windows/Engine/Saved")}
DOTNET_ENV = {
    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "DOTNET_NOLOGO": "1",
    "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
    "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
}


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def run(command, dry_run, cwd=None, env=None, log=None):
    printable = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in command)
    print(f"$ {printable}", flush=True)
    if dry_run:
        return ""
    merged = os.environ | (env or {})
    if log:
        with Path(log).open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                [str(c) for c in command],
                cwd=cwd,
                env=merged,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
    else:
        result = subprocess.run(
            [str(c) for c in command], cwd=cwd, env=merged, capture_output=True, text=True
        )
    if result.returncode != 0:
        detail = "" if log else (result.stdout + result.stderr)[-4000:]
        raise RuntimeError(f"Command failed ({result.returncode}): {printable}\n{detail}")
    return "" if log else result.stdout


def git_head(path):
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


# Syntax-only engine fixes needed to compile UE 5.3.2 engine modules with MSVC 14.44.
# The official binary did not compile engine modules: Epic's precompiled Launcher engine
# used MSVC 14.36. Each fix is applied only to the expected original bytes.
COMPAT_FIXES = [
    {
        "path": "Engine/Source/Runtime/Core/Public/Experimental/ConcurrentLinearAllocator.h",
        "original_sha256": "d97c1ccbc30222fe01f320b4e9cda24c9dfcceffb0bd26562df722441fb7cad5",
        "fixed_sha256": "92e5803dabe32fd4993750c39ade4b8292b85ac9a559fc2fffc42a231f858f3b",
        "old": "#elif __has_feature(address_sanitizer)\n#define IS_ASAN_ENABLED 1\n#else\n"
        "#define IS_ASAN_ENABLED 0\n#endif\n",
        "new": "#elif defined(__has_feature)\n#if __has_feature(address_sanitizer)\n"
        "#define IS_ASAN_ENABLED 1\n#else\n#define IS_ASAN_ENABLED 0\n#endif\n"
        "#else\n#define IS_ASAN_ENABLED 0\n#endif\n",
        "reason": "MSVC >= 14.38 ships sanitizer/asan_interface.h, so the header evaluates "
        "__has_feature(), which MSVC does not define (C4668/C4067 are errors in engine "
        "modules). Nested under defined(__has_feature); IS_ASAN_ENABLED stays 0.",
    },
    {
        "path": "Engine/Source/Runtime/D3D12RHI/Private/D3D12CommandContext.h",
        "original_sha256": "8726657d7cbf2203309cd1d82621d46c0dac8ad1d718b878eea358d8005f18af",
        "fixed_sha256": "6877d6adddd7dd3a4765a5581108e92ca5a093d655f310ebda54e37d549cc720",
        "old": "return FD3D12DynamicRHI::ResourceCast<RHIType, ObjectType>(RHIObject, GPUIndex);",
        "new": "return FD3D12DynamicRHI::template ResourceCast<RHIType, ObjectType>"
        "(RHIObject, GPUIndex);",
        "reason": "MSVC >= 14.40 parses the member template of a class that is incomplete at "
        "this point as a comparison (C3878/C2760); the standard 'template' disambiguator "
        "names the same function.",
    },
]


def apply_engine_compat_fix(engine, dry_run):
    """Apply COMPAT_FIXES idempotently; refuse any unexpected file content."""
    for fix in COMPAT_FIXES:
        header = engine / fix["path"]
        print(f"engine compatibility fix: {header}", flush=True)
        if dry_run:
            continue
        digest = file_hash(header)
        if digest == fix["fixed_sha256"]:
            continue
        if digest != fix["original_sha256"]:
            raise RuntimeError(f"Unexpected {header} content; review the compatibility fix")
        text = header.read_bytes().decode("utf-8")
        if text.count(fix["old"]) != 1:
            raise RuntimeError(f"Compatibility fix anchor not found exactly once in {header}")
        header.write_bytes(text.replace(fix["old"], fix["new"]).encode("utf-8"))
        if file_hash(header) != fix["fixed_sha256"]:
            raise RuntimeError(f"Compatibility fix produced unexpected bytes in {header}")


def step_engine(args):
    engine = args.engine_root
    if not (engine / ".git").is_dir():
        run(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "-c",
                "core.autocrlf=false",
                "clone",
                "--depth",
                "1",
                "--branch",
                UE_TAG,
                "--single-branch",
                UE_REPOSITORY,
                engine,
            ],
            args.dry_run,
        )
    if not args.dry_run and git_head(engine) != UE_COMMIT:
        raise RuntimeError(f"{engine} is not {UE_TAG} ({UE_COMMIT})")
    gitdeps = engine / "Engine/Binaries/DotNET/GitDependencies/win-x64/GitDependencies.exe"
    run(
        [gitdeps, "--force", "--no-cache", "--threads=8"]
        + [f"--exclude={x}" for x in GITDEPS_EXCLUDES],
        args.dry_run,
        cwd=engine,
        log=args.work_root / "logs/gitdependencies.log",
    )
    apply_engine_compat_fix(engine, args.dry_run)


BUILD_TREE = "before"  # pristine tag; patched only while building the 'after' variant
REFERENCE_TREE = "after"  # read-only patched reference used by the audits
BUOYANT_CPP = Path("engine/Source/Holodeck/HolodeckCore/Private/HolodeckBuoyantAgent.cpp")


def clone_holoocean(target, dry_run):
    if (target / ".git").is_dir():
        return
    run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "clone",
            "--depth",
            "1",
            "--branch",
            HOLOOCEAN_TAG,
            "--single-branch",
            HOLOOCEAN_REPOSITORY,
            target,
        ],
        dry_run,
    )
    run(["git", "-C", target, "config", "core.autocrlf", "false"], dry_run)


def tracked_changes(tree):
    status = subprocess.run(
        ["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line[3:].strip() for line in status.splitlines() if line.strip()}


def set_patch_state(tree, patch, patched):
    """Apply or reverse the patch so that only the drag file differs when patched."""
    changed = tracked_changes(tree)
    target = BUOYANT_CPP.as_posix()
    if patched and target not in changed:
        run(["git", "-C", tree, "apply", "--check", patch.resolve()], False)
        run(["git", "-C", tree, "apply", patch.resolve()], False)
    elif not patched and target in changed:
        run(["git", "-C", tree, "apply", "--reverse", "--check", patch.resolve()], False)
        run(["git", "-C", tree, "apply", "--reverse", patch.resolve()], False)
    expected = {target} if patched else set()
    if tracked_changes(tree) != expected:
        raise RuntimeError(f"{tree}: unexpected tracked changes {tracked_changes(tree)}")


def source_state(tree):
    diff = subprocess.run(
        ["git", "-C", str(tree), "diff", "--binary"], capture_output=True, check=True
    ).stdout
    return {
        "repository": HOLOOCEAN_REPOSITORY,
        "tag": HOLOOCEAN_TAG,
        "commit": git_head(tree),
        "tree": str(tree),
        "working_tree_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "buoyant_agent_cpp_sha256": file_hash(tree / BUOYANT_CPP),
    }


def step_source(args):
    tree = args.work_root / "src" / BUILD_TREE
    reference = args.work_root / "src" / REFERENCE_TREE
    for target in (tree, reference):
        clone_holoocean(target, args.dry_run)
        if not args.dry_run and git_head(target) != HOLOOCEAN_COMMIT:
            raise RuntimeError(f"{target} is not {HOLOOCEAN_TAG} ({HOLOOCEAN_COMMIT})")
    if not args.dry_run:
        set_patch_state(tree, args.patch, False)
        set_patch_state(reference, args.patch, True)


def ubt_command(args, key):
    project = args.work_root / "src" / BUILD_TREE / "engine/Holodeck.uproject"
    return [
        args.engine_root / "Engine/Build/BatchFiles/Build.bat",
        "Holodeck",
        "Win64",
        "Development",
        f"-Project={project}",
        "-WaitMutex",
        "-NoHotReload",
        "-DisableAdaptiveUnity",
        f"-CompilerVersion={MSVC_TOOLSET}",
        f"-WindowsSDKVersion={WINDOWS_SDK}",
        # The official cooked plugin manifest mounts EOSShared (enabled in Epic's Launcher
        # build); without its module the packaged game exits at startup. Same plugin set.
        "-EnablePlugin=EOSShared",
        f"-MaxParallelActions={args.max_parallel_actions}",
        f"-Log={args.work_root / 'logs' / f'ubt_{key}.log'}",
    ]


def output_dir(args, key):
    return args.work_root / "outputs" / VARIANTS[key]["name"]


def step_build(args):
    (args.work_root / "logs").mkdir(parents=True, exist_ok=True)
    apply_engine_compat_fix(args.engine_root, args.dry_run)
    tree = args.work_root / "src" / BUILD_TREE
    reference = args.work_root / "src" / REFERENCE_TREE
    built = tree / "engine/Binaries/Win64/Holodeck.exe"
    try:
        for key in [k for k in VARIANTS if k in args.variants]:
            patched = VARIANTS[key]["patched"]
            if not args.dry_run:
                set_patch_state(tree, args.patch, patched)
                if patched and file_hash(tree / BUOYANT_CPP) != file_hash(reference / BUOYANT_CPP):
                    raise RuntimeError("Patched build tree differs from the patched reference")
            run(
                ubt_command(args, key),
                args.dry_run,
                env=DOTNET_ENV,
                log=args.work_root / "logs" / f"build_{key}.out",
            )
            if args.dry_run:
                continue
            out = output_dir(args, key)
            out.mkdir(parents=True, exist_ok=True)
            for suffix in (".exe", ".pdb"):
                shutil.copy2(built.with_suffix(suffix), out / f"Holodeck{suffix}")
            (out / "source_state.json").write_text(
                json.dumps(source_state(tree), indent=2) + "\n", encoding="utf-8"
            )
    finally:
        if not args.dry_run:
            set_patch_state(tree, args.patch, False)


def package_root(args, key):
    return args.work_root / "packages" / VARIANTS[key]["name"] / "Ocean"


def step_assemble(args):
    original = args.original_package
    if file_hash(original / PACKAGE_EXE) != ORIGINAL_EXE_SHA256:
        raise RuntimeError("Original package executable hash differs from the audited 2.3.0 binary")
    for key in args.variants:
        built = output_dir(args, key) / "Holodeck.exe"
        if not built.is_file():
            raise FileNotFoundError(f"Build output missing: {built}")
        target = package_root(args, key)
        print(f"Assembling {target}", flush=True)
        if args.dry_run:
            continue
        for source in sorted(original.rglob("*")):
            relative = source.relative_to(original)
            if source.is_dir() or any(relative.is_relative_to(s) for s in SKIPPED):
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if relative.parent == PAKS:
                if destination.exists():
                    if os.path.samefile(source, destination):
                        continue
                    destination.unlink()
                os.link(source, destination)  # same volume; never written by the runtime
            elif relative in (PACKAGE_EXE, PACKAGE_EXE.with_suffix(".pdb")):
                continue
            else:
                shutil.copy2(source, destination)
        for suffix in (".exe", ".pdb"):
            shutil.copy2(built.with_suffix(suffix), target / PACKAGE_EXE.with_suffix(suffix))


def toolchain_versions(args):
    cl = (
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC")
        / MSVC_TOOLSET
        / "bin/Hostx64/x64/cl.exe"
    )
    banner = None
    if cl.is_file():
        result = subprocess.run([str(cl)], capture_output=True, text=True)
        banner = (result.stderr or result.stdout).strip().splitlines()[0]
    build_version = json.loads(
        (args.engine_root / "Engine/Build/Build.version").read_text(encoding="utf-8")
    )
    dotnet = sorted((args.engine_root / "Engine/Binaries/ThirdParty/DotNet").glob("*/"))
    return {
        "msvc_toolset": MSVC_TOOLSET,
        "cl_banner": banner,
        "cl_path": str(cl),
        "windows_sdk": WINDOWS_SDK,
        "unreal_engine": {
            "repository": UE_REPOSITORY,
            "tag": UE_TAG,
            "commit": git_head(args.engine_root),
            "build_version": build_version,
            "gitdependencies_excludes": GITDEPS_EXCLUDES,
            "local_modifications": {
                fix["path"]: {
                    "sha256": file_hash(args.engine_root / fix["path"]),
                    "original_sha256": fix["original_sha256"],
                    "reason": fix["reason"],
                }
                for fix in COMPAT_FIXES
            },
        },
        "bundled_dotnet_sdk": [p.name for p in dotnet if p.is_dir()],
        "host": platform.platform(),
        "python": platform.python_version(),
    }


def step_manifest(args):
    original = args.original_package
    shared = {}
    for path in sorted((original / PAKS).iterdir()):
        shared[(PAKS / path.name).as_posix()] = {
            "sha256": file_hash(path),
            "size_bytes": path.stat().st_size,
            "mode": "NTFS hard link to the official package file",
        }
    tools = toolchain_versions(args)
    patch_hash = file_hash(args.patch)
    reference = args.work_root / "src" / REFERENCE_TREE
    for key in args.variants:
        target = package_root(args, key)
        exe = target / PACKAGE_EXE
        state_path = output_dir(args, key) / "source_state.json"
        ubt_log = args.work_root / "logs" / f"ubt_{key}.log"
        manifest = {
            "variant": VARIANTS[key]["name"],
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "separate code-only rebuild of Holodeck.exe for physics verification",
            "holoocean_source": json.loads(state_path.read_text(encoding="utf-8"))
            | {"recorded_at_build_time": str(state_path)},
            "patched_reference_tree": {
                "path": str(reference),
                "buoyant_agent_cpp_sha256": file_hash(reference / BUOYANT_CPP),
            },
            "patch": {
                "path": str(args.patch.relative_to(ROOT))
                if args.patch.is_relative_to(ROOT)
                else str(args.patch),
                "sha256": patch_hash,
                "applied": VARIANTS[key]["patched"],
            },
            "toolchain": tools,
            "build_command": [str(c) for c in ubt_command(args, key)],
            "build_environment": DOTNET_ENV,
            "build_log": {
                "path": str(ubt_log),
                "sha256": file_hash(ubt_log) if ubt_log.is_file() else None,
            },
            "outputs": {
                "executable": str(exe),
                "executable_sha256": file_hash(exe),
                "executable_size_bytes": exe.stat().st_size,
                "pdb_sha256": file_hash(exe.with_suffix(".pdb")),
            },
            "original_package": {
                "root": str(original),
                "executable_sha256": file_hash(original / PACKAGE_EXE),
                "config_sha256": file_hash(original / "config.json"),
            },
            "reused_official_cooked_content": shared,
            "limitations": [
                "Ocean worlds are not public; official cooked content reused unchanged",
                "engine built from GitHub source (Build.version Changelist 0), official binary from "
                "the Launcher build of the same 5.3.2 release (CL 29314046)",
                "behavioural equivalence with the official binary is tested, not assumed",
            ],
        }
        (target / "holoenergy_build_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Manifest: {target / 'holoenergy_build_manifest.json'}", flush=True)


STEPS = {
    "engine": step_engine,
    "source": step_source,
    "build": step_build,
    "assemble": step_assemble,
    "manifest": step_manifest,
}


def main():
    if sys.platform != "win32":
        raise SystemExit("The documented Ocean 2.3.0 rebuild targets Windows Win64")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--work-root", type=Path, default=Path("C:/HOB"))
    parser.add_argument("--engine-root", type=Path, default=Path("C:/UE532"))
    parser.add_argument(
        "--original-package",
        type=Path,
        default=Path.home() / "AppData/Local/holoocean/2.3.0/worlds/Ocean",
    )
    parser.add_argument(
        "--patch", type=Path, default=ROOT / "patches/holoocean-2.3-drag-units.patch"
    )
    parser.add_argument("--steps", nargs="+", choices=list(STEPS), default=list(STEPS))
    parser.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS))
    parser.add_argument("--max-parallel-actions", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for step in args.steps:
        print(f"== {step}", flush=True)
        STEPS[step](args)


if __name__ == "__main__":
    main()
