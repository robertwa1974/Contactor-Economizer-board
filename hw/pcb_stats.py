import pcbnew, collections
b = pcbnew.LoadBoard("econ.kicad_pcb")
w = collections.defaultdict(list)
vias = collections.Counter()
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        vias[t.GetNetname()] += 1
        continue
    w[t.GetNetname()].append((pcbnew.ToMM(t.GetWidth()), pcbnew.ToMM(t.GetLength())))
for n in ["+12V_IN", "VBB", "COIL1_P", "COIL1_N", "COIL2_P", "COIL2_N", "NODE_X_1", "NODE_X_2", "GND", "ISP_1", "ISN_1"]:
    ws = w.get(n, [])
    thin = sum(l for wd, l in ws if wd < 0.79)
    print(f"{n:<9} segs={len(ws):3} minW={min((x for x,_ in ws), default=0):.3f} len={sum(l for _,l in ws):6.1f}mm thin(<0.8)={thin:5.1f}mm vias={vias[n]}")
print("total vias", sum(vias.values()))
lay = collections.Counter()
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA":
        lay[t.GetLayerName()] += pcbnew.ToMM(t.GetLength())
print("track length by layer:", {k: round(v) for k, v in lay.items()})
for z in b.Zones():
    a = 0.0
    fp = z.GetFilledPolysList(z.GetLayer())
    a = fp.Area() / 1e12
    print(f"zone {z.GetNetname()} {b.GetLayerName(z.GetLayer())} filled area {a:.0f} mm2 of {76*66}")
