"""Build econ.kicad_pcb from design.py (run with KiCad's python.exe).

Stage "place":  footprints, nets, outline, holes, netclasses -> econ.kicad_pcb + econ.dsn
Stage "finish": import Freerouting's econ.ses, add GND pours on both layers, fill, save.

Floorplan (mm, origin top-left, board 76 x 66):
  J1 centred on the top edge, mating face outward.
  Centre column under J1: reverse-polarity FET, bulk caps, TVS1, LDOs, then the MCU, headers on the bottom edge.
  Channel 1 power stage in the upper-left, its small-signal parts in a grid below; channel 2 is the mirror image.
"""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402
from gen_sch import uid  # noqa: E402  (same deterministic symbol UUIDs -> footprints link to the schematic)

FPDIR = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
PCB = os.path.join(HERE, "econ.kicad_pcb")
PLACED = os.path.join(HERE, "econ_placed.kicad_pcb")   # placement only; "finish" always starts from this
W, H = 76.0, 66.0

POWER_NETS = ["+12V_IN", "VBB", "COIL1_P", "COIL1_N", "COIL2_P", "COIL2_N", "NODE_X_1", "NODE_X_2"]


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


# ---------------------------------------------------------------- placement
# Shared parts (not mirrored): ref -> (x, y, rotation)
SHARED = {
    "J1": (30.5, 9.5, 0),
    "Q9": (38.0, 21.0, 90), "D3": (30.5, 24.0, 90), "R3": (30.5, 28.5, 90),
    "C1": (38.0, 32.0, 0), "C2": (45.5, 24.0, 90), "C3": (45.5, 29.0, 90),
    "D4": (38.0, 39.0, 0),
    "U2": (30.5, 35.0, 0), "C4": (30.5, 31.5, 0), "C5": (30.5, 39.0, 0),
    "U3": (45.5, 35.0, 0), "C7": (45.5, 32.0, 0), "C6": (45.5, 39.0, 0),
    "U1": (38.0, 50.0, 0), "C9": (30.5, 44.5, 0), "C10": (30.5, 47.5, 0), "C11": (30.5, 50.5, 0),
    "R5": (45.6, 45.0, 90), "R6": (45.6, 49.0, 90), "C8": (45.6, 53.0, 90), "D6": (45.6, 57.0, 0),
    "J2": (28.0, 61.0, 90), "J3": (44.0, 61.0, 90),
    "R4": (55.0, 61.5, 0), "D5": (59.0, 61.5, 0),
    "H1": (3.5, 3.5, 0), "H2": (W - 3.5, 3.5, 0), "H3": (3.5, H - 3.5, 0), "H4": (W - 3.5, H - 3.5, 0),
}

# Channel 1 parts by role (refs looked up from design.py order); channel 2 is mirrored about x = W/2.
CH1_POWER = {
    # high side
    "U4": (21.5, 15.0, 0), "D8": (22.5, 6.0, 0), "C13": (21.5, 20.0, 0),
    "R14": (15.0, 13.5, 90), "R15": (15.0, 18.0, 90),
    # low side and sense
    "D1": (12.5, 6.0, 0), "Q1": (9.0, 16.0, 90), "R1": (20.0, 26.0, 0),
    "U8": (8.0, 27.0, 0), "C14": (8.0, 31.0, 0), "R16": (12.5, 25.0, 90), "R17": (4.0, 24.0, 90),
    "U6": (20.0, 33.0, 0), "C15": (25.5, 33.0, 90),
    "R18": (16.0, 37.0, 0), "R19": (20.0, 37.0, 0), "C16": (24.0, 37.0, 0),
}
# Remaining channel-1 small parts go in a grid, in this order (command/kill chain, then status).
GRID_COLS = [6.0, 11.0, 16.0, 21.0, 26.0]
GRID_ROWS = [41.0, 45.2, 49.4, 53.6]


def channel_refs(n):
    return [p["ref"] for p in design.parts if p["block"].startswith(f"Channel {n} ")]


def placements():
    pos = dict(SHARED)
    ch1, ch2 = channel_refs(1), channel_refs(2)
    assert len(ch1) == len(ch2)
    ch1_to_ch2 = dict(zip(ch1, ch2))
    grid = [r for r in ch1 if r not in CH1_POWER]
    cells = [(x, y) for y in GRID_ROWS for x in GRID_COLS]
    assert len(grid) <= len(cells), f"{len(grid)} grid parts > {len(cells)} cells"
    ch1_pos = dict(CH1_POWER)
    for r, (x, y) in zip(grid, cells):
        ch1_pos[r] = (x, y, 0)
    for r, (x, y, rot) in ch1_pos.items():
        pos[r] = (x, y, rot)
        pos[ch1_to_ch2[r]] = (W - x, y, (180 - rot) % 360)
    missing = [p["ref"] for p in design.parts if p["footprint"] and p["ref"] not in pos]
    assert not missing, f"unplaced: {missing}"
    return pos


# ---------------------------------------------------------------- board
def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(HERE, "econ.pretty") if lib == "econ" else os.path.join(FPDIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    assert fp, fpid
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def setup_rules(board):
    ds = board.GetDesignSettings()
    # JLCPCB standard 2-layer capabilities, with margin.
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.5)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.3)
    ds.m_HoleClearance = mm(0.25)
    ds.m_HoleToHoleMin = mm(0.5)
    ns = ds.m_NetSettings
    ns.ClearNetclassPatternAssignments()   # the project file persists between runs
    dflt = ns.GetDefaultNetclass()
    dflt.SetClearance(mm(0.2))
    dflt.SetTrackWidth(mm(0.25))
    dflt.SetViaDiameter(mm(0.6))
    dflt.SetViaDrill(mm(0.3))
    pwr = pcbnew.NETCLASS("Power")
    pwr.SetClearance(mm(0.25))
    pwr.SetTrackWidth(mm(0.8))
    pwr.SetViaDiameter(mm(0.9))
    pwr.SetViaDrill(mm(0.45))
    ns.SetNetclass("Power", pwr)
    for n in POWER_NETS:
        ns.SetNetclassPatternAssignment(n, "Power")
    # GND is routed as 0.4 mm tracks (plus vias); pours on both layers are added afterwards.
    gnd = pcbnew.NETCLASS("Gnd")
    gnd.SetClearance(mm(0.2))
    gnd.SetTrackWidth(mm(0.4))
    gnd.SetViaDiameter(mm(0.7))
    gnd.SetViaDrill(mm(0.35))
    ns.SetNetclass("Gnd", gnd)
    ns.SetNetclassPatternAssignment("GND", "Gnd")
    ns.RecomputeEffectiveNetclasses()


def outline(board):
    r = 2.0  # corner radius
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    k = r * (1 - 0.70710678)
    corners = (((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
               ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r)))
    for s_, m_, e_ in corners:
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(pt(*s_), pt(*m_), pt(*e_))
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(mm(0.1))
        board.Add(a)


def silk(board, text, x, y, size=1.0, layer=None, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if t.GetLayer() == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def add_track(board, a, b, width, net, layer=None):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a); t.SetEnd(b)
    t.SetWidth(mm(width)); t.SetLayer(layer if layer is not None else pcbnew.F_Cu)
    t.SetNet(net); t.SetLocked(True)
    board.Add(t)


def fanout(board, fp, pads, stub=1.3, bar_w=0.8):
    """Join a row of fine-pitch pads of one net into a wide bar just outside the package.

    The TPS1H100 VS (8-10) and OUT (5-7) pins sit on 0.65 mm pitch, too fine for a 0.8 mm power
    track. Each pad gets a 0.35 mm stub outward; the stub ends are joined by a bar_w-wide bar that
    the autorouter (and the current) can use. Tracks are locked so Freerouting keeps them.
    """
    ps = [p for p in fp.Pads() if p.GetNumber() in pads]
    c = fp.GetPosition()
    ends = []
    for p in ps:
        pp = p.GetPosition()
        d = pp - c
        # outward along the axis where the pad is farthest from the centre
        if abs(d.x) >= abs(d.y):
            u = pcbnew.VECTOR2I(1 if d.x > 0 else -1, 0)
        else:
            u = pcbnew.VECTOR2I(0, 1 if d.y > 0 else -1)
        half = max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()) / 2
        e = pcbnew.VECTOR2I(int(pp.x + u.x * (half + mm(stub))), int(pp.y + u.y * (half + mm(stub))))
        add_track(board, pp, e, 0.35, p.GetNet())
        ends.append(e)
    ends.sort(key=lambda v: (v.x, v.y))
    add_track(board, ends[0], ends[-1], bar_w, ps[0].GetNet())


def kilib_desc(lib_id, field="Description"):
    import kilib
    from sexpr import find_all
    for pr in find_all(kilib.get_symbol(lib_id), "property"):
        if pr[1] == field:
            return "" if pr[2] == "~" else pr[2]
    return ""


def place_refs(board):
    """Put each reference at the first clear spot (default, above, below, left, right of courtyard)."""
    def inflate(bb, d):
        bb = pcbnew.BOX2I(bb.GetPosition(), bb.GetSize())
        bb.Inflate(mm(d))
        return bb
    obstacles = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            obstacles.append(inflate(p.GetBoundingBox(), 0.2))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS:
                obstacles.append(inflate(g.GetBoundingBox(), 0.1))
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            obstacles.append(inflate(d.GetBoundingBox(), 0.1))
    edge = pcbnew.BOX2I(pt(0.5, 0.5), pcbnew.VECTOR2I(mm(W - 1), mm(H - 1)))
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.Reference()
        if not ref.IsVisible():
            continue
        ref.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        ref.SetTextThickness(mm(0.12))
        ref.SetTextAngleDegrees(0)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        c = bb.GetCenter()
        hw, hh = bb.GetWidth() // 2, bb.GetHeight() // 2
        cands = [ref.GetPosition()]
        for k in (0.6, 1.6):
            cands += [pcbnew.VECTOR2I(c.x, c.y - hh - mm(k)), pcbnew.VECTOR2I(c.x, c.y + hh + mm(k)),
                      pcbnew.VECTOR2I(c.x - hw - mm(k + 0.8), c.y), pcbnew.VECTOR2I(c.x + hw + mm(k + 0.8), c.y),
                      pcbnew.VECTOR2I(c.x - hw - mm(k), c.y - hh - mm(k)), pcbnew.VECTOR2I(c.x + hw + mm(k), c.y - hh - mm(k)),
                      pcbnew.VECTOR2I(c.x - hw - mm(k), c.y + hh + mm(k)), pcbnew.VECTOR2I(c.x + hw + mm(k), c.y + hh + mm(k))]
        chosen = None
        for p in cands:
            ref.SetPosition(p)
            tb = ref.GetBoundingBox()
            if edge.Contains(tb) and not any(tb.Intersects(o) for o in obstacles):
                chosen = p
                break
        if chosen is None:
            ref.SetPosition(cands[0])
            ref.SetVisible(False)        # no clear spot: reference stays on F.Fab only
            print("hid silkscreen reference", fp.GetReference())
            continue
        obstacles.append(inflate(ref.GetBoundingBox(), 0.1))


def place():
    board = pcbnew.NewBoard(PCB)
    setup_rules(board)
    nets = {}
    for name in design.nets():
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    import kilib
    # KiCad gives every unused pin its own net "unconnected-(REF-PINNAME-PadN)"; mirror that for parity.
    nc_nets = {}
    for p in design.parts:
        if not p["footprint"] or not p["pins"] and p["lib_id"] == "Mechanical:MountingHole":
            continue
        for num, (pname, etype, *_r) in kilib.pins(p["lib_id"]).items():
            if not p["pins"].get(num):
                name = f"unconnected-({p['ref']}-{pname.replace('/', '{slash}')}-Pad{num})"
                ni = pcbnew.NETINFO_ITEM(board, name)
                board.Add(ni)
                nc_nets[(p["ref"], num)] = ni
    pos = placements()
    for p in design.parts:
        if not p["footprint"]:
            continue
        fp = load_fp(p["footprint"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("sym", p["ref"])))
        x, y, rot = pos[p["ref"]]
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = p["pins"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
            elif (p["ref"], pad.GetNumber()) in nc_nets:
                pad.SetNet(nc_nets[(p["ref"], pad.GetNumber())])
        desc = kilib_desc(p["lib_id"])
        fp.SetLibDescription(desc)
        for key, val in (("Description", desc), ("Datasheet", kilib_desc(p["lib_id"], "Datasheet")), ("MPN", p["mpn"]), ("LCSC", p["lcsc"]), ("Notes", p["note"])):
            if val:
                fp.SetField(key, val)
                fp.GetField(key).SetVisible(False)
        if p["ref"].startswith("H"):
            fp.SetExcludedFromBOM(True)
        # Hide value text on the silkscreen; keep references.
        fp.Value().SetVisible(False)
        if p["ref"].startswith("H"):
            fp.Reference().SetVisible(False)
    outline(board)
    for fp in board.GetFootprints():
        if fp.GetValue() == "TPS1H100AQPWPRQ1":
            fanout(board, fp, ("8", "9", "10"))
            fanout(board, fp, ("5", "6", "7"))
    # 0.3 mm thermal vias (JLCPCB standard) in each TPS1H100 exposed pad (pad 15 = GND).
    for fp in [f for f in board.GetFootprints() if f.GetValue() == "TPS1H100AQPWPRQ1"]:
        ep = [p for p in fp.Pads() if p.GetNumber() == "15"][0]
        c = ep.GetPosition()
        for dx in (-0.9, 0, 0.9):
            for dy in (-1.6, -0.55, 0.55, 1.6):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(c.x + mm(dx), c.y + mm(dy)))
                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(nets['GND']); v.SetIsFree(False); v.SetLocked(True)
                board.Add(v)
    # Pin-1 marker on the front; full J1 pinout on the back silkscreen.
    silk(board, "1", 28.6, 15.0, 0.8)
    silk(board, "J1 (pin side, view from top)", 38, 20.0, 1.0, pcbnew.B_SilkS)
    silk(board, "row 1-6:  C1+  CMD1  +12V  GND  CMD2  C2+", 38, 22.0, 1.0, pcbnew.B_SilkS)
    silk(board, "row 7-12: C1-  STA1  +12V  GND  STA2  C2-", 38, 24.0, 1.0, pcbnew.B_SilkS)
    silk(board, "Two-channel contactor economizer rev A", 38, 45.0, 1.0, pcbnew.B_SilkS)
    silk(board, "SWD 3V3 IO CK RST GND", 33.1, 64.2, 0.8)
    silk(board, "UART TX RX GND", 46.5, 64.2, 0.8)
    place_refs(board)
    board.BuildConnectivity()
    pcbnew.SaveBoard(PLACED, board)
    pcbnew.SaveBoard(PCB, board)
    dsn = os.path.join(HERE, "econ.dsn")
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    print("placed", len(pos), "parts; DSN export", ok)


def pour(board, net, layer, inset=0.4):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    o = z.Outline()
    o.NewOutline()
    for x, y in ((inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)):
        o.Append(mm(x), mm(y))
    z.SetAssignedPriority(0)
    board.Add(z)
    return z


def stitch(board, gnd, zones, pitch=3.0, r_check=0.36):
    """Drop GND vias on a grid wherever both layers' GND fill fully contain the via.

    Fills are first computed with island removal off, so islands cut off by tracks get a via
    to the other layer and survive the final fill. The fill already keeps zone clearance from
    other nets, so a via inside both fills cannot violate clearance.
    """
    for z in zones:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    fills = [z.GetFilledPolysList(z.GetLayer()) for z in zones]
    keep_out = []   # (x, y, radius) in nm: pads and existing vias
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            keep_out.append((bb.GetCenter().x, bb.GetCenter().y,
                             max(bb.GetWidth(), bb.GetHeight()) / 2 + mm(0.9)))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            keep_out.append((t.GetPosition().x, t.GetPosition().y, mm(1.2)))
    ring = [(0, 0)] + [(r_check * c, r_check * s) for c, s in
                       ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071),
                        (0.7071, -0.7071), (-0.7071, -0.7071))]
    added = 0
    y = 1.5
    while y < H - 1.0:
        x = 1.5
        while x < W - 1.0:
            cx, cy = mm(x), mm(y)
            ok = all(all(f.Contains(pcbnew.VECTOR2I(cx + mm(dx), cy + mm(dy))) for dx, dy in ring) for f in fills)
            if ok and all((cx - kx) ** 2 + (cy - ky) ** 2 > kr ** 2 for kx, ky, kr in keep_out):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(cx, cy))
                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                board.Add(v)
                keep_out.append((cx, cy, mm(1.2)))
                added += 1
            x += pitch
        y += pitch
    for z in zones:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    return added


def finish():
    board = pcbnew.LoadBoard(PLACED)
    ses = os.path.join(HERE, "econ.ses")
    if os.path.exists(ses):
        print("SES import", pcbnew.ImportSpecctraSES(board, ses))
    gnd = board.FindNet("GND")
    # Freerouting occasionally necks down to 0.125 mm for a fraction of a mm at a pad; widen to 0.15.
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < mm(0.15):
            t.SetWidth(mm(0.15))
    # Solid (not thermal-relief) pour connection on pads that carry coil current to GND.
    solid = {"Q1": "3", "Q2": "3", "U4": "15", "U5": "15", "C1": "2", "C2": "2", "D4": "2"}
    for fp in board.GetFootprints():
        if fp.GetReference() in solid:
            for p in fp.Pads():
                if p.GetNumber() == solid[fp.GetReference()]:
                    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    zones = [pour(board, gnd, pcbnew.B_Cu), pour(board, gnd, pcbnew.F_Cu)]
    n = stitch(board, gnd, zones)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("stitching vias", n)
    pcbnew.SaveBoard(PCB, board)
    print("tracks", len(board.GetTracks()), "zones filled")


if __name__ == "__main__":
    {"place": place, "finish": finish}[sys.argv[1]]()
