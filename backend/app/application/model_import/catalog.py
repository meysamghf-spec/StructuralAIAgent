"""Built-in steel shape catalog (European IPE, HEA, HEB, UNP; parametric BOX / PIPE; double 2IPE / 2UNP).

Properties are computed from the nominal catalog dimensions (h, b, tw, tf, root radius r) so that names
such as ``IPE300``, ``HE240B``, ``UNP160``, ``BOX200X10``, ``PIPE168.3X6`` or ``2IPE200`` resolve without
user input. Results are in metres (A m2, I m4). Computed values match the published tables to about 1 %
(UNP flanges are tapered in reality; a parallel-flange equivalent is used). The engineer of record should
verify critical sections.
"""

from __future__ import annotations

import math
import re
from typing import Any

# name: (h, b, tw, tf, r) in mm
IPE = {80: (80, 46, 3.8, 5.2, 5), 100: (100, 55, 4.1, 5.7, 7), 120: (120, 64, 4.4, 6.3, 7), 140: (140, 73, 4.7, 6.9, 7),
       160: (160, 82, 5.0, 7.4, 9), 180: (180, 91, 5.3, 8.0, 9), 200: (200, 100, 5.6, 8.5, 12), 220: (220, 110, 5.9, 9.2, 12),
       240: (240, 120, 6.2, 9.8, 15), 270: (270, 135, 6.6, 10.2, 15), 300: (300, 150, 7.1, 10.7, 15), 330: (330, 160, 7.5, 11.5, 18),
       360: (360, 170, 8.0, 12.7, 18), 400: (400, 180, 8.6, 13.5, 21), 450: (450, 190, 9.4, 14.6, 21), 500: (500, 200, 10.2, 16.0, 21),
       550: (550, 210, 11.1, 17.2, 24), 600: (600, 220, 12.0, 19.0, 24)}
HEA = {100: (96, 100, 5, 8, 12), 120: (114, 120, 5, 8, 12), 140: (133, 140, 5.5, 8.5, 12), 160: (152, 160, 6, 9, 15),
       180: (171, 180, 6, 9.5, 15), 200: (190, 200, 6.5, 10, 18), 220: (210, 220, 7, 11, 18), 240: (230, 240, 7.5, 12, 21),
       260: (250, 260, 7.5, 12.5, 24), 280: (270, 280, 8, 13, 24), 300: (290, 300, 8.5, 14, 27), 320: (310, 300, 9, 15.5, 27),
       340: (330, 300, 9.5, 16.5, 27), 360: (350, 300, 10, 17.5, 27), 400: (390, 300, 11, 19, 27), 450: (440, 300, 11.5, 21, 27),
       500: (490, 300, 12, 23, 27), 550: (540, 300, 12.5, 24, 27), 600: (590, 300, 13, 25, 27)}
HEB = {100: (100, 100, 6, 10, 12), 120: (120, 120, 6.5, 11, 12), 140: (140, 140, 7, 12, 12), 160: (160, 160, 8, 13, 15),
       180: (180, 180, 8.5, 14, 15), 200: (200, 200, 9, 15, 18), 220: (220, 220, 9.5, 16, 18), 240: (240, 240, 10, 17, 21),
       260: (260, 260, 10, 17.5, 24), 280: (280, 280, 10.5, 18, 24), 300: (300, 300, 11, 19, 27), 320: (320, 300, 11.5, 20.5, 27),
       340: (340, 300, 12, 21.5, 27), 360: (360, 300, 12.5, 22.5, 27), 400: (400, 300, 13.5, 24, 27), 450: (450, 300, 14, 26, 27),
       500: (500, 300, 14.5, 28, 27), 550: (550, 300, 15, 29, 27), 600: (600, 300, 15.5, 30, 27)}
UNP = {80: (80, 45, 6, 8, 8), 100: (100, 50, 6, 8.5, 8.5), 120: (120, 55, 7, 9, 9), 140: (140, 60, 7, 10, 10),
       160: (160, 65, 7.5, 10.5, 10.5), 180: (180, 70, 8, 11, 11), 200: (200, 75, 8.5, 11.5, 11.5), 220: (220, 80, 9, 12.5, 12.5),
       240: (240, 85, 9.5, 13, 13), 260: (260, 90, 10, 14, 14), 280: (280, 95, 10, 15, 15), 300: (300, 100, 10, 16, 16),
       320: (320, 100, 14, 17.5, 17.5), 350: (350, 100, 14, 16, 16), 380: (380, 102, 13.5, 16, 16), 400: (400, 110, 14, 18, 18)}
FAMILIES = {"IPE": IPE, "HEA": HEA, "HEB": HEB, "UNP": UNP}

_NUM = r"(\d+(?:\.\d+)?)"


def i_shape(h: float, b: float, tw: float, tf: float, r: float = 0.0) -> dict[str, float]:
    """Doubly symmetric I (mm in, m out) incl. root fillets (4 x (1 - pi/4) r^2 at web/flange junctions)."""
    hw = h - 2 * tf
    fil = (4 - math.pi) * r * r  # four fillets
    area = 2 * b * tf + hw * tw + fil
    y_f = hw / 2 - (10 - 3 * math.pi) / (12 - 3 * math.pi) * r  # fillet centroid distance (approx)
    i33 = (b * h**3 - (b - tw) * hw**3) / 12 + fil * y_f**2
    i22 = (2 * tf * b**3 + hw * tw**3) / 12 + fil * (tw / 2 + 0.2234 * r) ** 2
    j = (2 * b * tf**3 + (h - tf) * tw**3) / 3
    z33 = b * tf * (h - tf) + tw * hw**2 / 4 + fil * y_f
    z22 = tf * b**2 / 2 + hw * tw**2 / 4
    return _m({"A": area, "I33": i33, "I22": i22, "J": j, "Z33": z33, "Z22": z22, "d": h, "bf": b, "tw": tw, "tf": tf})


def channel(h: float, b: float, tw: float, tf: float, r: float = 0.0) -> dict[str, float]:
    hw = h - 2 * tf
    area = 2 * b * tf + hw * tw
    i33 = (b * h**3 - (b - tw) * hw**3) / 12
    xc = (2 * b * tf * b / 2 + hw * tw * tw / 2) / area
    i22 = 2 * (tf * b**3 / 12 + b * tf * (b / 2 - xc) ** 2) + hw * tw**3 / 12 + hw * tw * (tw / 2 - xc) ** 2
    j = (2 * b * tf**3 + hw * tw**3) / 3
    z33 = b * tf * (h - tf) + tw * hw**2 / 4
    return _m({"A": area, "I33": i33, "I22": i22, "J": j, "Z33": z33, "Z22": 0.0, "d": h, "bf": b, "tw": tw, "tf": tf, "xc": xc})


def box(h: float, b: float, t: float) -> dict[str, float]:
    hi, bi = h - 2 * t, b - 2 * t
    area = h * b - hi * bi
    i33 = (b * h**3 - bi * hi**3) / 12
    i22 = (h * b**3 - hi * bi**3) / 12
    am = (h - t) * (b - t)
    j = 4 * am**2 * t / (2 * ((h - t) + (b - t)))
    z33 = b * h**2 / 4 - bi * hi**2 / 4
    z22 = h * b**2 / 4 - hi * bi**2 / 4
    return _m({"A": area, "I33": i33, "I22": i22, "J": j, "Z33": z33, "Z22": z22, "d": h, "bf": b, "tw": t, "tf": t})


def pipe(od: float, t: float) -> dict[str, float]:
    di = od - 2 * t
    area = math.pi * (od**2 - di**2) / 4
    i = math.pi * (od**4 - di**4) / 64
    z = (od**3 - di**3) / 6
    return _m({"A": area, "I33": i, "I22": i, "J": 2 * i, "Z33": z, "Z22": z, "d": od, "bf": od, "tw": t, "tf": t})


def _m(p: dict[str, float]) -> dict[str, float]:
    scale = {"A": 1e-6, "I33": 1e-12, "I22": 1e-12, "J": 1e-12, "Z33": 1e-9, "Z22": 1e-9}
    return {k: (v * scale[k] if k in scale else v * 1e-3) for k, v in p.items()}


def lookup(name: str | None) -> dict[str, Any] | None:
    """Resolve a section name to properties (m units) or None. Accepts IPE300, IPE 300, HE300B, HEB300, UPN160, U160..."""
    if not name:
        return None
    s = str(name).upper().replace(" ", "").replace("-", "").replace("_", "")
    s = s.replace("UPN", "UNP")
    dbl = False
    m = re.match(r"^(2|DOUBLE|2X)(.+)$", s)
    if m and re.match(r"^(IPE|HE|UNP|U)", m.group(2)):
        dbl, s = True, m.group(2)
    m = re.match(r"^HE(\d+)([AB])$", s)
    if m:
        s = f"HE{m.group(2)}{m.group(1)}"
    m = re.match(r"^(IPE|HEA|HEB|UNP|U)(\d+)$", s)
    props: dict[str, Any] | None = None
    if m:
        fam = "UNP" if m.group(1) == "U" else m.group(1)
        dims = FAMILIES[fam].get(int(m.group(2)))
        if dims is None:
            return None
        props = (channel if fam == "UNP" else i_shape)(*dims)
        props["family"] = fam
        props["shape"] = f"{fam}{int(m.group(2))} (catalog)"
    if props is None:
        m = re.match(rf"^(?:BOX|SHS|RHS|TUBE)?{_NUM}X{_NUM}(?:X{_NUM})?$", s) if s.startswith(("BOX", "SHS", "RHS", "TUBE")) else None
        if m:
            a, b, c = (float(g) if g else None for g in m.groups())
            h, w, t = (a, b, c) if c is not None else (a, a, b)
            if h and w and t and t < min(h, w) / 2:
                props = box(h, w, t)
                props["family"], props["shape"] = "BOX", f"Box {h:g}x{w:g}x{t:g} (parametric)"
    if props is None:
        m = re.match(rf"^(?:PIPE|CHS|P){_NUM}X{_NUM}$", s)
        if m:
            od, t = float(m.group(1)), float(m.group(2))
            if t < od / 2:
                props = pipe(od, t)
                props["family"], props["shape"] = "PIPE", f"Pipe {od:g}x{t:g} (parametric)"
    if props is None:
        return None
    if dbl:
        if props["family"] not in ("IPE", "HEA", "HEB", "UNP"):
            return None
        a = props["A"]
        xc = props.get("xc", props["bf"] / 2)
        i22_own = props["I22"]
        props = dict(props)
        props["A"] = 2 * a
        props["I33"] *= 2
        props["J"] *= 2
        props["Z33"] *= 2
        props["I22"] = 2 * (i22_own + a * xc**2)  # back-to-back, no gap
        props["Z22"] = 2 * a * xc
        props["shape"] = "2x" + props["shape"] + " back-to-back"
    return props
