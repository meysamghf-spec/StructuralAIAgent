"""Program -> per-floor room layout (metres, building-local axes).

Axes: x along the street frontage (0 = west party wall), y from the front facade (0, faces the yard/street)
to the back facade (Db). Rooms are axis-aligned rectangles whose edges are wall centre lines (exterior walls
are drawn inward from the boundary). The generator is deliberately rule-based and generic: plot size, floors,
units, bedrooms, parking and elevator all come from the program; dimensions from ArchRules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .program import BuildingProgram
from .rules import ArchRules

NAMES = {  # kind: (en, fa)
    "living": ("Living", "پذیرایی"), "hall": ("Dining", "ناهارخوری"), "family": ("Family room", "نشیمن"), "kitchen": ("Kitchen", "آشپزخانه"),
    "bedroom": ("Bedroom", "اتاق خواب"), "master": ("Master bedroom", "اتاق خواب اصلی"), "bath": ("Bath", "حمام"),
    "wc": ("WC", "سرویس بهداشتی"), "corridor": ("Corridor", "راهرو"), "lobby": ("Lobby", "لابی"),
    "stair": ("Stair", "راه پله"), "elevator": ("Elevator", "آسانسور"), "parking": ("Parking", "پارکینگ"),
    "storage": ("Storage", "انباری"), "balcony": ("Balcony", "بالکن"), "roof": ("Roof terrace", "بام"),
    "stairhouse": ("Stair house", "خرپشته"), "landing": ("Landing", "پاگرد"),
}
OPEN_PAIRS = {frozenset(p) for p in (("living", "hall"), ("living", "family"), ("family", "hall"), ("family", "kitchen"), ("family", "corridor"), ("hall", "kitchen"), ("hall", "corridor"), ("lobby", "stair"),
                                     ("landing", "stair"), ("roof", "roof"), ("parking", "parking"), ("lobby", "landing"))}


@dataclass
class Room:
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    unit: int = 0
    num: int = 0

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    @property
    def en(self) -> str:
        return NAMES[self.kind][0] + (f" {self.num}" if self.num else "")

    @property
    def fa(self) -> str:
        return NAMES[self.kind][1] + (f" {self.num}" if self.num else "")


@dataclass
class Opening:
    kind: str            # door | window | gate | opening
    horizontal: bool     # True -> on a wall parallel to x (at y=line)
    line: float
    a0: float
    a1: float
    into: str = ""       # room kind the door swings into
    swing_pos: bool = True   # door swings toward +y (horizontal) / +x (vertical)
    hinge_low: bool = True
    tag: str = ""        # D1/W2 schedule tag
    sill: float = 0.0
    head: float = 2.1


@dataclass
class Floor:
    index: int
    kind: str            # ground | typical | roof
    name_en: str
    name_fa: str
    z: float             # finished floor level (m)
    height: float
    rooms: list[Room] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    balconies: list[Room] = field(default_factory=list)
    stalls: list[tuple[float, float, float, float]] = field(default_factory=list)


@dataclass
class Layout:
    program: BuildingProgram
    rules: ArchRules
    W: float
    D: float              # building depth
    floors: list[Floor]
    core: tuple[float, float, float, float]       # x0, y0, x1, y1 of stair+elevator
    stair: tuple[float, float, float, float]
    shaft: tuple[float, float, float, float] | None
    grid_x: list[float]
    grid_y: list[float]
    assumptions: list[str]
    warnings: list[str]
    yard_depth: float
    side_setback: float
    stair_flight_len: float
    risers_per_flight: int

    @property
    def total_height(self) -> float:
        return self.floors[-1].z


def _r(v: float) -> float:
    return round(v * 20) / 20  # 5 cm grid


def _door(fl: Floor, a: Room, b: Room, width: float, tag: str, at_end: str = "low") -> bool:
    """Door between rooms a and b on their shared edge (swings into a). Returns False when not adjacent."""
    eps = 1e-6
    if abs(a.y0 - b.y1) < eps or abs(a.y1 - b.y0) < eps:  # horizontal shared edge
        line = a.y0 if abs(a.y0 - b.y1) < eps else a.y1
        lo, hi = max(a.x0, b.x0), min(a.x1, b.x1)
        if hi - lo < width + 0.2:
            return False
        s = lo + 0.15 if at_end == "low" else (hi - 0.15 - width if at_end == "high" else (lo + hi - width) / 2)
        fl.openings.append(Opening("door", True, line, s, s + width, into=a.kind, swing_pos=(line == a.y0), hinge_low=at_end != "high", tag=tag, head=2.1))
        return True
    if abs(a.x0 - b.x1) < eps or abs(a.x1 - b.x0) < eps:
        line = a.x0 if abs(a.x0 - b.x1) < eps else a.x1
        lo, hi = max(a.y0, b.y0), min(a.y1, b.y1)
        if hi - lo < width + 0.2:
            return False
        s = lo + 0.15 if at_end == "low" else (hi - 0.15 - width if at_end == "high" else (lo + hi - width) / 2)
        fl.openings.append(Opening("door", False, line, s, s + width, into=a.kind, swing_pos=(line == a.x0), hinge_low=at_end != "high", tag=tag, head=2.1))
        return True
    return False


def _windows(fl: Floor, D: float, r: ArchRules) -> None:
    for rm in fl.rooms:
        if rm.kind in ("corridor", "elevator", "parking", "roof", "lobby", "landing"):
            continue
        for line in (0.0, D):
            if abs(rm.y0 - line) < 1e-6 or abs(rm.y1 - line) < 1e-6:
                L = rm.x1 - rm.x0
                if rm.kind in ("bath", "wc"):
                    w, tag, sill = min(0.6, L - 0.4), "W3", r.wet_window_sill_m
                elif rm.kind in ("living", "hall"):
                    w, tag, sill = min(2.4, L - 0.8), "W1", r.window_sill_m
                elif rm.kind == "stair":
                    w, tag, sill = min(1.2, L - 0.6), "W4", 1.0
                else:
                    w, tag, sill = min(1.6, L - 0.8), "W2", r.window_sill_m
                if w >= 0.5:
                    c = (rm.x0 + rm.x1) / 2
                    fl.openings.append(Opening("window", True, line, _r(c - w / 2), _r(c + w / 2), tag=tag, sill=sill, head=r.window_head_m))


def _grid(cands: list[float], total: float, lo=3.0, hi=5.5) -> list[float]:
    pts = sorted({round(c, 3) for c in cands if 0 < c < total} | {0.0, round(total, 3)})
    out, i = [0.0], 0
    while out[-1] < total - 1e-6:
        nxt = [p for p in pts if lo <= p - out[-1] <= hi]
        if nxt:
            out.append(max(nxt))
        else:
            rest = total - out[-1]
            if rest <= hi:
                out.append(total)
            else:
                out.append(out[-1] + rest / math.ceil(rest / hi))
        i += 1
        if i > 50:
            break
    if len(out) > 2 and out[-1] - out[-2] < lo * 0.6:
        out.pop(-2)
    return [round(v, 3) for v in out]


def generate(p: BuildingProgram) -> Layout:
    r = p.rules_obj()
    assumptions: list[str] = []
    warnings: list[str] = []
    units = p.units_per_floor
    if units > 2:
        warnings.append(f"{units} units per floor requested; this version lays out at most 2 units per floor, so 2 are drawn.")
        units = 2
    if units == 2 and p.plot_width_m < 14:
        warnings.append("Plot narrower than 14 m: 2 units per floor do not fit well; 1 unit per floor is drawn.")
        units = 1
    ss = r.side_setback_m
    W = _r(p.plot_width_m - 2 * ss)
    D = _r(r.occupancy_depth(p.plot_depth_m))
    yard = p.plot_depth_m - D
    assumptions.append(f"Occupancy {r.occupancy_pct:.0f}% of plot depth + {r.occupancy_extra_m:g} m -> building depth {D:.2f} m, yard {yard:.2f} m (municipal rule, configurable).")
    elevator = p.has_elevator()
    assumptions.append(("Elevator provided" if elevator else "No elevator") + f" (rule: required from {r.elevator_from_floors} storeys; program floors {p.floors}).")
    # stair geometry
    h = r.floor_to_floor_m
    risers = math.ceil(h / r.riser_m)
    rpf = math.ceil(risers / 2)
    flight = (rpf - 1) * r.tread_m
    sl = _r(flight + 2 * 1.2)            # two landings
    sw = _r(2 * r.stair_width_m + 0.15)
    assumptions.append(f"Stair: 2 flights x {r.stair_width_m:.2f} m, {risers} risers of {h / risers:.3f} m, tread {r.tread_m:.2f} m (Mabhas 4 limits).")
    ew = r.elevator_shaft_m[0] if elevator else 0.0
    cw = sw + ew
    bd = max(sl, 3.6)
    if units == 1:
        cx0 = W - cw
    else:
        cx0 = _r(W / 2 - cw / 2)
    cx1 = cx0 + cw
    core = (cx0, D - bd, cx1, D)
    stair = (cx0, D - bd, cx0 + sw, D)
    shaft = (cx0 + sw, D - bd + (bd - r.elevator_shaft_m[1]), cx1, D) if elevator else None
    cor_w = max(r.min_corridor_w_m, 1.2)
    fd = D - bd - cor_w       # front band depth
    if fd < 6.0:
        warnings.append("Building is shallow; front rooms are compact.")
    floors: list[Floor] = []
    z = 0.0
    n_above = p.floors
    parking = p.parking and r.pilotis_ground_floor
    for i in range(n_above + 1):
        if i == n_above:
            fl = Floor(i, "roof", "Roof plan", "پلان بام", z, 0.0)
        elif i == 0 and parking:
            fl = Floor(i, "ground", "Ground floor (parking)", "پلان همکف (پارکینگ)", z, r.ground_floor_to_floor_m)
        else:
            nm = i + (0 if parking else 1)
            fl = Floor(i, "typical", f"Floor {nm} plan", f"پلان طبقه {nm}", z, r.floor_to_floor_m if i else r.ground_floor_to_floor_m)
        floors.append(fl)
        z = round(z + fl.height, 3)
    for fl in floors:
        if fl.kind == "roof":
            fl.rooms = [Room("stairhouse", cx0, D - bd, cx0 + sw, D)]
            if shaft:
                fl.rooms.append(Room("elevator", *shaft))
            fl.rooms.append(Room("roof", 0, 0, W, D - bd))
            if cx0 > 0.01:
                fl.rooms.append(Room("roof", 0, D - bd, cx0, D))
            if W - cx1 > 0.01:
                fl.rooms.append(Room("roof", cx1, D - bd, W, D))
            if shaft and shaft[1] > D - bd + 0.01:
                fl.rooms.append(Room("roof", shaft[0], D - bd, shaft[2], shaft[1]))
            st = fl.rooms[0]
            _door(fl, st, fl.rooms[2 if shaft else 1], 0.9, "D4", at_end="low")
            _windows(fl, D, r)
            continue
        if fl.kind == "ground":
            lw = 1.6
            lx0 = cx0 - lw if units == 1 else _r(W / 2 - lw / 2)
            lx0 = max(0.0, lx0)
            lobby = Room("lobby", lx0, 0, lx0 + lw, D - bd)
            st = Room("stair", *stair)
            fl.rooms += [lobby, st]
            if shaft:
                fl.rooms.append(Room("elevator", *shaft))
                if shaft[1] > D - bd + 0.01:
                    fl.rooms.append(Room("landing", shaft[0], D - bd, shaft[2], shaft[1]))
            parks = [Room("parking", 0, 0, lx0, D - bd)] if lx0 > 0.01 else []
            if lobby.x1 < W - 0.01:
                parks.append(Room("parking", lobby.x1, 0, W, D - bd))
            fl.rooms += parks
            need = math.ceil(r.parking_per_unit * units * max(1, n_above - 1))
            got = 0
            for pk in parks:
                cols = int((pk.x1 - pk.x0 + 0.01) // r.stall_w_m)
                rows = int((pk.y1 - pk.y0 - r.driveway_w_m * 0 + 0.01) // r.stall_l_m)
                for cxi in range(cols):
                    for ryi in range(rows):
                        if got >= need:
                            break
                        x = pk.x0 + cxi * r.stall_w_m
                        y = pk.y1 - (ryi + 1) * r.stall_l_m
                        fl.stalls.append((x, y, x + r.stall_w_m, y + r.stall_l_m))
                        got += 1
            if got < need:
                warnings.append(f"Parking: {got} stalls fit, {need} required (1 per unit) -> check tandem/mechanical parking.")
            assumptions.append(f"Ground floor = pilotis parking: {got} stalls of {r.stall_w_m}x{r.stall_l_m} m (required {need}).")
            # storages along the back band
            segs = [(0.0, cx0), (cx1, W)]
            k = 0
            for a, b in segs:
                if b - a < 1.4:
                    continue
                n = max(1, int((b - a) // 1.6))
                for j in range(n):
                    k += 1
                    fl.rooms.append(Room("storage", _r(a + (b - a) * j / n), D - bd, _r(a + (b - a) * (j + 1) / n), D, num=k))
            for s_ in [x for x in fl.rooms if x.kind == "storage"]:
                for pk in parks:
                    if _door(fl, s_, pk, 0.8, "D3", at_end="mid"):
                        break
            # entrance & gate on the front facade
            fl.openings.append(Opening("door", True, 0.0, lobby.x0 + 0.3, lobby.x0 + 0.3 + min(1.1, lw - 0.4), into="lobby", swing_pos=True, tag="D1", head=2.2))
            for pk in parks:
                gw = min(r.driveway_w_m, pk.x1 - pk.x0 - 0.3)
                if gw >= 2.4:
                    c = (pk.x0 + pk.x1) / 2
                    fl.openings.append(Opening("gate", True, 0.0, _r(c - gw / 2), _r(c + gw / 2), tag="G1", head=2.4))
                    break
            _windows(fl, D, r)
            continue
        # typical residential floor
        st = Room("stair", *stair)
        fl.rooms.append(st)
        if shaft:
            fl.rooms.append(Room("elevator", *shaft))
            if shaft[1] > D - bd + 0.01:
                fl.rooms.append(Room("landing", shaft[0], D - bd, shaft[2], shaft[1]))
        lob = Room("lobby", cx0, fd, cx1, D - bd)
        fl.rooms.append(lob)
        ranges = [(0.0, W)] if units == 1 else [(0.0, W / 2), (W / 2, W)]
        for u, (ux0, ux1) in enumerate(ranges, start=1):
            _unit(fl, u, ux0, ux1, fd, cor_w, D, bd, core, p.bedrooms, r, lob, warnings)
        _windows(fl, D, r)
    # balconies on typical floors (front facade, in front of the living room)
    for fl in floors:
        if fl.kind != "typical":
            continue
        for rm in [x for x in fl.rooms if x.kind == "living"]:
            bw = min(3.6, rm.x1 - rm.x0 - 0.6)
            c = (rm.x0 + rm.x1) / 2
            if bw >= 1.8 and yard >= r.balcony_depth_m + 1:
                fl.balconies.append(Room("balcony", _r(c - bw / 2), -r.balcony_depth_m, _r(c + bw / 2), 0, unit=rm.unit))
                for o in list(fl.openings):   # living window becomes a balcony door
                    if o.kind == "window" and o.horizontal and o.line == 0.0 and rm.x0 <= o.a0 and o.a1 <= rm.x1:
                        o.kind, o.tag, o.sill, o.head = "slider", "D5", 0.0, r.window_head_m
                        side = min(o.a0 - rm.x0, rm.x1 - o.a1)
                        if side >= 2.0:  # flanking windows in wide living rooms
                            for cc in (rm.x0 + side / 2, o.a1 + (rm.x1 - o.a1) / 2):
                                fl.openings.append(Opening("window", True, 0.0, _r(cc - 0.7), _r(cc + 0.7), tag="W2", sill=r.window_sill_m, head=r.window_head_m))
                        break
    if p.parking:
        assumptions.append("Street entrance via the ground-floor lobby; ramp-free parking at street level (+0.00 = street +0.15).")
    xs = [c for fl in floors for rm in fl.rooms for c in (rm.x0, rm.x1)]
    ys = [c for fl in floors for rm in fl.rooms for c in (rm.y0, rm.y1)]
    gx, gy = _grid(xs, W), _grid(ys, D)
    assumptions.append(f"Structural grid {len(gx)}x{len(gy)} axes (bays 3.0-5.5 m), {p.structure} frame; to be confirmed by structural design.")
    assumptions.append(f"Walls: exterior {r.exterior_wall_m*100:.0f} cm, party {r.party_wall_m*100:.0f} cm, interior {r.interior_wall_m*100:.0f} cm.")
    return Layout(p, r, W, D, floors, core, stair, shaft, gx, gy, assumptions, warnings, yard, ss, flight, rpf)


def _unit(fl: Floor, u: int, ux0: float, ux1: float, fd: float, cor_w: float, D: float, bd: float,
          core, bedrooms: int, r: ArchRules, lob: Room, warnings: list[str]) -> None:
    cx0, _, cx1, _ = core
    yb = D - bd
    # back band segments of this unit outside the core
    segs = [(max(ux0, a), min(ux1, b)) for a, b in ((0.0, cx0), (cx1, 1e9))]
    segs = [(a, b) for a, b in segs if b - a > 0.6]
    # corridor (unit part of the corridor band, outside the lobby)
    cor_parts = [(max(ux0, a), min(ux1, b)) for a, b in ((0.0, cx0), (cx1, 1e9))]
    cor_parts = [(a, b) for a, b in cor_parts if b - a > 0.3]
    beds_left = bedrooms
    wet_done = False
    rooms: list[Room] = []
    # wet strip next to the core (plumbing near the shaft) in the widest segment
    segs.sort(key=lambda s: -(s[1] - s[0]))
    for a, b in segs:
        near_core_high = abs(b - cx0) < 1e-6  # segment ends at the core
        if not wet_done and b - a >= 2.0:
            wa, wb = (b - 2.0, b) if near_core_high else (a, a + 2.0)
            rooms.append(Room("wc", wa, yb, wb, yb + 1.5, unit=u))
            rooms.append(Room("bath", wa, yb + 1.5, wb, D, unit=u))
            a, b = (a, wa) if near_core_high else (wb, b)
            wet_done = True
        rem = b - a
        n = min(beds_left, int(rem // 3.0))
        for j in range(n):
            rooms.append(Room("bedroom", _r(a + rem * j / n), yb, _r(a + rem * (j + 1) / n), D, unit=u))
        beds_left -= n
        if n == 0 and rem > 0.6:
            rooms.append(Room("storage", a, yb, b, D, unit=u))
    # front band: living along the facade, a back strip with kitchen / extra bedrooms / hall
    strip = min(3.6, fd * 0.45)
    if fd - strip > 6.0:  # keep the living room ≤ 6 m deep; the strip (kitchen/dining hall) takes the rest
        strip = min(fd - 6.0, 5.0)
    ys = fd - strip
    if not wet_done:
        beds_left += 0
    inner_high = (ux1 <= cx0 + 1e-6) or (ux0 < cx0 < ux1 and abs(ux1 - (cx1 if cx1 <= ux1 else ux1)) < 1e-6 and False)
    # kitchen sits on the side nearest the core
    core_mid = (cx0 + cx1) / 2
    k_high = abs(ux1 - core_mid) < abs(ux0 - core_mid) or (ux0 <= core_mid <= ux1 and core_mid > (ux0 + ux1) / 2)
    _ = inner_high
    kw = 3.2
    pieces: list[Room] = []
    if k_high:
        pieces.append(Room("kitchen", ux1 - kw, ys, ux1, fd, unit=u))
        free = (ux0, ux1 - kw)
    else:
        pieces.append(Room("kitchen", ux0, ys, ux0 + kw, fd, unit=u))
        free = (ux0 + kw, ux1)
    a, b = free
    if not wet_done and b - a >= 2.0 + 2.0:
        if k_high:
            pieces.append(Room("wc", a, ys, a + 1.2, fd, unit=u)); pieces.append(Room("bath", a + 1.2, ys, a + 2.4, fd, unit=u)); a += 2.4
        else:
            pieces.append(Room("bath", b - 2.4, ys, b - 1.2, fd, unit=u)); pieces.append(Room("wc", b - 1.2, ys, b, fd, unit=u)); b -= 2.4
        wet_done = True
    while beds_left > 0 and b - a >= 3.0 + 2.0:
        if k_high:
            pieces.append(Room("bedroom", a, ys, a + 3.2, fd, unit=u)); a += 3.2
        else:
            pieces.append(Room("bedroom", b - 3.2, ys, b, fd, unit=u)); b -= 3.2
        beds_left -= 1
    pieces.append(Room("hall", a, ys, b, fd, unit=u))
    living_front = Room("living", ux0, 0, ux1, ys, unit=u)
    # extra bedrooms take the outer end of the living strip
    while beds_left > 0 and (living_front.x1 - living_front.x0) >= 3.2 + 4.0:
        if k_high:
            rooms.append(Room("bedroom", living_front.x0, 0, living_front.x0 + 3.4, ys, unit=u)); living_front.x0 += 3.4
        else:
            rooms.append(Room("bedroom", living_front.x1 - 3.4, 0, living_front.x1, ys, unit=u)); living_front.x1 -= 3.4
        beds_left -= 1
    if beds_left > 0:
        warnings.append(f"Unit {u}: {beds_left} bedroom(s) did not fit the footprint.")
    extra: list[Room] = []
    if ys > 6.0 + 2.6:  # deep front zone: split into living (front) + family room (open plan)
        extra.append(Room("family", living_front.x0, 6.0, living_front.x1, ys, unit=u))
        living_front.y1 = 6.0
    rooms += pieces + [living_front] + extra
    cors = [Room("corridor", a_, fd, b_, yb, unit=u) for a_, b_ in cor_parts]
    rooms += cors
    # number bedrooms, biggest = master
    beds = sorted([x for x in rooms if x.kind == "bedroom"], key=lambda x: -x.area)
    if beds:
        beds[0].kind = "master"
    others = sorted([x for x in rooms if x.kind == "bedroom"], key=lambda x: (x.y0, x.x0))
    for k, bdr in enumerate(others, start=1):
        bdr.num = k if len(others) > 1 else 0
    fl.rooms += rooms
    # doors
    entry = None
    for c in cors:
        if _door(fl, c, lob, r.entrance_door_w_m, "D1", at_end="mid"):
            entry = c
            break
    if entry is None:
        for c in [x for x in rooms if x.kind in ("hall", "kitchen", "living")]:
            if _door(fl, c, lob, r.entrance_door_w_m, "D1", at_end="mid"):
                break
    targets = cors + [x for x in rooms if x.kind == "hall"] + [living_front]
    for rm in rooms:
        if rm.kind in ("living", "hall", "corridor", "kitchen"):
            continue
        w = r.wet_door_w_m if rm.kind in ("bath", "wc") else (0.8 if rm.kind == "storage" else r.room_door_w_m)
        tag = "D3" if rm.kind in ("bath", "wc", "storage") else "D2"
        for t in targets:
            if _door(fl, rm, t, w, tag, at_end="mid"):
                break
