# Handoff: Contactor Economizer Board (GV200-005 and other salvaged HV contactors)

Owner: Rob. Updated 2026-11-25 (Claude Code) for board **rev B** / firmware **v3**.

This file is the designer's reference: the current design, why it is the way it is, and what is still
open. For building, programming and using the board, see [OPERATORS_MANUAL.md](OPERATORS_MANUAL.md).

## 0. Status

- Rev B design complete; no board built yet.
- Firmware v3 compiles cleanly (PlatformIO, STM32duino): flash 51.4 KB of 64 KB, RAM 4.1 KB of 8 KB.
  Not yet run on hardware.
- Schematic: ERC 0 violations; KiCad's netlist matches `hw/design.py` (68 nets, 0 mismatches).
- PCB: DRC with schematic parity, all severities: 0 violations, 0 unconnected, 0 parity issues.
- Fab outputs in `hw/fab/` (Gerber zip, JLCPCB BOM and CPL, 3D renders).

Rev B = rev A plus the IMD provisions (section 10.3): 14-pin J1, IMD stacking socket J4, PTC-fused
12 V feed for the IMD, right-angle J2/J3, HS_ST moved to PB8/PB9, firmware close-inhibit.

## 1. Goal

A two-channel 12 V economizer for HV contactor coils, first for the two Gigavac GV200-005 main
contactors (from a Mercedes B250e / Tesla-built pack) in Rob's son's truck EV conversion:

- Truck: Lexus GS450H inverter and motors, ZombieVerter VCU, 96S lithium pack (about 403 V full,
  350 V nominal).
- Pick-up and hold are both current-regulated, so one board suits coils from about 0.5 to 100 ohm.
  Per-channel profiles live in flash and are set over a 3.3 V serial port.
- Commanded by the ZombieVerter's existing low-side contactor outputs. No VCU firmware change.
- Optional insulation monitor (IMD) board stacked on top. The IMD blocks a CLOSE, never forces an
  OPEN; the VCU decides when to open. The economizer stays a pure 12 V board and works stand-alone.
- Open source (MIT).

## 2. Files and pipeline

| Path | What |
|---|---|
| `src/main.cpp`, `platformio.ini` | Firmware (env `nucleo_g031k8`, same MCU as the board) |
| `hw/design.py` | **Single source of truth**: parts, footprints, MPN/LCSC, pin -> net |
| `hw/gen_lib.py` | Project library: `econ.kicad_sym` (TPS1H100A-Q1, UCC27517, TPS7B6950-Q1), `econ.pretty` (Kelvin 2512 shunt, edge-trimmed right-angle headers) |
| `hw/gen_sch.py` | Draws `econ.kicad_sch` from design.py (do not hand-edit; UUIDs are deterministic) |
| `hw/check_netlist.py` | Compares KiCad's exported netlist with design.py |
| `hw/gen_pcb.py` | `place` (placement, outline, rules, fan-outs, EP vias, silkscreen, DSN) and `finish` (import SES, hole keep-outs, GND pours, stitching vias) |
| `hw/econ.rules` | Freerouting cost settings (bottom layer 3-6x costlier, so it stays mostly a GND plane) |
| `hw/fab.py` | Gerbers + drill (zipped), JLCPCB BOM/CPL, 3D renders |
| `hw/render.py`, `hw/pcb_stats.py` | Review aids |

Pipeline (from `hw/`; KPY = `C:\Program Files\KiCad\10.0\bin\python.exe`):

1. `python gen_lib.py` (only if library parts change), `python gen_sch.py`, ERC
   (`kicad-cli sch erc`), export netlist, `python check_netlist.py`.
2. `KPY gen_pcb.py place` -> `econ_placed.kicad_pcb` + `econ.dsn`.
3. `java -jar freerouting-2.5.0.jar -de econ.dsn -dr econ.rules -do econ.ses -mp 150 --gui.enabled=false`.
   Skip if placement and nets are unchanged (the committed `econ.ses` still applies).
4. `KPY gen_pcb.py finish` (copies `econ.kicad_pro` beside `econ_placed` first so the netclasses and
   rules are not overwritten by KiCad defaults).
5. `kicad-cli pcb drc --severity-all --schematic-parity econ.kicad_pcb`, then `python fab.py`.

## 3. Architecture (per channel)

```
 VBB (+12 V after Q9) ──┬───────────────┬──────────────────┐
                        │               │ K                │ K
               [U4 TPS1H100 high side]  D8 SMBJ28A        D1 SS36 (freewheel)
                 EN from VCU (hardware) │ A                │ A
                        │               │                  │
                     COIL+ ─────────────┘                  │
                        │                                  │
                 ( contactor coil )                        │
                        │                                  │
                     COIL− ──[R1 30 mΩ Kelvin]── NODE_X ───┘
                               │      │           │
                         U6 INA240A1 (gain 20)   Q1 AOD2610E drain (low side, 20 kHz PWM via U8 UCC27517)
                                                  │ source
                                                 GND
```

- The VCU command drives the high-side EN in hardware. Firmware can only force it off (KILL
  transistor), never on. MCU dead or in reset: PWM low, Q1 off, no coil current, contactor open.
- Hold: current recirculates through D1 and the closed high-side switch (~0.5 V), so hold power is
  small. The shunt sits between COIL− and NODE_X, so it sees all coil current including freewheel.
- Release: when U4 opens, the coil drives COIL+ negative until D8 (SMBJ28A, 31-34 V breakdown)
  conducts across the switch. Energy circulates coil -> D1 -> VBB -> D8 -> coil, so the battery does
  not pump the clamp, and D8 never sees VBB (a jump start or load dump can't destroy it). U4's internal
  clamp is 50-70 V, so D8 takes the energy (U4 alone is rated 70 mJ).
- IMD refusal uses the existing hardware: firmware keeps Q1 off (no current path) and asserts KILL.

## 4. Measured contactor data (bench, 2026-11-24/25)

Method: Jesverty SPS-6005V in CC mode with a 12 V limit. Pick-up = lowest current that closes firmly
5/5 times when switched on suddenly; drop-out = current where main-stud continuity stops while slowly
lowering the current.

| Contactor | Source | Coil R (cold) | Pick-up | Drop-out | Notes |
| --- | --- | --- | --- | --- | --- |
| Gigavac GV200-005 | Mercedes B250e pack, main (x2) | 4.8 ohm (DMM); ~5.6 ohm incl. leads | 0.8 A | 0.13 A | Not a catalog part (likely Tesla-spec); 2-wire coil, no series diode; unregulated 12 V = ~28 W |
| LS Electric GER150 | Chevy Bolt | 23 ohm (datasheet 23.5 ±5%) | 0.30 A | 0.10 A | 6.5 W continuous at 12 V. 150 A cont, 500 VDC: too small for the GS450H main path |
| Panasonic AEV14012 (M25) | BMW 330e S-box | 25.9 ohm (catalog 34 ohm) | 0.30 A firm (soft click at 0.20 A) | 0.065 A | ~5.6 W at 12 V. 120 A, 400 V: do NOT use on the 403 V pack |

Decision: GV200-005s are the truck's main contactors. Channel 1 = positive main, channel 2 = negative.

## 5. Circuit (current; design.py is authoritative)

### Power input and supplies
| Item | Parts | Notes |
| --- | --- | --- |
| Reverse polarity | Q9 AOD4185 P-FET (drain = +12V_IN, source = VBB), gate 10k to GND, D3 MMSZ5245B 15 V gate-source clamp | External 5 A fuse in the harness |
| Load dump | D4 SMBJ24A VBB-GND | 12 V systems only (conducts above ~26.7 V) |
| Bulk | C1 47 µF/50 V electrolytic, C2 10 µF/50 V, C3 100 nF | |
| 5 V | U2 TPS7B6950-Q1 (no EN pin; DBV 1 IN, 2 NC, 3/4 GND, 5 OUT), C4 1 µF in, C5 10 µF out | INA240s, UCC27517s, TPS1H100 DIAG_EN/EN pull-ups |
| 3.3 V | U3 AP2112K-3.3, C6/C7 1 µF | MCU; power LED D5 via R4 1k |
| VBAT sense | R5 100k / R6 15k, C8 100 nF, D6 BAT54S clamp | 15/115 V/V; full scale 25.3 V |

### Per channel (channel 1 refs; channel 2 mirrors)
| Function | Parts | Notes |
| --- | --- | --- |
| Command input | 2.2k 1206 pull-up VBB -> CMD, 10 nF, 10k/10k divider -> 2N7002 inverter -> EN (10k pull-up to +5V) | VCU low = close |
| Command sense | 15k/10k divider + BAT54S clamp -> CMD_SENSE (PB0/PB1) | Idle ~4 V clamped; active low |
| Kill | 2N7002 on EN, gate from KILL (PB4/PB5), 100k pull-down | MCU high forces the high side off |
| High side | U4 TPS1H100AQPWPRQ1, DIAG_EN = +5V, CL R14 = 390 Ω, ST 10k pull-up to 3V3 -> HS_ST, 100 nF at VS | I_lim = 1.233 V × 2000 / R = 6.3 A ±14 % (5.4-7.2 A) |
| Release clamp | D8 SMBJ28A, K = VBB, A = COIL+ | Across the switch |
| Low side | Q1 AOD2610E, U8 UCC27517 (IN− to GND), 10 Ω gate resistor, 100k gate pull-down, 1 µF VDD | 20 kHz PWM from TIM3 |
| Freewheel | D1 SS36, NODE_X -> VBB | |
| Current sense | R1 RLP25FECR030 30 mΩ 1 W Kelvin 2512, U6 INA240A1 (REF1/2 to GND), 10k/20k divider, 10 nF | 0.4 V/A at the ADC; full scale 8.25 A |
| Status | 2N7002 open drain -> STAT (J1), 100k gate pull-down; LED D9 via 1k | STAT low = holding, no fault |

### IMD interface (rev B)
| Item | Parts | Notes |
| --- | --- | --- |
| Stacking socket | J4 2×6 female, 2.54 mm, 8.5 mm tall, bottom-left | Pinout in section 6 |
| IMD supply | F1 Bourns MF-MSMF020/60 PTC, VBB -> 12V_PROT | Section 10.3 |
| Logic protection | R37-R42 1k series on IMD_OK, CONT1/2_CLOSED, IMD_INHIBIT, IMD_TX, IMD_RX; U10/U11 SRV05-4 ESD arrays (VP = +5V) on the socket side | |
| IMD_OK default | R43 100k pull-down (MCU side) | Missing or dead IMD = not OK |
| Pass-through | IMD_MHS, IMD_OKHS: J4 pins 11/12 straight to J1 pins 4/11 | Levels set by the IMD |

### MCU pin map (STM32G031K8T6, LQFP-32; matches firmware v3)
| Pin | Port | Net | Function |
| --- | --- | --- | --- |
| 7, 8 | PA0, PA1 | ISENSE_1/2 | ADC |
| 9, 10 | PA2, PA3 | UART_TX/RX | USART2, 115200, J3 (CLI) |
| 11 | PA4 | VBAT_SENSE | ADC |
| 13, 14 | PA6, PA7 | PWM_1/2 | TIM3_CH1/CH2 (PA7_ALT1) |
| 15, 16 | PB0, PB1 | CMD_SENSE_1/2 | Input, active low |
| 28, 29 | PB4, PB5 | KILL_1/2 | Output, high = kill |
| 32, 1 | PB8, PB9 | HS_ST_1/2 | Input, low = high-side fault (polled) |
| 22, 23 | PA11, PA12 | STATUS_1/2 | Output, high = OK (pin 22/23 default mapping, no remap) |
| 24, 25 | PA13, PA14 | SWDIO/SWCLK | J2 |
| 26 | PA15 | IMD_OK | Input, high = OK |
| 18 | PA8 | CONT1_CLOSED | Output |
| 20 | PC6 | CONT2_CLOSED | Output |
| 27 | PB3 | IMD_INHIBIT | Output (held low) |
| 30, 31 | PB6, PB7 | IMD_TX/RX | USART1 AF0, reserved |
| 12, 17, 2, 3 | PA5, PB2, PC14, PC15 | — | Free |

## 6. Connectors

J1 Molex Micro-Fit 3.0 43045-1400 (2×7, right angle; mates with 43025-1400). Pad n is above pad n+7.

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | COIL1+ | 8 | COIL1− |
| 2 | CMD_1 | 9 | STAT_1 |
| 3 | +12V_IN | 10 | +12V_IN |
| 4 | IMD_MHS | 11 | IMD_OKHS |
| 5 | GND | 12 | GND |
| 6 | CMD_2 | 13 | STAT_2 |
| 7 | COIL2+ | 14 | COIL2− |

J4 IMD stacking socket (2×6, 2.54 mm, odd pins in one row):

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | 12V_PROT (via F1) | 2 | GND |
| 3 | IMD_OK (in, 3.3 V, 100k pull-down) | 4 | GND |
| 5 | CONT1_CLOSED (out) | 6 | CONT2_CLOSED (out) |
| 7 | IMD_INHIBIT (out, reserved) | 8 | GND |
| 9 | IMD_TX (economizer TX, reserved) | 10 | IMD_RX (reserved) |
| 11 | IMD_MHS (to J1-4) | 12 | IMD_OKHS (to J1-11) |

J2 SWD (1×5 right angle): 1 3V3, 2 SWDIO, 3 SWCLK, 4 NRST, 5 GND. J3 UART (1×3 right angle):
1 TX, 2 RX, 3 GND. Pin 1 is the right-hand pin of each; pins point off the bottom edge.

## 7. Layout

- 76 × 66 mm, 2 layers, rounded corners, four M3 holes (69 × 59 mm grid), no copper within 4 mm of each
  hole centre on either layer.
- J1 centred on the top edge; channel 1 power stage upper-left, channel 2 mirrored upper-right;
  Q9, bulk caps, TVS and LDOs down the centre; MCU bottom centre; J2/J3 on the bottom edge (right
  angle, pins overhang the edge); IMD socket J4 and its protection parts bottom-left, away from the
  coil loops (which are all in the top corners); F1 beside C2/C3 on VBB.
- Netclasses: Power 0.8 mm (+12V_IN, VBB, COILx_P/N, NODE_X_x), Gnd 0.4 mm plus pours on both layers,
  default 0.25 mm. TPS1H100 VS/OUT pins fanned out with 0.35 mm stubs into 0.8 mm bars.
- 12 × 0.3 mm thermal vias per TPS1H100 exposed pad (GND); grid GND stitching vias; solid pour
  connection on coil-current GND pads.
- Ground: solid planes, not a star. The coil PWM loops and clamp paths stay in the top corners and the
  coil DC return runs along the top to J1's GND pins, so the plane between J4 and J1 carries only
  logic current and the IMD's supply return.
- Stacking: IMD on 15 mm nylon standoffs; tallest economizer parts are J1 (~10 mm, under the IMD's
  required cut-out) and C1 (~8 mm).
- DRC (rev B, all severities, with schematic parity): 0 violations, 0 unconnected, 0 parity issues.
- Routing is Freerouting output (bottom layer 3-6x cost; at 4-8x the rev B board would not fully
  route). `finish` normalises any via whose annular ring is under 0.1 mm.

## 8. Firmware (src/main.cpp v3)

- States: OFF -> PICKUP (PI to pick-up current, may use 100 % duty) -> HOLD (PI to hold current,
  max 95 %); PASS (100 % for self-economized contactors); FAULT (latched until the command is removed).
- 1 kHz loop, 20 kHz PWM on TIM3; feed-forward target × ohms ÷ VBAT plus PI (KP 0.20, KI 2.0,
  integrator ±0.30). Watchdog 100 ms.
- Faults: 0x01 pick-up low; 0x02 overcurrent (auto = max(1.5×pick-up, 3×hold) + 0.5 A, max 6.5 A;
  drives KILL); 0x04 hold low; 0x08 hold high (reported); 0x10 high-side ST low (blanked 20 ms after
  energising, must persist 10 ms); 0x20 not configured; **0x40 IMD inhibit**.
- IMD (v3): global `imd required|optional` setting, default optional. IMD_OK counts as OK after 2 s
  continuously high. Close request with IMD required and not OK -> 0x40, KILL asserted, latched until
  the command drops (no auto-close). IMD_OK low for 20 ms while energised -> warning `W=IMD_LOST`
  only. CONTx_CLOSED = HOLD at ≥ 60 % of hold current (PASS: ≥ 0.05 A), debounced 20 ms both ways.
  STAT is unaffected by warnings; on 0x40 it stays released like any fault.
- Settings (CRC32, STM32duino buffered EEPROM emulation in the last flash page) are format v3; older
  saved settings are discarded and both channels come up unconfigured.
- CLI (115200): `help`, `show`, `presets`, `preset`, `set`, `imd`, `save`, `defaults`, `log`.
  Presets: `unconfigured`, `gv200-005` (2.5 A / 200 ms / 0.30 A / 5.0 Ω), `ger150`, `aev14012`,
  `passthrough`.

## 9. Bring-up plan

1. Nucleo-G031K8: flash, `preset 1 gv200-005`, `save`, ground PB0. Expect PICKUP then HOLD; with no
   coil, FAULT (pick-up low) after 200 ms. Then `imd required`: with PA15 low, a close gives 0x40;
   with PA15 high for > 2 s, it closes.
2. First board: manual sections 4-6 (power-up, flash, bench test with a GV200 and HV disconnected).
   Log hold current (~0.30 A) and supply current (~0.04-0.05 A).
3. Release check: scope COIL+ at release; expect a swing to about −31 to −34 V relative to VBB and
   main-stud continuity gone within ~12 ms.
4. IMD socket: drive J4-3 from 3.3 V through a switch; check 0x40 refusal, the 2 s qualification, the
   warning while closed, and CONTx_CLOSED on J4-5/6.

## 10. Design history

### 10.1 Rev A changes from the original plan
1. Release clamp moved across the switch (SMBJ28A K=VBB, A=COIL+), replacing SMBJ20CA COIL+ to GND,
   which a >22 V VBB event would have destroyed through the closed switch.
2. TPS1H100 DIAG_EN tied to +5V (low makes ST high-impedance).
3. CL resistor 390 Ω (6.3 A).
4. CMD_SENSE divider 15k/10k (33k/10k gave a phantom command near 11 V).
5. VBAT divider 100k/15k plus BAT54S clamp.
6. J1 to 2×6 with doubled +12 V and GND; extra decoupling, gate pull-downs, CMD filter caps, power LED.
7. Firmware: PA7 must be `PA7_ALT1` for TIM3_CH2; strtof replaced (−9.5 KB); HS_ST blanking.

### 10.2 External review (Gemini, 2026-11-25)
- Acted on: mounting-hole copper keep-outs.
- Not real: "COIL_SENSE divider inverted" (no such nets), "INA240 clips at 5.5 A" (missed the 10k/20k
  divider), missing pull-ups/pull-downs (fitted), duplicate C10, silkscreen overlaps.
- Judged unnecessary for the GV200: SS56 freewheel diode, wider coil copper, extra ceramics at D1/Q1.
- Limit: CL minimum 5.4 A, so pick-up setpoints above ~5 A hit the TPS1H100 limit.

### 10.3 Rev B: IMD provisions
- J1 2×6 -> 2×7 (43045-1400) for IMD_MHS/IMD_OKHS pass-through; D8/D11 moved 1.5 mm outward.
- J4 stacking socket (2×6 female, 8.5 mm) with 1k + ESD on the six logic/UART lines, 100k pull-down
  on IMD_OK. Female socket is unkeyed; the IMD board's header position plus the hole pattern means it
  only fits one way.
- J2/J3 right angle on the bottom edge (vertical headers would be under the IMD board). Footprints are
  library copies with the silkscreen over the overhanging pins removed.
- HS_ST moved PB6/PB7 -> PB8/PB9 to free USART1 (PB6 TX / PB7 RX, the only USART1 pins on LQFP-32
  besides PA9/PA10, which are taken by STATUS). HS_ST is polled, not EXTI; no other input shares EXTI
  lines 8/9 (inputs are on lines 0, 1, 8, 9, 15), so interrupts can be added later without conflict.
- F1 PTC: Bourns MF-MSMF020/60 (1812): 60 V, Imax 40 A, Ihold 0.20 A, Itrip 0.40 A, R 0.40-6.0 Ω
  (R1max), trips within 0.15 s at 1.5 A (datasheet p.1). Chosen over the 030 parts, whose 10 A Imax
  is below a dead short on a stiff 12 V supply; voltage rating covers the SMBJ24A clamp (~39 V).
  - Short on the IMD: ~25 A through 0.4 Ω trips it in about a millisecond (I²t scaling), long before
    a 5 A harness fuse opens; the coils keep running.
  - IMD inrush: e.g. 22 µF charged through 0.4 Ω: τ ≈ 9 µs, I²t ≈ 0.004 A²s, against ~0.3 A²s to
    trip at 1.5 A: no nuisance trip, including hot-plugging.
  - Drop at 9 V input: a 1 W IMD draws ~0.11 A; × 6 Ω worst case = 0.7 V, so the IMD sees ≥ 8.3 V.
  - Hold current derates with temperature (roughly 0.15 A in a hot enclosure): keep the IMD ≤ ~1 W.
- Standoffs: 4 × nylon M3 × 15 mm male-female hex plus 4 × nylon M3 × 6 mm screws (or the IMD's
  mounting holes must sit in its LV region with HV clearance). Not on the JLCPCB BOM (not assembled).

## 11. Open items

- [ ] Rob: review the autorouted power routing in KiCad.
- [ ] Assign LCSC numbers left blank (passives, LEDs, SMBJ28A, 15 V zener, 47 µF/50 V, SRV05-4,
      MF-MSMF020/60). Prefer JLCPCB basic parts. Check MF-MSMF020/60 is still recommended for new
      designs (some MF-MSMF models are not); MF-MSMF020/60X is the fallback (slower trip).
- [ ] Check component rotations in JLCPCB's CPL preview (SOT-23, SOT-23-5/6, TO-252).
- [ ] J1, J2, J3, J4 are through-hole: hand-solder (excluded from the CPL).
- [ ] Confirm J1 (43045-1400) height from the Molex drawing for the IMD cut-out.
- [ ] Flash the firmware to a Nucleo-G031K8 and run bring-up step 1.
- [ ] UCC27517 UVLO (4.65 V max) vs the 5 V rail: ~0.25 V margin. Confirm on the bench.
- [ ] Passthrough mode: COIL+ is pulled ~21 V negative for < 1 ms at release while Q1 is on. Check such
      contactors tolerate reverse voltage.
- [ ] Measure GV200 coil inductance; release energy ½LI² is 0.31 J at 2.5 A / 100 mH. SMBJ28A is fine
      for release from hold and from a 2.5 A pick-up; at the 5 A hardware maximum consider SMCJ28A.
- [ ] Confirm AOD2610E RDS(on) at 4.5 V gate.
- [ ] Decide whether the ZombieVerter reads STAT_1/STAT_2 and IMD_OKHS/IMD_MHS.
- [ ] IMD board (separate project): HV taps on the pack side of the contactors with fused leads,
      switched-resistor bridge, HV-side STM32G0, UCC12050 isolated supply, IR155-compatible MHS/OKHS
      outputs; ≤ 1 W from 12V_PROT; 3.3 V logic on J4; cut-out over J1; header reaching the 8.5 mm
      socket across a 15 mm stack.
- [ ] Optional future: drive IMD_INHIBIT (e.g. during DC fast charging) and use the USART1 link.
