# Handoff: Contactor Economizer Board (GV200-005 and other salvaged HV contactors)

Owner: Rob. Handoff written 2026-11-25 from a claude.ai design session, for continuing in Claude Code.

Live design doc (may not be reachable from Claude Code): https://claude.ai/artifact/VjvyEwBQTDrGUeuGKAZBDW
This file is the authoritative, current summary. Where it differs from the doc, this file wins.

## 0. Session 2 update (2026-11-25, Claude Code) — read first

Done:
- Git repo initialised (nothing committed yet). `main.cpp` moved to `src/main.cpp`.
- Firmware compiles cleanly (PlatformIO, STM32duino). Flash 50.5 KB / 64 KB (was 91.5% before the fixes below).
- KiCad 10 schematic generated: `hw/econ.kicad_sch` (+ `hw/econ_schematic.pdf`). ERC: 0 errors, 0 warnings.
  KiCad's exported netlist matches `hw/design.py` exactly (`python hw/check_netlist.py`).
- Pinouts verified from TI datasheets (TPS1H100-Q1 SLVSCM2D, UCC27517 SLUSAY4D, TPS7B69xx-Q1 SLVSCJ8B).

How the hardware files work:
- `hw/design.py` is the single source of truth (parts, footprints, MPN/LCSC, pin->net). Edit it, then run
  `python hw/gen_lib.py` (custom symbols/footprint), `python hw/gen_sch.py`, then ERC and `check_netlist.py`.
  Do not hand-edit `econ.kicad_sch`; it is regenerated (UUIDs are deterministic, so PCB links stay stable).
- `hw/econ.kicad_sym`: TPS1H100A-Q1, UCC27517, TPS7B6950-Q1. `hw/econ.pretty/R_2512_Kelvin`: 2512 shunt with
  Kelvin sense pads tied via `net_tie_pad_groups` (symbol Device:R_Shunt: 1=I+, 2=S+, 3=S-, 4=I-).

Firmware fixes:
- BUG: PA7's first PinMap_TIM entry is TIM1_CH1N, so `setMode(2, ..., PA7)` would never drive TIM3_CH2.
  Now `PA7_ALT1`. (PA6 maps to TIM3_CH1 correctly.)
- `strtof` replaced by a small parser (saved ~9.5 KB; keeps clear of the EEPROM-emulation flash page).
- `validate()` rejects oc < 0 or > 6.5 A. Serial TX buffer 256 B so logging never blocks the 1 kHz loop.
  Removed redundant `-D HAL_ADC_MODULE_ENABLED` (caused redefinition warnings).
- HS_ST is blanked for 20 ms after entering PICKUP/PASS and must persist 10 ms. Reason: with DIAG_EN high the
  TPS1H100 flags open load (<2-10 mA for 700 us); the VCU turns the high side on ~5 ms before Q1 starts, so ST
  is legitimately low at PICKUP entry and would have latched a false F_HS_SWITCH.
- VBAT scale now 15/115 (matches the hardware change below).

Hardware changes from section 6 (all marked `CHANGE:` in design.py):
1. Release clamp moved: SMBJ28A (unidirectional) across each high-side switch, K=VBB, A=COIL+, replacing
   SMBJ20CA COIL+ to GND. Reasons: (a) with the old part, any VBB above ~22 V (jump start, load dump up to
   TVS1's ~39 V) drives TVS2 through the closed switch at the 6.5 A current limit (~140-190 W) and destroys it;
   across the switch it never sees VBB. (b) The release energy now circulates coil -> D1 -> VBB node -> TVS ->
   coil, so the battery no longer pumps energy into the clamp. (c) Release voltage stays similar (~34 V across
   the coil). TPS1H100 internal VDS clamp is 50-70 V and the TVS breaks down at 31-34 V, so the TVS takes the
   energy (TPS1H100 alone is only rated 70 mJ). This also answers the "raise the clamp toward 55 V" item:
   not possible above ~45 V without the switch's own clamp taking over.
2. TPS1H100 DIAG_EN tied to +5V. With DIAG_EN low, ST is high-impedance (datasheet Table 2), so HS_ST would
   never report anything.
3. TPS1H100 CL resistor = 390 ohm -> 1.233 V x 2000 / 390 = 6.3 A (+/-14% = 5.4-7.2 A).
4. TPS7B6950-Q1 has NO enable pin (DBV: 1 IN, 2 NC, 3 GND, 4 GND, 5 OUT); needs >=2.2 uF out (10 uF fitted).
5. CMD_SENSE divider 15k/10k (was 33k/10k). Old divider gave 2.40 V at the pin for an idle 12 V input
   (2.2 V at 11 V) against a ~2.31 V VIH, i.e. a phantom command at low battery. Now ~4 V, BAT54S-clamped.
6. VBAT divider 100k/15k (was 22k; old one hit 3.3 V at 18.3 V) plus a BAT54S clamp.
7. J1 is now Micro-Fit 2x6 (43045-1200): +12V on pins 1+2, GND on 7+8, so simultaneous pick-up on both
   channels does not exceed one contact's rating. Pin map (columns, pad n above pad n+6):
   1 COIL1+, 7 COIL1-; 2 CMD_1, 8 STAT_1; 3 +12V_IN, 9 +12V_IN; 4 GND, 10 GND; 5 CMD_2, 11 STAT_2;
   6 COIL2+, 12 COIL2-.
8. Added: 100k gate pull-down on Q1/Q2; 10 nF on each CMD line; 47 uF/50 V bulk + 10 uF + 100 nF on VBB;
   100 nF at each TPS1H100 VS; power LED; 2.2k CMD pull-ups in 1206 (116 mW at 16 V); SWD header now 5-pin
   with NRST. Q9 gate zener = MMSZ5245B (SOD-123).

Refs: U1 MCU, U2 5 V LDO, U3 3.3 V LDO, U4/U5 TPS1H100, U6/U7 INA240, U8/U9 UCC27517, Q1/Q2 low-side FETs,
Q9 reverse-polarity FET, D1/D2 SS36, R1/R2 shunts, D8/D11 release TVS, D4 TVS1, J1 harness.

### PCB (session 2, later)

Status: `hw/econ.kicad_pcb`, 76 x 66 mm, 2 layers, routed. KiCad DRC with schematic parity, all severities:
0 errors, 0 warnings. Fab outputs in `hw/fab/`: `econ_gerbers_jlcpcb.zip` (Gerbers + Excellon),
`econ_bom_jlcpcb.csv`, `econ_cpl_jlcpcb.csv`, `econ_3d_top.png`, `econ_3d_bottom.png`.

Pipeline (run from `hw/`; KPY = "C:\Program Files\KiCad\10.0\bin\python.exe"):
1. `python gen_sch.py` (after any design.py change), ERC, `check_netlist.py`.
2. `KPY gen_pcb.py place` -> placement, outline, holes, netclasses, locked fan-outs and EP vias,
   `econ_placed.kicad_pcb` + `econ.dsn`.
3. `java -jar freerouting-2.5.0.jar -de econ.dsn -dr econ.rules -do econ.ses -mp 150 --gui.enabled=false`
   (`econ.rules` makes B.Cu 4-8x costlier so the bottom stays a near-solid GND plane). Skip if placement
   and net names are unchanged: the committed `econ.ses` still applies.
4. `KPY gen_pcb.py finish` -> import SES, GND pours on both layers, grid stitching vias, solid GND
   connection on the coil-current pads, fill.
5. `kicad-cli pcb drc --severity-all --schematic-parity econ.kicad_pcb`, then `python fab.py`.
Review aids: `python render.py out.png [layers]`, `KPY pcb_stats.py` (power-net widths, pour area).

Layout decisions:
- J1 centred on the top edge. Its pinout is arranged in columns so the two channels mirror each other
  (see change 7, updated): pads 1/7 COIL1+/COIL1-, 2/8 CMD_1/STAT_1, 3/9 +12V, 4/10 GND, 5/11 CMD_2/STAT_2,
  6/12 COIL2+/COIL2-. Back silkscreen carries this table.
- Channel 1 power stage in the upper-left, channel 2 mirrored upper-right; Q9, bulk caps, TVS1 and LDOs
  down the centre; MCU bottom centre; SWD (5-pin) and UART headers on the bottom edge.
- Netclasses: Power 0.8 mm (+12V_IN, VBB, COILx_P/N, NODE_X_x), Gnd 0.4 mm plus pours, default 0.25 mm.
  The TPS1H100 VS/OUT pins (0.65 mm pitch) are fanned out with 0.35 mm stubs into a 0.8 mm bar.
- Kelvin shunt sense nets (ISP_x/ISN_x) are separate nets from the current path by construction.
- 12 x 0.3 mm thermal vias per TPS1H100 exposed pad; ~150 GND stitching vias. Bottom pour ~85% of the board.
- Drills >= 0.3 mm, track >= 0.15 mm, clearance >= 0.2 mm: inside JLCPCB standard 2-layer rules.
- No copper within 4 mm of each M3 hole centre, both layers (screw head / 7 mm washer cannot bite into GND).

External review (Gemini, 2026-11-25), checked against design.py and the board:
- Acted on: mounting-hole copper keep-outs (above).
- Not real: "COIL_SENSE divider inverted" (no such nets exist); "INA240 clips at 5.5 A" (the 10k/20k
  divider gives 0.4 V/A at the ADC, full scale 8.25 A, and caps the pin at 3.3 V); missing HS_ST
  pull-ups / CMD_SENSE pull-downs (both fitted: 10k); duplicate C10 (C18's text at low resolution; refs
  are unique, DRC parity clean); silkscreen overlaps (DRC clean; the doubled labels are F.Fab text).
- Judged unnecessary for the GV200 (2.5 A pick-up, 0.30 A hold): SS56 instead of SS36 (freewheel loss
  ~0.1 W at hold); wider coil copper (0.8 mm is fine for 2.5 A pulses); extra ceramics at D1/Q1 (0.3 A
  commutating, estimated ringing well under 1 V).
- Limit to keep in mind: CL = 390 ohm gives 5.4 A minimum current limit, so pick-up setpoints above ~5 A
  will hit the TPS1H100's limit (then ST faults). Lower R14/R29 (e.g. 300 ohm, 7.1 A min) only if a
  heavier contactor is ever used; the shunt (1 W) and SS36 would also need a look then.

Before ordering (open):
- [ ] Rob: open in KiCad, review the power routing (autorouted). Hand-tuning that would help: shorten
      VBB from Q9 to U4/U5 VS and D1/D2, widen the COILx paths, check the Q1/Q2 source GND return.
- [ ] Assign LCSC numbers for all passives, LEDs, the SMBJ28A, the 15 V zener and the 47 uF/50 V cap
      (left blank on purpose, not guessed). Prefer JLCPCB basic parts.
- [ ] Check component rotations in JLCPCB's CPL preview (SOT-23/SOT-23-5/TO-252 often need offsets).
- [ ] J1, J2, J3 are through-hole and excluded from the CPL: hand-solder. J1 has no 3D model in the render.
- [ ] Flash the firmware to a Nucleo-G031K8 and run bring-up step 1 (section 10).

## 1. Goal

A two-channel 12 V economizer board for HV contactor coils, first for the two Gigavac GV200-005 main contactors (from a Mercedes B250e / Tesla-built pack) in Rob's son's truck EV conversion:

- Truck: Lexus GS450H inverter and motors, ZombieVerter VCU, 96S lithium pack (about 403 V full, about 350 V nominal).
- Pick-up and hold are both current-regulated, so one board handles coils from about 1 to 100 ohm. Per-channel profiles live in flash and are set over USB serial.
- Commanded by the ZombieVerter's existing low-side contactor outputs. No ZombieVerter firmware change needed.
- Intended to be open-sourced for other builders with salvaged contactors.

## 2. What exists now

| File | Status |
| --- | --- |
| `platformio.ini` | Env `nucleo_g031k8`, Arduino framework (STM32duino), ST-Link upload |
| `src/main.cpp` | Firmware v2, about 510 lines. NOT YET COMPILED (no toolchain was available). Compile first. |
| `handoff.md` | This file |

Not started: KiCad schematic, PCB layout, Gerbers/BOM/CPL for JLCPCB.

## 3. Next steps for Claude Code (suggested order)

1. Create a git repo; put `platformio.ini` and `src/main.cpp` in it.
2. Build the firmware with PlatformIO; fix compile errors (see section 9 for likely trouble spots). Optionally flash to a Nucleo-G031K8 and run bring-up step 1 (section 10).
3. Install KiCad (kicad-cli needed for ERC/DRC and fabrication outputs).
4. Generate the KiCad schematic from section 6 with Python (e.g. via s-expression writing, kiutils, or SKiDL), using the parts in section 7 with correct footprints. Run ERC until clean.
5. Generate a 2-layer PCB (about 50 x 70 mm) with Python placement/routing per the layout rules in section 8. Run DRC with JLCPCB limits until clean.
6. Export Gerbers, drill, BOM and CPL in JLCPCB format; render images for Rob to review.
7. Independent review of the schematic and layout (Rob may also run another model as an auditor).
8. Rob reviews in KiCad and the JLCPCB 3D preview before ordering. Build one prototype first.

## 4. Measured contactor data (bench, 2026-11-24/25)

Method: Jesverty SPS-6005V bench supply in CC mode with voltage limit 12 V; pick-up = lowest current that closes firmly 5/5 times when switched on suddenly; drop-out = current where continuity across the main studs stops while slowly lowering current.

| Contactor | Source | Coil R (cold) | Pick-up | Drop-out | Notes |
| --- | --- | --- | --- | --- | --- |
| Gigavac GV200-005 | Mercedes B250e pack, main (x2) | 4.8 ohm (DMM); ~5.6 ohm incl. supply leads | 0.8 A | 0.13 A | Not a catalog part (likely Tesla-spec); single 2-wire coil, no series diode; unregulated 12 V = ~28 W |
| LS Electric GER150 | Chevy Bolt | 23 ohm (datasheet 23.5 ohm +/-5%) | 0.30 A | 0.10 A | Rated 6.5 W continuous at 12 V, so economizing optional. 150 A cont / 225 A 15 min / 500 VDC max: too small for GS450H main path |
| Panasonic AEV14012 (M25) | BMW 330e S-box | 25.9 ohm (catalog part is 34 ohm) | 0.30 A firm (soft partial click at 0.20 A) | 0.065 A | ~5.6 W at 12 V, economize. 120 A, switching voltage listed 400 V: do NOT use on the 403 V pack |

Decision: GV200-005s are the main contactors for the truck.

## 5. Architecture (per channel)

```
 VBB (+12 V, fused) ──┬──────────────────────────────┐
                      │                              │ cathode
        [U4 smart high-side switch]                 D1 (SS36)
          EN = from VCU command (hardware)           │ anode
                      │                              │
                   COIL+ ──[TVS2 SMBJ20CA bidir to GND]
                      │                              │
                 ( contactor coil )                  │
                      │                              │
                   COIL− ──[Rs1 30 mΩ]── NODE_X ─────┘
                             │   │          │
                      INA240 (Kelvin)    Q1 drain (low-side N-FET, 20 kHz PWM)
                                            │
                                           GND
```

- Freewheel D1 returns to VBB BEFORE the high-side switch (not to COIL+). During hold, current recirculates via D1 and the closed high-side switch (~0.5 V). When the high-side switch opens, COIL+ is pulled about 24–32 V below ground by TVS2 (and the switch's own inductive clamp), so release is fast.
- The VCU command drives the high-side EN in hardware; firmware can only force it OFF (KILL transistor), never ON.
- MCU dead/reset: PWM pins low, Q1 off, both coil ends at +12 V, no current: contactor cannot close (fails open).
- Shunt sits between COIL− and NODE_X so it sees all coil current, including freewheel. INA240 common mode stays 0 to VBB+0.7 V.

## 6. Netlist (channel 1 shown; channel 2 identical with _2 suffix)

Power input (shared)
| From | Part | To | Note |
| --- | --- | --- | --- |
| J1 +12V_IN | Q9 AOD4185 P-FET reverse-polarity stage (gate via 10 k to GND, 15 V zener gate-source clamp) | VBB | External 5 A fuse in harness |
| VBB | TVS1 SMBJ24A to GND | — | Load-dump clamp |
| VBB | U2 TPS7B6950-Q1 (5 V, 40 V in) | +5V | INA240s, UCC27517s; input/output caps per datasheet |
| +5V | U3 AP2112K-3.3 | +3V3 | MCU |
| VBB | 100 k / 22 k divider to GND, 100 nF | VBAT_SENSE | 0.180 V/V |

Command input (per channel)
| From | Part | To | Note |
| --- | --- | --- | --- |
| VBB | 2.2 k pull-up | CMD_1 (J1) | VCU low-side output sinks ~5.5 mA |
| CMD_1 | 10 k / 10 k divider | Q_IN1 gate (2N7002) | Idle 6 V = Q_IN1 on; VCU low = off |
| Q_IN1 drain | 10 k pull-up to +5V | EN_1 | EN_1 high only when VCU commands close; Q_IN1 source to GND |
| CMD_1 | 33 k / 10 k divider + BAT54S clamp to +3V3/GND | CMD_SENSE_1 | Active low at MCU |
| KILL_1 (MCU) | 100 k pull-down, Q_K1 gate (2N7002) | Q_K1 drain on EN_1 | MCU high forces high-side off |

Coil drive (per channel)
| From | Part | To | Note |
| --- | --- | --- | --- |
| VBB | U4 TPS1H100AQPWPRQ1, EN = EN_1 | COIL1+ (J1) | Set external current limit ~6.5 A via CL resistor (datasheet formula); internal limit 7–13 A |
| COIL1+ | TVS2 SMBJ20CA bidirectional to GND | — | Release clamp |
| COIL1− (J1) | Rs1 30 mΩ 1% 1 W 2512 | NODE_X1 | |
| NODE_X1 | D1 SS36 (anode), cathode to VBB | VBB | |
| NODE_X1 | Q1 AOD2610E drain; source GND | — | |
| PWM_1 (MCU) | U8 UCC27517 on +5V, 10 Ω gate resistor | Q1 gate | Driver input has internal pull-down |
| U4 ST pin | 10 k pull-up to +3V3 | HS_ST_1 | Low = high-side fault |

Current sense (per channel)
| From | Part | To | Note |
| --- | --- | --- | --- |
| Rs1 (Kelvin) | U6 INA240A1 (gain 20) on +5V, REF1/REF2 to GND | ISENSE_RAW_1 | 0.6 V/A |
| ISENSE_RAW_1 | 10 k / 20 k divider, 10 nF to GND | ISENSE_1 | 0.4 V/A at ADC; 5 A = 2.0 V; saturates ~8 A |

Status output (per channel)
| From | Part | To | Note |
| --- | --- | --- | --- |
| STATUS_1 (MCU) | Q_S1 gate (2N7002), 100 k pull-down | Q_S1 drain to STAT_1 (J1) | Pulled low = holding, no fault |
| STATUS_1 (MCU) | 1 k + LED to GND | — | Lit while holding |

Connectors
- J1 Molex Micro-Fit 3.0, 10-pin right angle (43045-1000): +12V_IN, GND, CMD_1, CMD_2, STAT_1, STAT_2, COIL1+, COIL1−, COIL2+, COIL2−.
- 4-pin SWD header (3V3, SWDIO, SWCLK, GND); 3-pin UART header (TX, RX, GND).
- MCU support: decoupling per STM32G031 datasheet, NRST pull-up + 100 nF, BOOT0 handling per datasheet (PA14-BOOT0 shared with SWCLK on G0; check option bytes).

MCU pin map (STM32G031K8T6, LQFP-32; matches firmware)
| Pin | Net | Function |
| --- | --- | --- |
| PA0 | ISENSE_1 | ADC |
| PA1 | ISENSE_2 | ADC |
| PA4 | VBAT_SENSE | ADC |
| PA6 | PWM_1 | TIM3_CH1, 20 kHz |
| PA7 | PWM_2 | TIM3_CH2, 20 kHz |
| PB0 | CMD_SENSE_1 | input, active low |
| PB1 | CMD_SENSE_2 | input, active low |
| PB4 | KILL_1 | output, high = kill |
| PB5 | KILL_2 | output, high = kill |
| PB6 | HS_ST_1 | input, low = fault |
| PB7 | HS_ST_2 | input, low = fault |
| PA11 | STATUS_1 | output, high = OK |
| PA12 | STATUS_2 | output, high = OK |
| PA2 / PA3 | UART TX / RX | 115200 debug + config CLI |
| PA13 / PA14 | SWDIO / SWCLK | programming |

## 7. BOM (locked to JLCPCB/LCSC numbers, checked 2026-11-25; re-check stock before ordering)

| Ref | Part (MPN) | LCSC # | Qty | Note |
| --- | --- | --- | --- | --- |
| U1 | STM32G031K8T6, LQFP-32 | C432203 | 1 | Stock was thin (45 pcs); fallback STM32G030K8T6 C431631 (verify pin compatibility) |
| U2 | TPS7B6950QDBVRQ1, 5 V 150 mA, 40 V in | C132202 | 1 | |
| U3 | AP2112K-3.3TRG1 | C51118 | 1 | |
| U4, U5 | TPS1H100AQPWPRQ1, HTSSOP-14 (exposed pad) | C478465 | 2 | A-version = ST status pin |
| U6, U7 | INA240A1PWR, TSSOP-8 | C93965 | 2 | Automotive alt INA240A1QPWRQ1 C553123 |
| U8, U9 | UCC27517DBVR, SOT-23-5 | C99395 | 2 | |
| Q1, Q2 | AOD2610E, 60 V N-FET, TO-252 | C282428 | 2 | Check RDS(on) at 4.5 V (gate driven at 5 V) |
| Q3–Q8 | 2N7002, SOT-23 | C8545 | 6 | JLCPCB basic part |
| Q9 | AOD4185, −40 V P-FET, TO-252 | C400894 | 1 | Reverse-polarity |
| D1, D2 | SS36, SMA | C727061 | 2 | |
| D3, D4 | BAT54S, SOT-23 | C171786 | 2 | |
| TVS1 | SMBJ24A (Littelfuse), SMB | C224017 | 1 | |
| TVS2, TVS3 | SMBJ20CA bidirectional, SMB | C713702 | 2 | |
| Rs1, Rs2 | RLP25FECR030, 30 mΩ 1% 1 W 2512 | C2930482 | 2 | |
| J1 | Molex 43045-1000 | not at LCSC | 1 | Buy from Digi-Key/Mouser, hand-solder |
| — | 0603 R/C, 2 LEDs, 15 V zener, headers | JLCPCB basic parts | — | Prefer basic parts (no loading fee) |

Cost estimate: parts ~$10–14 per board + connector; ~$25–35 per board assembled in a batch of 5 (extended-part loading fees dominate).

## 8. Layout rules

- 2-layer, ~50 x 70 mm, solid GND pour on bottom; JLCPCB standard capabilities.
- Kelvin sense: route INA240 inputs as a tight pair from the inner edges of the shunt pads; never share the coil-current path.
- Keep the coil current loop (U4 → COIL+ → coil → Rs → NODE_X → Q1/D1) short and wide (≥1 mm traces or pours, 5 A pick-up peak); keep it away from CMD/ISENSE/MCU nets.
- Thermal copper under U4/U5 exposed pads (vias to bottom GND only if the pad is GND per datasheet) and under Q1/Q2/Q9 tabs.
- J1 and TVS1/TVS2/TVS3 at the board edge, TVS parts right at the connector pins.
- Decoupling caps adjacent to every IC supply pin; INA240 and ADC divider/filter close to the MCU.
- Mounting holes x4 (M3), conformal-coat friendly (no parts under the connector overhang).

## 9. Firmware notes (src/main.cpp v2)

- States: OFF → PICKUP (PI loop to pick-up current, may use 100% duty) → HOLD (PI loop to hold current, capped 95%) ; PASS (100% for self-economized contactors) ; FAULT (latched until command removed).
- Control: 1 kHz loop, 20 kHz PWM on TIM3; feed-forward = target × coil ohms ÷ VBAT, plus PI (KP 0.20, KI 2.0, integrator clamp ±0.30).
- Faults: not configured; pick-up low (<60% of pick-up at end of pick-up); overcurrent (auto = max(1.5×pick-up, 3×hold)+0.5 A, capped 6.5 A; drives KILL); hold low; hold high (>2.5× hold for 500 ms; reported only); high-side ST low.
- Profiles in flash via STM32duino buffered EEPROM emulation (`eeprom_buffer_fill`, `eeprom_buffered_read_byte`, `eeprom_buffered_write_byte`, `eeprom_buffer_flush`), CRC32-protected. Factory default = unconfigured (won't energize).
- Presets: `unconfigured`, `gv200-005` (2.5 A / 200 ms / hold 0.30 A / 5.0 Ω), `ger150` (0.45 A / 100 ms / 0.25 A / 23.5 Ω), `aev14012` (0.44 A / 100 ms / 0.16 A / 25.9 Ω), `passthrough`.
- CLI (115200): `help`, `show`, `presets`, `preset <1|2> <name>`, `set <1|2> <mode|pickup|pickup_ms|hold|ohms|oc> <value>`, `save`, `defaults`, `log on|off`. Settings change only while both commands are off.
- Truck setup: `preset 1 gv200-005`, `preset 2 gv200-005`, `save`.
- Scaling: ISENSE 0.4 V/A at ADC (30 mΩ × 20 × 2/3); VBAT 22/122.
- Likely compile trouble spots: HardwareTimer pin→channel mapping on PA6/PA7 (must be TIM3 CH1/CH2, not TIM16/17 alternates), EEPROM buffered API names, `offsetof` on the struct, F() macro in ternaries.

## 10. Bring-up (contactor studs disconnected from HV; bench supply 12 V, 3 A limit)

1. Nucleo-G031K8: flash, `preset 1 gv200-005`, `save`, ground PB0. Expect PICKUP then HOLD; with no coil, FAULT (pick-up low) after 200 ms.
2. Breadboard one low-side channel (UCC27517, Q1, D1, 30 mΩ shunt, INA240) on a real GV200 coil, with a toggle switch between VBB (D1 cathode side) and COIL+ standing in for the high-side switch, and SMBJ20CA from COIL+ to GND. Logged hold ≈ 0.30 A; supply shows ≈ 0.04–0.05 A average.
3. Release check: open the toggle switch (not the supply lead). Main-stud continuity should stop within ~12 ms; scope on COIL+ should swing to about −24 to −32 V.
4. PCB: repeat with the VCU outputs; unplug CMD and confirm the contactor opens.

## 11. Open items

- [x] Compile firmware (done session 2; not yet flashed to a Nucleo).
- [x] TPS1H100-Q1 CL resistor (390 ohm, 6.3 A) and clamp coordination (see section 0, change 1).
- [ ] UCC27517 UVLO turn-on is 4.65 V max over temperature vs a 5 V (±2%) rail: OK, ~0.25 V margin. Confirm on bench.
- [ ] Contactors with built-in economizers (passthrough mode) see COIL+ pulled ~21 V negative for <1 ms at release
      while Q1 is still on. Check that such contactors tolerate reverse voltage before using passthrough.
- [ ] Release-clamp TVS rating: SMBJ (600 W, 1 ms) is fine for release from hold (mJ) and from a 2.5 A pick-up
      (~0.3 J at 100 mH); at the 5 A hardware maximum consider SMCJ28A.
- [ ] Measure GV200 coil inductance (LCR, or τ = L/R from a current-rise scope capture). Release energy ½LI²: 0.31 J at 2.5 A / 100 mH, 1.25 J at 5 A; TVS2/TVS3 must absorb it.
- [ ] TPS1H100-Q1: pick the CL resistor for ~6.5 A; check its output clamp voltage versus SMBJ20CA so the TVS takes the energy; confirm reverse-battery behavior with Q9.
- [ ] Consider raising the release clamp toward Gigavac's ~55 V if the high-side switch rating allows (faster release).
- [ ] Confirm AOD2610E RDS(on) at 4.5 V gate; confirm UCC27517 UVLO is comfortably below 5 V.
- [ ] Decide whether the ZombieVerter reads STAT_1/STAT_2 (spare digital inputs) or they only drive LEDs.
- [ ] Coil wire counts for GER150 and AEV14012 (for the contactor table).
- [ ] Optional future: 24 V variant (60 V parts), CAN (STM32G0B1), third channel.
