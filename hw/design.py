"""Contactor economizer: single source of truth for parts and connectivity.

gen_sch.py draws the KiCad schematic from this; gen_pcb.py builds the board from it.
Each part: ref, lib_id, value, footprint, pin->net map, plus BOM fields and a block name
(the schematic groups parts by block).

Changes from handoff.md section 6 are marked "CHANGE:" and listed in DESIGN_NOTES.md.
"""
from collections import OrderedDict

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_R1206 = "Resistor_SMD:R_1206_3216Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
FP_TO252 = "Package_TO_SOT_SMD:TO-252-2"
FP_SMA = "Diode_SMD:D_SMA"
FP_SMB = "Diode_SMD:D_SMB"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_HTSSOP = "Package_SO:Texas_HTSSOP-14-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask3.155x3.255mm"  # vias added by gen_pcb (0.3 mm)

parts = []          # list of dicts, in schematic order
_counters = {}


# Refs kept from handoff.md so the docs and the board agree.
RESERVED = {"U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "Q1", "Q2", "Q9",
            "D1", "D2", "R1", "R2", "J1"}


def _next_ref(prefix):
    while True:
        _counters[prefix] = _counters.get(prefix, 0) + 1
        ref = f"{prefix}{_counters[prefix]}"
        if ref not in RESERVED:
            return ref


def part(prefix, lib_id, value, footprint, pins, block, mpn="", lcsc="", note="", ref=None, dnp=False):
    p = dict(ref=ref or _next_ref(prefix), lib_id=lib_id, value=value, footprint=footprint,
             pins={str(k): v for k, v in pins.items()}, block=block, mpn=mpn, lcsc=lcsc, note=note, dnp=dnp)
    parts.append(p)
    return p


def R(value, a, b, block, fp=FP_R0603, note=""):
    return part("R", "Device:R", value, fp, {1: a, 2: b}, block, note=note)


def C(value, a, b, block, fp=FP_C0603, note=""):
    return part("C", "Device:C", value, fp, {1: a, 2: b}, block, note=note)


# --------------------------------------------------------------------------- power
B = "Power input"
part("J", "Connector_Generic:Conn_02x06_Top_Bottom", "Micro-Fit 3.0 2x6",
     "Connector_Molex:Molex_Micro-Fit_3.0_43045-1200_2x06_P3.00mm_Horizontal",
     # CHANGE: 12-pin (was 10) so +12V and GND each get two 5 A contacts.
     # Arranged in columns (pad n above pad n+6) so the board is mirror-symmetric:
     # ch1 coil | ch1 cmd/stat | +12V | GND | ch2 cmd/stat | ch2 coil
     {1: "COIL1_P", 7: "COIL1_N", 2: "CMD_1", 8: "STAT_1", 3: "+12V_IN", 9: "+12V_IN",
      4: "GND", 10: "GND", 5: "CMD_2", 11: "STAT_2", 6: "COIL2_P", 12: "COIL2_N"},
     B, mpn="Molex 43045-1200", note="Not at LCSC: buy from Digi-Key/Mouser, hand-solder", ref="J1")
part("Q", "Transistor_FET:Q_PMOS_GDS", "AOD4185", FP_TO252,
     {1: "Q_REV_G", 2: "+12V_IN", 3: "VBB"}, B, mpn="AOD4185", lcsc="C400894",
     note="Reverse-polarity P-FET: drain = input, source = VBB", ref="Q9")
R("10k", "Q_REV_G", "GND", B)
part("D", "Device:D_Zener", "15V", "Diode_SMD:D_SOD-123", {1: "VBB", 2: "Q_REV_G"}, B,
     mpn="MMSZ5245B (15 V)", note="Q9 gate-source clamp")
part("D", "Device:D_Zener", "SMBJ24A", FP_SMB, {1: "VBB", 2: "GND"}, B,
     mpn="SMBJ24A", lcsc="C224017", note="TVS1 load-dump clamp (unidirectional)")
part("C", "Device:C_Polarized", "47u 50V", "Capacitor_SMD:CP_Elec_6.3x7.7", {1: "VBB", 2: "GND"}, B,
     note="Bulk, damps harness inductance")
C("10u 50V", "VBB", "GND", B, FP_C1206)
C("100n 50V", "VBB", "GND", B)
part("#FLG", "power:PWR_FLAG", "PWR_FLAG", "", {1: "VBB"}, B, ref="#FLG01")
part("#FLG", "power:PWR_FLAG", "PWR_FLAG", "", {1: "GND"}, B, ref="#FLG02")

B = "Logic supplies"
part("U", "econ:TPS7B6950-Q1", "TPS7B6950QDBVRQ1", FP_SOT235,
     {1: "VBB", 2: None, 3: "GND", 4: "GND", 5: "+5V"}, B, mpn="TPS7B6950QDBVRQ1", lcsc="C132202", ref="U2")
C("1u 50V", "VBB", "GND", B, FP_C0805, note="LDO input")
C("10u 16V", "+5V", "GND", B, FP_C0805, note="LDO output, needs >=2.2 uF effective")
part("U", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", FP_SOT235,
     {1: "+5V", 2: "GND", 3: "+5V", 4: None, 5: "+3V3"}, B, mpn="AP2112K-3.3TRG1", lcsc="C51118", ref="U3")
C("1u", "+5V", "GND", B)
C("1u", "+3V3", "GND", B)
R("1k", "+3V3", "LED_PWR", B)
part("D", "Device:LED", "green", FP_LED, {1: "GND", 2: "LED_PWR"}, B, note="Power LED")

B = "Battery sense"
R("100k", "VBB", "VBAT_SENSE", B)
# CHANGE: 15k (was 22k): full scale 25.3 V instead of 18.3 V, plus a BAT54S clamp.
R("15k", "VBAT_SENSE", "GND", B)
C("100n", "VBAT_SENSE", "GND", B)
part("D", "Diode:BAT54S", "BAT54S", FP_SOT23, {1: "GND", 2: "+3V3", 3: "VBAT_SENSE"}, B,
     mpn="BAT54S", lcsc="C171786")

# --------------------------------------------------------------------------- MCU
B = "MCU"
part("U", "MCU_ST_STM32G0:STM32G031K8Tx", "STM32G031K8T6", "Package_QFP:LQFP-32_7x7mm_P0.8mm",
     {4: "+3V3", 5: "GND", 6: "NRST",
      7: "ISENSE_1", 8: "ISENSE_2", 9: "UART_TX", 10: "UART_RX", 11: "VBAT_SENSE",
      13: "PWM_1", 14: "PWM_2", 15: "CMD_SENSE_1", 16: "CMD_SENSE_2",
      28: "KILL_1", 29: "KILL_2", 30: "HS_ST_1", 31: "HS_ST_2",
      22: "STATUS_1", 23: "STATUS_2", 24: "SWDIO", 25: "SWCLK",
      1: None, 2: None, 3: None, 12: None, 17: None, 18: None, 20: None, 26: None, 27: None, 32: None},
     B, mpn="STM32G031K8T6", lcsc="C432203", ref="U1",
     note="Pin 22 = PA11, pin 23 = PA12 (default, no remap)")
C("100n", "+3V3", "GND", B)
C("4.7u", "+3V3", "GND", B)
C("100n", "NRST", "GND", B)
part("J", "Connector_Generic:Conn_01x05", "SWD", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
     {1: "+3V3", 2: "SWDIO", 3: "SWCLK", 4: "NRST", 5: "GND"}, B, note="ST-Link: 3V3 SWDIO SWCLK NRST GND")
part("J", "Connector_Generic:Conn_01x03", "UART", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {1: "UART_TX", 2: "UART_RX", 3: "GND"}, B, note="3.3 V USB-serial: board TX, board RX, GND")

# --------------------------------------------------------------------------- per channel
for n in (1, 2):
    s = f"_{n}"
    B = f"Channel {n} command / kill"
    # CHANGE: 1206 for the 2.2k pull-up (66 mW at 12 V, 116 mW at 16 V).
    R("2.2k", "VBB", "CMD" + s, B, FP_R1206, note="Pull-up for VCU low-side output")
    C("10n 50V", "CMD" + s, "GND", B, note="Harness noise filter")
    R("10k", "CMD" + s, "QIN_G" + s, B)
    R("10k", "QIN_G" + s, "GND", B)
    part("Q", "Transistor_FET:2N7002", "2N7002", FP_SOT23, {1: "QIN_G" + s, 2: "GND", 3: "EN" + s}, B,
         mpn="2N7002", lcsc="C8545", note="Inverts command: VCU low -> EN high")
    R("10k", "+5V", "EN" + s, B)
    # CHANGE: 15k/10k (was 33k/10k): idle reads ~4 V (clamped) instead of a marginal 2.4 V.
    R("15k", "CMD" + s, "CMD_SENSE" + s, B)
    R("10k", "CMD_SENSE" + s, "GND", B)
    part("D", "Diode:BAT54S", "BAT54S", FP_SOT23, {1: "GND", 2: "+3V3", 3: "CMD_SENSE" + s}, B,
         mpn="BAT54S", lcsc="C171786")
    part("Q", "Transistor_FET:2N7002", "2N7002", FP_SOT23, {1: "KILL" + s, 2: "GND", 3: "EN" + s}, B,
         mpn="2N7002", lcsc="C8545", note="MCU can force the high side OFF, never ON")
    R("100k", "KILL" + s, "GND", B)

    B = f"Channel {n} high-side switch"
    part("U", "econ:TPS1H100A-Q1", "TPS1H100AQPWPRQ1", FP_HTSSOP,
         {8: "VBB", 9: "VBB", 10: "VBB", 3: "EN" + s, 12: "+5V", 13: "CL" + s,
          5: f"COIL{n}_P", 6: f"COIL{n}_P", 7: f"COIL{n}_P", 14: "HS_ST" + s,
          1: None, 4: None, 11: None, 2: "GND", 15: "GND"},
         B, mpn="TPS1H100AQPWPRQ1", lcsc="C478465",
         # CHANGE: DIAG_EN tied high; with it low the ST pin is high-impedance.
         note="DIAG_EN high enables ST; CL sets ~6.3 A", ref=f"U{3 + n}")
    R("390", "CL" + s, "GND", B, note="I_lim = 1.233 V x 2000 / R = 6.3 A (+/-14%)")
    R("10k", "+3V3", "HS_ST" + s, B)
    C("100n 50V", "VBB", "GND", B)
    # CHANGE: release clamp across the switch (VS->OUT) instead of COIL+ to GND.
    part("D", "Device:D_Zener", "SMBJ28A", FP_SMB, {1: "VBB", 2: f"COIL{n}_P"}, B,
         mpn="SMBJ28A", note="Release clamp across U4: K=VBB, A=COIL+. Vbr 31-34 V < 50 V internal clamp")

    B = f"Channel {n} low-side PWM and sense"
    part("R", "Device:R_Shunt", "30m 1W", "econ:R_2512_Kelvin",
         {1: f"COIL{n}_N", 2: "ISP" + s, 3: "ISN" + s, 4: "NODE_X" + s}, B,
         mpn="RLP25FECR030", lcsc="C2930482", note="Kelvin: sense pads 2/3 net-tied to 1/4", ref=f"R{n}")
    part("D", "Diode:SS36", "SS36", FP_SMA, {1: "VBB", 2: "NODE_X" + s}, B,
         mpn="SS36", lcsc="C727061", note="Freewheel to VBB", ref=f"D{n}")
    part("Q", "Transistor_FET:Q_NMOS_GDS", "AOD2610E", FP_TO252,
         {1: "GATE" + s, 2: "NODE_X" + s, 3: "GND"}, B, mpn="AOD2610E", lcsc="C282428", ref=f"Q{n}")
    part("U", "econ:UCC27517", "UCC27517DBVR", FP_SOT235,
         {1: "+5V", 2: "GND", 3: "PWM" + s, 4: "GND", 5: "DRV" + s}, B, mpn="UCC27517DBVR", lcsc="C99395", ref=f"U{7 + n}")
    C("1u", "+5V", "GND", B, note="Driver VDD")
    R("10", "DRV" + s, "GATE" + s, B)
    R("100k", "GATE" + s, "GND", B, note="Holds Q off without +5V")
    part("U", "Amplifier_Current:INA240A1PW", "INA240A1PW", "Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
         {1: "GND", 2: "ISP" + s, 3: "ISN" + s, 4: "GND", 5: "+5V", 6: "GND", 7: "GND", 8: "ISENSE_RAW" + s},
         B, mpn="INA240A1PWR", lcsc="C93965", ref=f"U{5 + n}")
    C("100n", "+5V", "GND", B)
    R("10k", "ISENSE_RAW" + s, "ISENSE" + s, B)
    R("20k", "ISENSE" + s, "GND", B)
    C("10n", "ISENSE" + s, "GND", B)

    B = f"Channel {n} status"
    part("Q", "Transistor_FET:2N7002", "2N7002", FP_SOT23, {1: "STATUS" + s, 2: "GND", 3: "STAT" + s}, B,
         mpn="2N7002", lcsc="C8545", note="Open drain to VCU: low = holding, no fault")
    R("100k", "STATUS" + s, "GND", B)
    R("1k", "STATUS" + s, "LED_ST" + s, B)
    part("D", "Device:LED", "green", FP_LED, {1: "GND", 2: "LED_ST" + s}, B)

# --------------------------------------------------------------------------- mechanical
for i in range(4):
    part("H", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {}, "Mechanical")


def nets():
    out = OrderedDict()
    for p in parts:
        for pin, net in p["pins"].items():
            if net:
                out.setdefault(net, []).append((p["ref"], pin))
    return out


def blocks():
    out = OrderedDict()
    for p in parts:
        out.setdefault(p["block"], []).append(p)
    return out


def check():
    refs = [p["ref"] for p in parts]
    dup = {r for r in refs if refs.count(r) > 1}
    assert not dup, f"duplicate refs {dup}"
    for net, conns in nets().items():
        if len(conns) < 2:
            raise AssertionError(f"net {net} has only one connection: {conns}")


check()

if __name__ == "__main__":
    for net, conns in nets().items():
        print(f"{net:<14} {' '.join(r + '.' + p for r, p in conns)}")
    print(len(parts), "parts,", len(nets()), "nets")
