# Isolated HoloOcean 2.3.0 drag unit patch

This patch targets official tag `v2.3.0`, commit
`49e70552dfd97273b7dfbe755fbe65d7738b24b7`. It adds only a magnitude conversion
in `engine/Source/Holodeck/HolodeckCore/Private/HolodeckBuoyantAgent.cpp`:

```cpp
DragForce *= UEUnitsPerMeter;
```

The source equation produces newtons. The raw physics force is kg·cm/s²
(centinewtons). The relative velocity, and therefore `DragForce`, is already
in UE world axes. Calling `ConvertLinearVector(..., ClientToUE)` here would
also reflect Y a second time. Gravity, buoyancy, thrusters and coefficients
are unchanged. Debug visualization using `DragForce` also sees the converted
value, as the existing gravity/buoyancy debug vectors do.

Use a separate source checkout and separately built world, never the installed
stable package. From the root of that checkout:

```powershell
git -c core.autocrlf=false apply --check C:/path/holoocean-2.3-drag-units.patch
git -c core.autocrlf=false apply C:/path/holoocean-2.3-drag-units.patch
# Reverse from that same checkout:
git -c core.autocrlf=false apply --reverse --check C:/path/holoocean-2.3-drag-units.patch
git -c core.autocrlf=false apply --reverse C:/path/holoocean-2.3-drag-units.patch
```

Apply/check/reverse/check passed on an isolated copy, restoring the original
bytes and SHA256. A real UE rebuild and after-patch runtime regression have
**not** been performed: no usable UE 5.3 development installation/cooker was
found on the audited machine. MSVC installations exist. The stable source and
Ocean executable were not modified. This is a proposed backend correction,
not a tested replacement binary. See the [audit report](../docs/holoocean_drag_units_report.md).

The patch contains context from HoloOcean's MIT-licensed
`engine/Source/Holodeck` code. Copyright (c) 2024 BYU-FRoStLab; the source file
also carries its original 2021 BYU FRoStLab notice. The upstream MIT terms are
retained in [HOLOOCEAN_LICENSE.txt](HOLOOCEAN_LICENSE.txt). No Epic engine code
is redistributed. Building/using UE and HoloOcean assets requires the relevant
upstream Epic licensing and attribution.
