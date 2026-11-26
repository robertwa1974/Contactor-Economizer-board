"""Generate the project symbol library (econ.kicad_sym) and footprint library (econ.pretty).

Pinouts were taken from the TI datasheets:
  TPS1H100-Q1  SLVSCM2D (Dec 2019), PWP HTSSOP-14, version A (ST pin)
  UCC27517     SLUSAY4D (Dec 2014), DBV SOT-23-5
  TPS7B69xx-Q1 SLVSCJ8B (Jan 2015),  DBV SOT-23-5 (no EN pin)
"""
import os
import uuid

from sexpr import Sym as S, dump

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
HIDE = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("hide"), S("yes")]]


def prop(name, value, x, y, hide=False):
    return [S("property"), name, value, [S("at"), x, y, 0], HIDE if hide else FONT]


def pin(etype, num, name, x, y, ang, length=2.54, hidden=False):
    p = [S("pin"), S(etype), S("line"), [S("at"), x, y, ang], [S("length"), length]]
    if hidden:
        p.append([S("hide"), S("yes")])
    p += [[S("name"), name, FONT], [S("number"), str(num), FONT]]
    return p


def symbol(name, ref, value, footprint, datasheet, desc, w, h, pins):
    """Rectangle body of half-width w, half-height h; pins given as (etype,num,name,side,offset)."""
    body = [S("rectangle"), [S("start"), -w, h], [S("end"), w, -h],
            [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]],
            [S("fill"), [S("type"), S("background")]]]
    plist = []
    for etype, num, pname, side, off in pins:
        if side == "L":
            plist.append(pin(etype, num, pname, -w - 2.54, off, 0))
        elif side == "R":
            plist.append(pin(etype, num, pname, w + 2.54, off, 180))
        elif side == "B":
            plist.append(pin(etype, num, pname, off, -h - 2.54, 90))
        elif side == "T":
            plist.append(pin(etype, num, pname, off, h + 2.54, 270))
    return [S("symbol"), name,
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            prop("Reference", ref, 0, h + 1.27),
            prop("Value", value, 0, -h - 1.27 - (2.54 if any(p[3] == "B" for p in pins) else 0)),
            prop("Footprint", footprint, 0, 0, True),
            prop("Datasheet", datasheet, 0, 0, True),
            prop("Description", desc, 0, 0, True),
            [S("symbol"), f"{name}_0_1", body],
            [S("symbol"), f"{name}_1_1", *plist]]


HTSSOP = "Package_SO:Texas_HTSSOP-14-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask3.155x3.255mm_ThermalVias"

SYMBOLS = [
    symbol("TPS1H100A-Q1", "U", "TPS1H100AQPWPRQ1", HTSSOP,
           "https://www.ti.com/lit/ds/symlink/tps1h100-q1.pdf",
           "40 V 100 mOhm smart high-side switch, adjustable current limit, ST status (version A)",
           10.16, 10.16, [
               ("power_in", 8, "VS", "L", 7.62), ("power_in", 9, "VS", "L", 5.08), ("power_in", 10, "VS", "L", 2.54),
               ("input", 3, "IN", "L", -2.54), ("input", 12, "DIAG_EN", "L", -5.08), ("passive", 13, "CL", "L", -7.62),
               ("passive", 5, "OUT", "R", 7.62), ("passive", 6, "OUT", "R", 5.08), ("passive", 7, "OUT", "R", 2.54),
               ("open_collector", 14, "ST", "R", -2.54),
               ("no_connect", 1, "NC", "R", -5.08), ("no_connect", 4, "NC", "R", -7.62),
               ("no_connect", 11, "NC", "T", 0),
               ("power_in", 2, "GND", "B", -2.54), ("passive", 15, "EP", "B", 2.54),
           ]),
    symbol("UCC27517", "U", "UCC27517DBVR", "Package_TO_SOT_SMD:SOT-23-5",
           "https://www.ti.com/lit/ds/symlink/ucc27517.pdf",
           "4 A/4 A single-channel low-side gate driver, IN+/IN-, SOT-23-5",
           7.62, 5.08, [
               ("power_in", 1, "VDD", "T", 0),
               ("input", 3, "IN+", "L", 2.54), ("input", 4, "IN-", "L", -2.54),
               ("output", 5, "OUT", "R", 0),
               ("power_in", 2, "GND", "B", 0),
           ]),
    symbol("TPS7B6950-Q1", "U", "TPS7B6950QDBVRQ1", "Package_TO_SOT_SMD:SOT-23-5",
           "https://www.ti.com/lit/ds/symlink/tps7b69-q1.pdf",
           "40 V input, 5 V 150 mA automotive LDO, SOT-23-5 (no enable)",
           7.62, 5.08, [
               ("power_in", 1, "IN", "L", 2.54),
               ("power_out", 5, "OUT", "R", 2.54),
               ("no_connect", 2, "NC", "R", -2.54),
               ("power_in", 3, "GND", "B", -1.27), ("power_in", 4, "GND", "B", 1.27),
           ]),
]


def write_symbols():
    lib = [S("kicad_symbol_lib"), [S("version"), 20241209], [S("generator"), "econ_gen"],
           [S("generator_version"), "1.0"], *SYMBOLS]
    with open(os.path.join(HERE, "econ.kicad_sym"), "w", encoding="utf-8") as f:
        f.write(dump(lib) + "\n")


def kelvin_2512():
    """2512 resistor with Kelvin sense pads at the inner edges of the current pads.

    Pads 1/4 carry current; 2/3 are sense taps (net-tied to 1/4 via net_tie_pad_groups),
    matching the Device:R_Shunt symbol (1=I+, 2=S+, 3=S-, 4=I-).
    Current pads follow the IPC 2512 land (3.35 x 1.4 mm at +/-3.15 mm, here enlarged
    for 1 W dissipation); the sense pads are small tabs tucked against the inner edge.
    """
    def pad(num, x, y, w, h, shape="roundrect"):
        p = [S("pad"), str(num), S("smd"), S(shape), [S("at"), x, y], [S("size"), w, h],
             [S("layers"), "F.Cu", "F.Paste", "F.Mask"]]
        if shape == "roundrect":
            p.append([S("roundrect_rratio"), 0.15])
        p.append([S("uuid"), str(uuid.uuid4())])
        return p

    def sense(num, x):
        # Sense tab: no paste (stays a copper tap), touches the inner edge of the current pad.
        return [S("pad"), str(num), S("smd"), S("rect"), [S("at"), x, 2.1], [S("size"), 0.6, 0.8],
                [S("layers"), "F.Cu", "F.Mask"], [S("uuid"), str(uuid.uuid4())]]

    def line(x1, y1, x2, y2, layer, w=0.12):
        return [S("fp_line"), [S("start"), x1, y1], [S("end"), x2, y2],
                [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("layer"), layer],
                [S("uuid"), str(uuid.uuid4())]]

    fp = [S("footprint"), "R_2512_Kelvin", [S("version"), 20241229], [S("generator"), "econ_gen"],
          [S("layer"), "F.Cu"],
          [S("descr"), "2512 shunt resistor with Kelvin sense tabs on the inner pad edges (1=I+,2=S+,3=S-,4=I-)"],
          [S("tags"), "resistor shunt kelvin 2512"],
          [S("property"), "Reference", "REF**", [S("at"), 0, -2.9, 0], [S("layer"), "F.SilkS"],
           [S("uuid"), str(uuid.uuid4())], [S("effects"), [S("font"), [S("size"), 1, 1], [S("thickness"), 0.15]]]],
          [S("property"), "Value", "R_2512_Kelvin", [S("at"), 0, 3.4, 0], [S("layer"), "F.Fab"],
           [S("uuid"), str(uuid.uuid4())], [S("effects"), [S("font"), [S("size"), 1, 1], [S("thickness"), 0.15]]]],
          [S("attr"), S("smd")],
          [S("net_tie_pad_groups"), "1,2", "4,3"],
          line(-3.2, -1.6, 3.2, -1.6, "F.Fab", 0.1), line(3.2, -1.6, 3.2, 1.6, "F.Fab", 0.1),
          line(3.2, 1.6, -3.2, 1.6, "F.Fab", 0.1), line(-3.2, 1.6, -3.2, -1.6, "F.Fab", 0.1),
          line(-1.6, -1.71, 1.6, -1.71, "F.SilkS"), line(-1.2, 2.66, 1.2, 2.66, "F.SilkS"),
          line(-4.3, -2.0, 4.3, -2.0, "F.CrtYd", 0.05), line(4.3, -2.0, 4.3, 2.75, "F.CrtYd", 0.05),
          line(4.3, 2.75, -4.3, 2.75, "F.CrtYd", 0.05), line(-4.3, 2.75, -4.3, -2.0, "F.CrtYd", 0.05),
          pad(1, -3.1, 0, 1.9, 3.5), pad(4, 3.1, 0, 1.9, 3.5),
          sense(2, -2.45), sense(3, 2.45),
          [S("model"), "${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_2512_6332Metric.step",
           [S("offset"), [S("xyz"), 0, 0, 0]], [S("scale"), [S("xyz"), 1, 1, 1]], [S("rotate"), [S("xyz"), 0, 0, 0]]]]
    d = os.path.join(HERE, "econ.pretty")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "R_2512_Kelvin.kicad_mod"), "w", encoding="utf-8") as f:
        f.write(dump(fp) + "\n")


def edge_headers(cut_x=4.5):
    """Right-angle 1x3/1x5 headers whose pins overhang the board edge (rev B, J2/J3).

    Copies of the KiCad library footprints with the silkscreen over the overhanging pins removed
    (local +x points off the board), so silkscreen never runs past the board edge.
    """
    from sexpr import parse
    src = r"C:\Program Files\KiCad\10.0\share\kicad\footprints\Connector_PinHeader_2.54mm.pretty"
    for n in (3, 5):
        name = f"PinHeader_1x{n:02d}_P2.54mm_Horizontal"
        with open(os.path.join(src, name + ".kicad_mod"), encoding="utf-8") as f:
            fp = parse(f.read())

        def beyond(item):
            if not (isinstance(item, list) and item and str(item[0]) in ("fp_line", "fp_rect", "fp_poly")):
                return False
            layer = [x for x in item if isinstance(x, list) and str(x[0]) == "layer"]
            if not layer or layer[0][1] != "F.SilkS":
                return False
            xs = [float(x[1]) for x in item if isinstance(x, list) and str(x[0]) in ("start", "end")]
            return any(x > cut_x for x in xs)

        fp = [x for x in fp if not beyond(x)]
        fp[1] = name + "_Edge"
        with open(os.path.join(HERE, "econ.pretty", name + "_Edge.kicad_mod"), "w", encoding="utf-8") as f:
            f.write(dump(fp) + "\n")


def write_lib_tables():
    with open(os.path.join(HERE, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "econ")(type "KiCad")(uri "${KIPRJMOD}/econ.kicad_sym")(options "")(descr "Contactor economizer parts"))\n)\n')
    with open(os.path.join(HERE, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "econ")(type "KiCad")(uri "${KIPRJMOD}/econ.pretty")(options "")(descr "Contactor economizer footprints"))\n)\n')


if __name__ == "__main__":
    write_symbols()
    kelvin_2512()
    edge_headers()
    write_lib_tables()
    print("wrote econ.kicad_sym, econ.pretty (Kelvin shunt, edge headers), lib tables")
