"""Small generators for model-import tests (ETABS-style e2k text)."""


def building_e2k(nx=2, ny=2, storeys=2, bay=5.0, h=3.2, slabs=True, diaph=True, q_dead=2.0, q_live=2.0,
                 col="C50", beam="B40X50", steel=False, release_beams=False) -> str:
    out = ['$ CONTROLS', '  UNITS "KN" "M" "C"', '$ STORIES - IN SEQUENCE FROM TOP']
    for s in range(storeys, 0, -1):
        out.append(f'  STORY "S{s}" HEIGHT {h}')
    out.append('  STORY "Base" ELEV 0')
    out += ['$ DIAPHRAGM NAMES', '  DIAPHRAGM "D1" TYPE RIGID', '$ MATERIAL PROPERTIES',
            '  MATERIAL "C30" TYPE "Concrete" WEIGHTPERVOLUME 25', '  MATERIAL "C30" SYMTYPE "Isotropic" E 27000000 U 0.2',
            '  MATERIAL "ST37" TYPE "Steel" WEIGHTPERVOLUME 77', '  MATERIAL "ST37" SYMTYPE "Isotropic" E 200000000 U 0.3',
            '$ FRAME SECTIONS']
    if steel:
        out += [f'  FRAMESECTION "{col}" MATERIAL "ST37" SHAPE "{col}"', f'  FRAMESECTION "{beam}" MATERIAL "ST37" SHAPE "{beam}"']
    else:
        out += [f'  FRAMESECTION "{col}" MATERIAL "C30" SHAPE "Concrete Rectangular" D 0.5 B 0.5',
                f'  FRAMESECTION "{beam}" MATERIAL "C30" SHAPE "Concrete Rectangular" D 0.5 B 0.4']
    out += ['$ SLAB PROPERTIES', '  SHELLPROP "SLAB15" PROPTYPE "Slab" MATERIAL "C30" MODELINGTYPE "Membrane" SLABTHICKNESS 0.15',
            '$ POINT COORDINATES']
    pid = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            pid[(i, j)] = f"{i}_{j}"
            out.append(f'  POINT "{i}_{j}" {i * bay} {j * bay}')
    out.append('$ LINE CONNECTIVITIES')
    lines = []
    for (i, j), p in pid.items():
        out.append(f'  LINE "C{p}" COLUMN "{p}" "{p}" 1'); lines.append((f"C{p}", col))
        if i < nx:
            out.append(f'  LINE "BX{p}" BEAM "{p}" "{pid[(i + 1, j)]}" 0'); lines.append((f"BX{p}", beam))
        if j < ny:
            out.append(f'  LINE "BY{p}" BEAM "{p}" "{pid[(i, j + 1)]}" 0'); lines.append((f"BY{p}", beam))
    out.append('$ AREA CONNECTIVITIES')
    areas = []
    for i in range(nx):
        for j in range(ny):
            a = f"F{i}_{j}"
            out.append(f'  AREA "{a}" FLOOR 4 "{pid[(i, j)]}" "{pid[(i + 1, j)]}" "{pid[(i + 1, j + 1)]}" "{pid[(i, j + 1)]}" 0 0 0 0')
            areas.append(a)
    out.append('$ POINT ASSIGNS')
    for p in pid.values():
        out.append(f'  POINTASSIGN "{p}" "Base" RESTRAINT "UX UY UZ RX RY RZ"')
    out.append('$ LINE ASSIGNS')
    for s in range(1, storeys + 1):
        for ln, sec in lines:
            rel = ' RELEASE "M2I M3I M2J M3J"' if release_beams and ln.startswith("B") else ""
            out.append(f'  LINEASSIGN "{ln}" "S{s}" SECTION "{sec}"{rel}')
    out.append('$ AREA ASSIGNS')
    if slabs:
        for s in range(1, storeys + 1):
            for a in areas:
                out.append(f'  AREAASSIGN "{a}" "S{s}" SECTION "SLAB15"' + (' DIAPH "D1"' if diaph else ""))
    out += ['$ LOAD PATTERNS', '  LOADPATTERN "Dead" TYPE "Dead" SELFWEIGHT 1', '  LOADPATTERN "Live" TYPE "Live" SELFWEIGHT 0',
            '  LOADPATTERN "EX" TYPE "Seismic" SELFWEIGHT 0', '  LOADPATTERN "EY" TYPE "Seismic" SELFWEIGHT 0', '$ SHELL OBJECT LOADS']
    if slabs:
        for s in range(1, storeys + 1):
            for a in areas:
                out.append(f'  AREALOAD "{a}" "S{s}" TYPE "UNIFF" DIR "GRAV" LC "Dead" FVAL {q_dead}')
                out.append(f'  AREALOAD "{a}" "S{s}" TYPE "UNIFF" DIR "GRAV" LC "Live" FVAL {q_live}')
    return "\n".join(out) + "\n"
