# Contactor Economizer: Operator's Manual

Board revision A, firmware v2.

This board drives the coils of two high-voltage contactors from a 12 V vehicle supply. When the vehicle
controller (VCU) commands a contactor closed, the board pulls it in with a strong, current-regulated
pulse and then drops to a much lower hold current. The coil runs cool and the 12 V load drops from
about 28 W to under 1 W per contactor (Gigavac GV200-005).

Safety comes from the hardware, not the firmware:

- Only the VCU command can switch a coil on. The microcontroller can switch a coil **off** at any time,
  but it can never switch one on by itself.
- If the microcontroller is unprogrammed, crashed or held in reset, no coil current flows and the
  contactors stay open.
- Release speed is set by a clamp diode on the board, so contactors open quickly with no help from the
  firmware.

> **High voltage warning.** Do every bench test in this manual with the contactor's main studs
> disconnected from the traction pack. Only connect HV once the board has passed the bench test in
> section 6.

---

## 1. What you need

### Parts not fitted by the factory

JLCPCB assembles all the surface-mount parts. Fit these three through-hole connectors yourself:

| Ref | Part | Source |
|---|---|---|
| J1 | Molex Micro-Fit 3.0, 2×6, right angle, **43045-1200** | Digi-Key / Mouser |
| J2 | 1×5 male pin header, 2.54 mm, vertical (SWD programming) | any header strip |
| J3 | 1×3 male pin header, 2.54 mm, vertical (serial setup) | any header strip |

For the harness:

- Mating plug: Molex Micro-Fit 3.0 **43025-1200** receptacle housing.
- Crimp terminals: Micro-Fit 3.0 female crimp terminals (43030 series) to suit your wire.
  Use 18–20 AWG for +12 V, GND and the coil wires.
- A 5 A fuse and holder for the +12 V feed.
- Four M3 screws and standoffs for mounting.

### Tools

| Tool | Used for |
|---|---|
| Soldering iron with a chisel tip, solder, flux | Fitting J1, J2, J3 |
| Micro-Fit crimp tool (or pre-crimped leads) | Making the harness |
| Multimeter | Power-up checks |
| 12 V bench supply with adjustable current limit | Power-up and bench test |
| **ST-Link programmer**: either an ST-Link V2 clone with female–female jumper wires, or a genuine STLINK-V3MINIE with a 14-pin-to-2.54 mm adapter | Loading the firmware (once) |
| **USB-to-serial adapter, 3.3 V** (CP2102 or FTDI type, set to 3.3 V, *not* 5 V). Not needed with the STLINK-V3MINIE, which has its own serial port. | Choosing the contactor type |
| A computer with VS Code and the PlatformIO extension, and this repository | Building and loading the firmware |

---

## 2. Fitting the through-hole parts

Fit the parts on the **top** side, the side with the components, and solder them on the bottom.

### J1 (harness connector)

1. Hold J1 so its opening faces **off the top edge of the board**. The connector's two plastic pegs
   go into the two large unplated holes. The pegs only fit one way round.
2. Push J1 down until the pegs click home and the body sits flat on the board.
3. Turn the board over. Solder **one corner pin only**, then check that J1 is still flat and square to
   the board edge. If it isn't, reheat that pin and adjust.
4. Solder the other 11 pins.
   - Pins 4 and 10 (GND) connect to the large ground plane and need more heat. Use a hotter iron
     (around 370 °C) or hold it longer, until the solder flows into the hole and forms a cone.
5. Check every joint: a smooth cone on all 12 pins and no bridges between them.

### J2 (SWD, 5 pins) and J3 (serial, 3 pins)

1. Break a 5-pin and a 3-pin length off a 2.54 mm header strip.
2. Fit each one with the **short** pins through the board from the top, leaving the long pins standing
   up.
3. Solder one pin, check the header is upright, then solder the rest.
   - The GND pins (J2 pin 5, J3 pin 3) need a little extra heat.
4. Pin 1 of each header is the square pad. The silkscreen labels below them read:
   - J2: `SWD 3V3 IO CK RST GND` (pins 1 to 5)
   - J3: `UART TX RX GND` (pins 1 to 3)

Clean off the flux with isopropyl alcohol when you're done.

---

## 3. J1 pin map

Pin numbers are moulded on the connector and the plug housing. The same table is printed on the back
of the board.

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | COIL1+ (contactor 1 coil, +) | 7 | COIL1− (contactor 1 coil, −) |
| 2 | CMD_1 (from VCU, pull low = close) | 8 | STAT_1 (to VCU, low = holding OK) |
| 3 | +12 V in | 9 | +12 V in |
| 4 | GND | 10 | GND |
| 5 | CMD_2 (from VCU, pull low = close) | 11 | STAT_2 (to VCU, low = holding OK) |
| 6 | COIL2+ (contactor 2 coil, +) | 12 | COIL2− (contactor 2 coil, −) |

Wiring rules:

- Wire **both** +12 V pins (3 and 9) and **both** GND pins (4 and 10). Each contact is rated about
  5 A, and both contactors can pull in at once.
- Fit a **5 A fuse** in the +12 V feed, close to where it is taken from the vehicle supply.
- Run both coil wires of each contactor **only to the board**. Don't connect COIL− to chassis ground.
  The board switches the low side of the coil itself.
- **Don't fit a flyback diode across the coil.** The board clamps the coil when it releases, and an
  external diode would make the contactor open slowly.
- The GV200-005 coil has no polarity. On a contactor with a built-in diode or economizer, connect
  its + terminal to COILx+.
- CMD_1 and CMD_2 go to the VCU's low-side outputs. These are the outputs that would otherwise
  switch the contactor coils directly. The board pulls each CMD line up to +12 V; the VCU pulling it
  to ground means "close".
- STAT_1 and STAT_2 are open-drain outputs. Each pulls low while its channel is holding with no
  fault, and floats otherwise. Use them only with a pull-up at the VCU end, to no more than 12 V
  and a few mA. If you don't need them, leave them unconnected.

---

## 4. First power-up (before programming)

1. **Look over the board** for solder bridges, especially on J1 and around the small chips.
2. **Check for shorts.** With no power connected, measure resistance between J1 pin 3 (+12 V) and
   pin 4 (GND). It should rise steadily as the input capacitor charges, not sit near 0 Ω.
3. **Power up gently.** Set the bench supply to 12 V with a **100 mA** current limit. Connect it to
   J1 pins 3 (+) and 4 (−).
   - The green power LED **D5** (bottom right) should light.
   - The supply should show a few tens of mA. If it sits at the current limit, switch off and
     look for a short.
4. **Check the rails** with the multimeter, negative probe on any GND pin:
   - **3.3 V** on J2 pin 1 (`3V3`), between 3.2 and 3.4 V.
   - **5 V** on C5, the 10 µF capacitor next to U2. One pad reads 4.9–5.1 V; the other is GND.

The board is protected against reverse polarity, but don't test that deliberately.

---

## 5. Programming the board

A new board has a blank microcontroller, so it does nothing until you load the firmware. You only
need to do this once, and again for firmware updates. After that the board is set up over the serial
port (section 5.3).

### 5.1 Connect the programmer

Power the board from 12 V through J1, as in section 4. You can raise the current limit to 500 mA.

Connect the ST-Link to J2 with jumper wires:

| J2 pin | Label | ST-Link pin |
|---|---|---|
| 1 | 3V3 | **Clone ST-Link V2: leave unconnected.** Genuine ST-Link: connect to VAPP / T_VCC (it only reads the voltage). |
| 2 | IO | SWDIO |
| 3 | CK | SWCLK |
| 4 | RST | RST / NRST |
| 5 | GND | GND |

Clone ST-Links put out 3.3 V on that pin, which would fight the board's own 3.3 V regulator.
That's why it stays unconnected on a clone.

### 5.2 Load the firmware

1. Open the repository folder (the one containing `platformio.ini`) in VS Code with PlatformIO
   installed.
2. Plug the ST-Link into the computer.
3. Click PlatformIO's **Upload** button (the → arrow in the status bar), or run
   `pio run -t upload` in a terminal. The first build downloads the toolchain, which takes a few
   minutes.
4. A successful upload ends with lines like `** Verified OK **` and `SUCCESS`.

The `nucleo_g031k8` build target is correct for this board: it uses the same microcontroller.

If the upload can't connect:

- Check the four wires, and check that the board is powered (D5 lit).
- Install **STM32CubeProgrammer** (free from st.com). Select ST-LINK with mode **Under reset**,
  connect, then program the file `.pio/build/nucleo_g031k8/firmware.elf` that the build produced.

You can disconnect the ST-Link once the firmware is loaded.

### 5.3 Choose the contactor type

The firmware starts with both channels **unconfigured**, so they won't energize anything until you
choose a contactor type and save it.

1. Connect the 3.3 V USB-serial adapter to J3. Cross over TX and RX:

   | J3 pin | Label | Adapter pin |
   |---|---|---|
   | 1 | TX | RX |
   | 2 | RX | TX |
   | 3 | GND | GND |

2. Open a serial monitor at **115200 baud**. PlatformIO's **Serial Monitor** button works, as does
   any terminal program. Choose the adapter's COM port.
3. Power-cycle the board (it has no reset button). You should see:

   ```
   Contactor economizer v2. Type 'help'.
   No valid settings in flash: both channels unconfigured.
   ch1: unconfigured mode=off ...
   ch2: unconfigured mode=off ...
   ```

4. A status line prints every half second. Type `log off` so it doesn't scroll away while you type.
5. For the truck's two Gigavac GV200-005 contactors, type:

   ```
   preset 1 gv200-005
   preset 2 gv200-005
   save
   ```

   The board answers `Saved.` The settings stay in flash through power cycles and resets.
6. Type `show` to confirm both channels, then `log on` to bring back the status line.

Settings can only be changed while **both** CMD lines are released. On the bench, leave CMD_1 and
CMD_2 unconnected. Otherwise the board replies `Refused: remove both VCU commands first.`

---

## 6. Bench test with a contactor

Keep the main studs disconnected from HV. Use the bench supply at 12 V with a 3 A current limit, and
keep the serial monitor open with `log on`.

1. Connect the contactor coil to J1 pins 1 (COIL1+) and 7 (COIL1−).
2. Connect a switch or jumper wire from **pin 2 (CMD_1)** to **pin 4 (GND)**. Closing it stands in for
   the VCU commanding contactor 1 closed.
3. Close the switch. You should see and hear:
   - A firm click as the contactor pulls in.
   - The log shows `ch1 PICKUP`, then `ch1 HOLD` after 0.2 s. For a GV200-005 it shows
     `I=0.30` (amps) and a duty `D` of roughly 10–20 %.
   - Status LED **D9** lights. A meter on J1 pin 8 (STAT_1) reads near 0 V against GND, given a
     pull-up.
   - The bench supply drops to around 0.05 A once holding.
   - The main studs show continuity on a meter.
4. Open the switch. The contactor should drop out at once, D9 goes off and the log shows `ch1 OFF`.
5. Repeat on channel 2: coil on pins 6 and 12, switch from **pin 5 (CMD_2)** to GND, LED **D12**.

A quick fault check: with **no** coil connected, closing the CMD switch should give `ch1 FAULT`
within 0.2 s, with a fault code such as `F=0x11`. Opening the switch clears it.

---

## 7. Installing in the vehicle

1. Mount the board with four M3 screws on standoffs. The holes are on a **69 × 59 mm** grid, centre to
   centre. The board is clear of copper for 4 mm around each hole, so metal screws and washers up to
   7 mm across are fine.
2. Keep J1's top edge accessible and protect the board from water. An enclosure or conformal coating
   is recommended.
3. Wire J1 as in section 3, with the 5 A fuse in the +12 V feed.
4. With the HV disconnected, run the VCU through its contactor sequence. Confirm each contactor
   closes on command and opens when the command is removed.
5. If you can, watch the serial log during the first few drives.

The board just follows the VCU commands. Precharge sequencing, and the decision to open the
contactors, stay with the VCU.

---

## 8. Indicators and status

| Indicator | Meaning |
|---|---|
| D5 (green, bottom right) | 12 V present, 3.3 V rail up |
| D9 (channel 1), D12 (channel 2) | Lit = holding (or pass-through) with no fault |
| STAT_1 / STAT_2 (J1 pins 8 / 11) | Pulled low = holding with no fault; floating = off, picking up, or fault |

### Serial status line

```
Vbat=12.84 | ch1 HOLD I=0.301 D=12.6% F=0x0 | ch2 OFF I=0.000 D=0.0% F=0x0
```

- `Vbat`: supply voltage after the reverse-polarity stage.
- `I`: coil current in amps.
- `D`: switching duty.
- `F`: fault code (below).

| State | Meaning |
|---|---|
| OFF | No command from the VCU |
| PICKUP | Pulling in at the pick-up current |
| HOLD | Holding at the hold current |
| PASS | Pass-through: full 12 V, for contactors with their own economizer |
| FAULT | Stopped. Stays latched until the VCU removes the command. |

### Fault codes

`F` is the sum of these values. For example, `0x11` = 0x10 + 0x01.

| Code | Fault | Effect | Likely cause |
|---|---|---|---|
| 0x01 | Pick-up low: current below 60 % of the pick-up setting at the end of pick-up | Channel stops | Open coil or wire, or battery too low |
| 0x02 | Overcurrent above the trip level | Channel stops and the high-side switch is forced off | Shorted coil or wiring |
| 0x04 | Hold low: can't reach the hold current even at maximum duty | Reported, keeps holding | Low battery, coil resistance higher than set |
| 0x08 | Hold high: current far above the hold setting for 0.5 s | Reported, keeps holding | Low-side switch failed on |
| 0x10 | High-side switch fault (open load, short, or over-temperature) | Reported | Coil disconnected, short to ground, overheating |
| 0x20 | Not configured: the VCU commanded a channel with no contactor type saved | Channel stays off | Do section 5.3 |

Any fault turns the channel's LED off and releases its STAT output, so the VCU can see it. Every
fault clears when the VCU removes the command.

---

## 9. Serial commands

The settings commands (`preset`, `set`, `save`, `defaults`) work only while both channels are off.

| Command | Does |
|---|---|
| `help` | List the commands |
| `show` | Show both channels' settings |
| `presets` | List the built-in contactor types |
| `preset <1\|2> <name>` | Load a built-in type into channel 1 or 2 |
| `set <1\|2> mode <off\|econ\|pass>` | Off, economize, or pass-through (plain 12 V) |
| `set <1\|2> pickup <A>` | Pick-up current, up to 5 A |
| `set <1\|2> pickup_ms <ms>` | Pick-up time, 20–1000 ms |
| `set <1\|2> hold <A>` | Hold current (must be less than pick-up) |
| `set <1\|2> ohms <Ω>` | Coil resistance as measured, 0.5–100 Ω |
| `set <1\|2> oc <A>` | Overcurrent trip, 0 = automatic, maximum 6.5 A |
| `save` | Store the settings in flash. Nothing changes permanently without this. |
| `defaults` | Reset both channels to unconfigured (not saved until `save`) |
| `log <on\|off>` | Status line every 0.5 s |

### Built-in contactor types

| Name | Contactor | Pick-up | Time | Hold | Coil |
|---|---|---|---|---|---|
| `gv200-005` | Gigavac GV200-005 (Mercedes B250e pack) | 2.5 A | 200 ms | 0.30 A | 5.0 Ω |
| `ger150` | LS Electric GER150 (Chevy Bolt) | 0.45 A | 100 ms | 0.25 A | 23.5 Ω |
| `aev14012` | Panasonic AEV14012 (BMW 330e) | 0.44 A | 100 ms | 0.16 A | 25.9 Ω |
| `passthrough` | Any contactor with its own built-in economizer | full 12 V | — | — | — |
| `unconfigured` | Channel disabled | — | — | — | — |

### Setting up a different contactor

1. Measure the coil resistance with a meter.
2. On a current-limited bench supply, find the lowest current that pulls the contactor in firmly
   every time. Then find the current at which it drops out.
3. Set pick-up to about **3× the firm pull-in current** (up to 5 A), with 100–200 ms of pick-up time.
4. Set hold to about **2× the drop-out current**.
5. `set` each value, `save`, then bench-test as in section 6.

For example, the GV200-005 pulls in at 0.8 A and drops out at 0.13 A, which gives 2.5 A pick-up and
0.30 A hold.

Before using pass-through, check that the contactor tolerates a brief reverse voltage on its coil at
release (about −21 V for under 1 ms).

---

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| D5 not lit | 12 V at J1 pins 3/9 and GND at 4/10; fuse; polarity |
| Upload fails to connect | ST-Link wiring, board powered, try STM32CubeProgrammer "Under reset" (section 5.2) |
| Nothing in the serial monitor | TX/RX crossed over? Adapter at 3.3 V? 115200 baud? Correct COM port? |
| `Refused: remove both VCU commands first.` | A CMD line is being pulled low. Disconnect CMD_1/CMD_2 or turn off the VCU outputs. |
| Channel goes straight to FAULT 0x20 | No contactor type saved (section 5.3) |
| FAULT 0x01 every time | Coil wiring; on the bench, the supply current limit is too low for pick-up (needs at least 3 A) |
| FAULT 0x02 | Coil or harness short; pick-up set higher than the coil needs |
| Contactor chatters or drops out in hold | Hold current too low for that contactor; raise `hold` |
| Contactor slow to open | A diode fitted across the coil? Remove it. |

---

## 11. Ratings and limits

| Item | Value |
|---|---|
| Supply | 12 V vehicle systems (about 9–16 V). **Not for 24 V systems**: the input protection diode conducts above about 26 V. |
| Reverse polarity | Protected |
| Channels | 2, independent |
| Coil resistance | 0.5–100 Ω |
| Pick-up current | Up to 5 A, regulated |
| Overcurrent trip | Automatic or set, maximum 6.5 A |
| High-side switch current limit | 5.4–7.2 A (hardware) |
| Release clamp | About 31–34 V across the switch, for fast opening |
| Switching frequency | 20 kHz |
| Board size | 76 × 66 mm, four M3 holes on a 69 × 59 mm grid |
| Connector | Molex Micro-Fit 3.0, 12 pins (43045-1200, mates with 43025-1200) |
| Serial port | 3.3 V logic, 115200 baud, 8N1 |
