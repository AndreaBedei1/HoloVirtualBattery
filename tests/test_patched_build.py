"""Patched-build tooling: launcher layout, pinned toolchain, guarded engine fixes."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backend = load("holoocean_backend", "tools/holoocean_backend.py")
build = load("patched_build", "tools/build_patched_holoocean.py")


def test_package_layout_is_resolved_from_the_executable(tmp_path):
    exe = tmp_path / "Ocean/Windows/Holodeck/Binaries/Win64/Holodeck.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    (tmp_path / "Ocean/config.json").write_text('{"version": "2.3.0", "worlds": []}')
    resolved, root, config = backend.resolve_binary(exe.with_suffix(""))
    assert resolved == exe.resolve() and root == (tmp_path / "Ocean").resolve()
    assert config.name == "config.json"
    stray = tmp_path / "elsewhere/Holodeck.exe"
    stray.parent.mkdir()
    stray.write_bytes(b"MZ")
    with pytest.raises(ValueError, match="Expected"):
        backend.resolve_binary(stray)


def test_build_command_pins_the_official_toolchain(tmp_path):
    from types import SimpleNamespace

    args = SimpleNamespace(
        work_root=tmp_path,
        engine_root=Path("C:/UE532"),
        engine_kind="source",
        windows_sdk=build.WINDOWS_SDK,
        max_parallel_actions=4,
    )
    command = [str(c) for c in build.ubt_command(args, "after")]
    assert "-CompilerVersion=14.44.35207" in command
    assert "-WindowsSDKVersion=10.0.22621.0" in command
    assert "-DisableAdaptiveUnity" in command
    assert "-EnablePlugin=EOSShared" in command
    assert not any(c.startswith("-Define:") for c in command)
    assert command[1:4] == ["Holodeck", "Win64", "Development"]
    assert all(name in build.GITDEPS_EXCLUDES for name in ("Content", "Android", "Linux", "Mac"))


def test_launcher_engine_build_reproduces_the_official_configuration(tmp_path):
    """Launcher engine: shared build environment, no plugin switch, ASAN include disabled."""
    from types import SimpleNamespace

    args = SimpleNamespace(
        work_root=tmp_path,
        engine_root=Path("C:/Program Files/Epic Games/UE_5.3"),
        engine_kind="launcher",
        windows_sdk="10.0.19041.0",
        max_parallel_actions=4,
    )
    command = [str(c) for c in build.ubt_command(args, "before")]
    assert "-EnablePlugin=EOSShared" not in command
    assert "-Define:PLATFORM_HAS_ASAN_INCLUDE=0" in command
    assert "-WindowsSDKVersion=10.0.19041.0" in command
    assert "-CompilerVersion=14.44.35207" in command
    assert Path("Windows/Holodeck/Octrees") in build.SKIPPED


def test_engine_compatibility_fixes_are_hash_guarded_and_syntax_only():
    for fix in build.COMPAT_FIXES:
        assert len(fix["original_sha256"]) == 64 and len(fix["fixed_sha256"]) == 64
        assert fix["old"] != fix["new"] and fix["reason"]
    header_fix, d3d12_fix = build.COMPAT_FIXES
    assert "defined(__has_feature)" in header_fix["new"]
    assert header_fix["new"].count("#define IS_ASAN_ENABLED 0") == 2
    assert d3d12_fix["new"].replace("::template ", "::") == d3d12_fix["old"]
