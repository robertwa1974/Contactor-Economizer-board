# Contactor Economizer: Operator's Manual

Board revision B, firmware v3.

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

Revision B adds an optional stacking socket for an insulation monitor (IMD) board mounted above
this one. Without an IMD, the board works exactly as before (see section 8).

> **High voltage warning.** Do every bench test in this manual with the contactor's main studs
> disconnected from the traction pack. Only connect HV once the board has passed the bench test in
> section 6.

---

## 1. What you need

### Parts not fitted by the factory

JLCPCB assembles all the surface-mount parts. Fit these through-hole connectors yourself:

| Ref | Part | Source |
|---|---|---|
| J1 | Molex Micro-Fit 3.0, 2×7, right angle, **43045-1400** | Digi-Key / Mouser |
| J2 | 1×5 male pin header, 2.54 mm, **right angle** (SWD programming) | any header strip |
| J3 | 1×3 male pin header, 2.54 mm, **right angle** (serial setup) | any header strip |
| J4 | 2×6 female socket, 2.54 mm, vertical, 8.5 mm tall (IMD stacking socket). **Only needed with an IMD board.** | any |

For the harness:

- Mating plug: Molex Micro-Fit 3.0 **43025-1400** receptacle housing.
- Crimp terminals: Micro-Fit 3.0 female crimp terminals (43030 series) to suit your wire.
  Use 18–20 AWG for +12 V, GND and the coil wires.
- A 5 A fuse and holder for the +12 V feed.
- Four M3 screws and standoffs for mounting the board.

For stacking an IMD board (section 8):

- Four **nylon** M3 × 15 mm hex standoffs, male–female.
- Four nylon M3 × 6 mm screws.

### Tools

| Tool | Used for |
|---|---|
| Soldering iron with a chisel tip, solder, flux | Fitting J1, J2, J3 |
| Micro-Fit crimp tool (or pre-crimped leads) | Making the harness |
| Multimeter | Power-up checks |
| 12 V bench supply with adjustable current limit | Power-up and bench test |
| A second bench supply that can deliver 5–10 A, and a meter with a 0.1 mV range | Contactor contact-resistance check (section 6.1) |
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
4. Solder the other 13 pins.
   - Pins 5 and 12 (GND) connect to the large ground plane and need more heat. Use a hotter iron
     (around 370 °C) or hold it longer, until the solder flows into the hole and forms a cone.
5. Check every joint: a smooth cone on all 14 pins and no bridges between them.

### J2 (SWD, 5 pins) and J3 (serial, 3 pins)

Both are right-angle headers, so you can reach them with an IMD board stacked on top.

1. Break a 5-pin and a 3-pin length off a 2.54 mm right-angle header strip.
2. Fit each one from the top with the plastic body lying flat on the board and the long pins
   pointing **off the bottom edge**.
3. Solder one pin, check the header is flat and square, then solder the rest.
   - The GND pins (J2 pin 5, J3 pin 3) need a little extra heat.
4. Pin 1 of each header is the square pad, at the **right-hand** end. The silkscreen labels above
   them read, left to right:
   - J2: `SWD GND RST CK IO 3V3` (pins 5 to 1)
   - J3: `UART GND RX TX` (pins 3 to 1)

### J4 (IMD stacking socket, optional)

Fit J4 only if you're stacking an IMD board.

1. Fit the 2×6 female socket on the top side, bottom-left of the board, upright.
2. Solder one pin, check that the socket is square and flat, then solder the rest. The GND pins
   (2, 4, 8) need extra heat.
3. The pinout is printed on the back of the board (section 8.2).

Clean off the flux with isopropyl alcohol when you're done.

---

## 3. J1 pin map

Pin numbers are moulded on the connector and the plug housing. The same table is printed on the back
of the board.

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | COIL1+ (contactor 1 coil, +) | 8 | COIL1− (contactor 1 coil, −) |
| 2 | CMD_1 (from VCU, pull low = close) | 9 | STAT_1 (to VCU, low = holding OK) |
| 3 | +12 V in | 10 | +12 V in |
| 4 | IMD_MHS (IMD measurement output, to VCU) | 11 | IMD_OKHS (IMD OK output, to VCU) |
| 5 | GND | 12 | GND |
| 6 | CMD_2 (from VCU, pull low = close) | 13 | STAT_2 (to VCU, low = holding OK) |
| 7 | COIL2+ (contactor 2 coil, +) | 14 | COIL2− (contactor 2 coil, −) |

Wiring rules:

- Wire **both** +12 V pins (3 and 10) and **both** GND pins (5 and 12). Each contact is rated about
  5 A, and both contactors can pull in at once.
- Pins 4 and 11 are wired straight through to the IMD socket J4. They carry the IMD board's own
  outputs (Bender IR155-style MHS and OKHS), and their electrical levels are set by the IMD board.
  Without an IMD, leave them unconnected.
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
   pin 5 (GND). It should rise steadily as the input capacitor charges, not sit near 0 Ω.
3. **Power up gently.** Set the bench supply to 12 V with a **100 mA** current limit. Connect it to
   J1 pins 3 (+) and 5 (−).
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
   Contactor economizer v3 (board rev B). Type 'help'.
   No valid settings in flash: both channels unconfigured.
   ch1: unconfigured mode=off ...
   ch2: unconfigured mode=off ...
   imd: optional, IMD_OK=low
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

1. Connect the contactor coil to J1 pins 1 (COIL1+) and 8 (COIL1−).
2. Connect a switch or jumper wire from **pin 2 (CMD_1)** to **pin 5 (GND)**. Closing it stands in for
   the VCU commanding contactor 1 closed.
3. Close the switch. You should see and hear:
   - A firm click as the contactor pulls in.
   - The log shows `ch1 PICKUP`, then `ch1 HOLD` after 0.2 s. For a GV200-005 it shows
     `I=0.30` (amps) and a duty `D` of roughly 10–20 %.
   - Status LED **D9** lights. A meter on J1 pin 9 (STAT_1) reads near 0 V against GND, given a
     pull-up.
   - The bench supply drops to around 0.05 A once holding.
   - The main studs show continuity on a meter.
4. Open the switch. The contactor should drop out at once, D9 goes off and the log shows `ch1 OFF`.
5. Repeat on channel 2: coil on pins 7 and 14, switch from **pin 6 (CMD_2)** to GND, LED **D12**.

A quick fault check: with **no** coil connected, closing the CMD switch should give `ch1 FAULT`
within 0.2 s, with a fault code such as `F=0x11`. Opening the switch clears it.

### 6.1 Contactor resistance check

Do this for every contactor, especially salvaged ones. A used contactor can click and show continuity
on a meter, yet have pitted contacts with a high resistance that varies from one closure to the next.
Under traction current, those contacts overheat.

**Coil resistance.** Measure it with nothing connected, across the two coil terminals. It should be
within about 10 % of the figure for the preset you chose: 4.8 Ω for the GV200-005, 23 Ω for the GER150
and 26 Ω for the AEV14012 (BMW variant). Use a cold contactor, because the reading rises as the coil
warms. An open coil, a short circuit or a figure far from the preset means the contactor is faulty, or
you have chosen the wrong preset.

**Main contact resistance.** An ordinary meter can't read this. A good contact is well under 1 mΩ, below
a meter's lead resistance. Instead, pass a known current through the contacts and measure the voltage
across them:

1. Keep the main studs disconnected from HV.
2. Hold the contactor closed with the board, as in step 3 above.
3. Use a second bench supply, set to about 1 V and a current limit of 5–10 A. Connect its leads to the
   two main studs with ring lugs. The supply then runs in constant-current mode. Note the current, I.
4. With a meter on its lowest DC millivolt range, put the probes directly on the two studs, inside the
   supply's lugs. Note the voltage, V.
5. Contact resistance = V / I. For example, 1.5 mV at 5 A is 0.3 mΩ.
6. Turn the current supply's output off, release the CMD switch, close it again, and turn the
   output back on. Repeat steps 3–5 a few times. Switching the current off first means the contacts
   never break the test current.

What the readings mean:

- **Good:** under 1 mΩ, steady from one closure to the next, and close to the other contactor's reading.
  Where the datasheet gives a contact resistance figure, compare against that.
- **Reject:** above about 1 mΩ, several times the other contactor's reading, or changing noticeably
  between closures. Don't fit that contactor.
- With the contactor **open**, the meter should show the supply's full voltage across the studs and no
  current should flow. Any current means the contacts are welded or bridged.

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

## 8. Using an insulation monitor (IMD)

Rev B can carry an insulation monitor (IMD) board stacked on top, plugged into socket J4. The IMD
board carries all the high voltage; this board stays 12 V only. Without an IMD, leave J4 unfitted and
the IMD setting at its default (`optional`). The board then works exactly as described in the rest of
this manual.

The rule is: **an IMD fault blocks a contactor from closing. It never forces a closed contactor
open.** The VCU decides when to open.

### 8.1 Mounting

- Stack the IMD board on four **nylon M3 × 15 mm** standoffs in the four corner holes, with nylon
  screws on top. Nylon keeps the IMD board's mounting holes from bridging to this board.
  Alternatively, the IMD board's mounting holes must sit in its low-voltage region, with HV
  clearance.
- The 15 mm stack clears the tallest parts on this board (C1, about 8 mm). The IMD board needs a
  male header that reaches down into the 8.5 mm socket J4 across that gap, and a cut-out over J1 so
  the harness plug latch can be pressed.
- The IMD board fits only one way round: rotated, its header misses J4.
- J2 and J3 stay reachable from the bottom edge with the IMD fitted.

### 8.2 Socket J4 pinout

Logic pins are 3.3 V. Each passes through a 1 kΩ resistor and an ESD clamp on this board.

| Pin | Signal | Direction | Meaning |
|---|---|---|---|
| 1 | 12V_PROT | to IMD | +12 V after the reverse-polarity stage, through a 0.2 A resettable fuse (F1) |
| 2, 4, 8 | GND | — | Ground |
| 3 | IMD_OK | from IMD | High = insulation OK. 100 kΩ pull-down here: a missing or dead IMD reads "not OK". |
| 5 | CONT1_CLOSED | to IMD | Channel 1 coil energised (see below) |
| 6 | CONT2_CLOSED | to IMD | Channel 2 coil energised |
| 7 | IMD_INHIBIT | to IMD | High = ask the IMD to stop measuring. Reserved: firmware v3 holds it low. |
| 9 | IMD_TX | to IMD | UART, this board's TX (USART1 PB6) to the IMD's RX: `imd send` (section 8.5) |
| 10 | IMD_RX | from IMD | UART, the IMD's TX to this board (USART1 PB7): IMD status frames (section 8.5) |
| 11 | IMD_MHS | from IMD | Passed straight to J1 pin 4 |
| 12 | IMD_OKHS | from IMD | Passed straight to J1 pin 11 |

**CONT1_CLOSED / CONT2_CLOSED** mean "this channel's coil is energised at 60 % or more of its hold
current" (or, in pass-through, carrying current). They're set 20 ms after that condition starts and
cleared 20 ms after it ends. They are **not** proof that the main contacts have closed: a welded or
mechanically stuck contactor reads the same.

Channel mapping: channel 1 is whichever contactor is wired to J1 pins 1/8, channel 2 is pins 7/14.
**For the truck: channel 1 = positive main contactor, channel 2 = negative main.** Record your own
mapping if it differs.

### 8.3 Power for the IMD

- The IMD draws from 12V_PROT through the 0.2 A resettable fuse F1 (Bourns MF-MSMF020/60). Keep the
  IMD board under about **1 W** (about 0.11 A at 9 V). The fuse's hold current falls as it warms, to
  roughly 0.15 A in a hot enclosure.
- A short on the IMD board trips F1 in milliseconds, before the 5 A harness fuse can blow. The coils
  and this board keep running.
- F1's resistance is at most 6 Ω, so the IMD sees at least about 8.3 V when the vehicle supply is at
  9 V.
- **With `imd required`, feed this board (and so the IMD) from the same permanent 12 V supply as the
  VCU, not a key-switched one.** The IMD then has its 2 s start-up qualification done before the VCU
  asks for the contactors at key-on.

### 8.4 Turning IMD checking on

```
imd required
save
```

`imd optional` turns it off again. The setting is saved with the contactor settings and defaults to
`optional`, so a board without an IMD is never blocked.

With `imd required`:

- IMD_OK only counts as OK once it has been high continuously for **2 s**. This rides through the
  IMD's start-up.
- **Close refused:** if the VCU asks a channel to close while IMD_OK isn't OK, the channel stays open
  and goes to FAULT with code **0x40**. Both its switches are held off. The fault stays latched until
  the VCU removes the command, so the contactor never closes late, out of sequence. The VCU has to
  ask again.
- What the VCU sees for a refused close: STAT stays released (floating), the same as any other fault.
  The channel LED stays off and the serial log shows `FAULT ... F=0x40`. STAT can't say *why*; the
  VCU can read the reason directly from IMD_OKHS on J1 pin 11.
- **IMD_OK lost while closed:** the contactor stays closed. After 20 ms of IMD_OK low, the log shows
  `W=IMD_LOST` for that channel until the command is removed. STAT and the LED are not affected.
  The IMD's own OKHS output tells the VCU.

### 8.5 IMD status over the UART (firmware v3.1)

The IMD board sends a status frame every 0.5 s on socket pin 10. This board shows it but **never
acts on it**: the interlock above uses the IMD_OK wire only, so a dead or garbled UART cannot block
or open a contactor.

- `imd` shows IMD_OK and the last frame: mode, state, OKHS, insulation HV+ and HV- to chassis (Rp,
  Rn in kΩ, `INF` = no measurable leakage), pack voltage, the age of the IMD's last valid measurement,
  calibration (`G` gain, `B` bridge) and pack/system scope. `LOST` = no valid frame for 2 s.
- The status line ends with the IMD mode and Rp/Rn while the link is up (section 9).
- `imd send <text>` passes one command line to the IMD; its replies appear prefixed `IMD> `.
  For example `imd send CAL` shows the IMD's calibration. IMD calibration commands (`CAL ...`)
  are refused unless both channels are off, because calibrating stops the IMD from monitoring.
- `imd log on` also echoes the IMD's own once-a-second status line.

The frame format is defined in the IMD board repository (`lib/imd_core/imd_proto.h`); this board
carries a copy in `lib/imd_proto/`.

---

## 9. Indicators and status

| Indicator | Meaning |
|---|---|
| D5 (green, bottom right) | 12 V present, 3.3 V rail up |
| D9 (channel 1), D12 (channel 2) | Lit = holding (or pass-through) with no fault |
| STAT_1 / STAT_2 (J1 pins 9 / 13) | Pulled low = holding with no fault; floating = off, picking up, or fault |

### Serial status line

```
Vbat=12.84 | ch1 HOLD I=0.301 D=12.6% F=0x0 CLOSED | ch2 OFF I=0.000 D=0.0% F=0x0 | IMD=ok req NORM Rp=20410k Rn=19870k
```

- `Vbat`: supply voltage after the reverse-polarity stage.
- `I`: coil current in amps.
- `D`: switching duty.
- `F`: fault code (below).
- `CLOSED`: the channel's CONTx_CLOSED output is high (section 8.2).
- `W=IMD_LOST`: IMD_OK dropped while this channel was closed (warning only).
- `IMD=`: `ok` (high for 2 s or more), `qual` (high, still qualifying) or `low`, then `req` or `opt`
  for the `imd` setting. Then, from the IMD's UART frames (section 8.5): its mode (`NORM`, `DEV`,
  `EARTH`, ...), Rp and Rn, and its state if not OK (`DEG`, `INT`, `CAL`); or `link=LOST` /
  `link=-` (no frame yet, e.g. no IMD fitted).

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
| 0x40 | IMD inhibit: close refused because IMD checking is on and IMD_OK wasn't OK | Channel stays off, both switches held off | Insulation fault, IMD not running or still starting (under 2 s), IMD unplugged |

Any fault turns the channel's LED off and releases its STAT output, so the VCU can see it. Every
fault clears when the VCU removes the command.

---

## 10. Serial commands

The settings commands (`preset`, `set`, `imd required|optional`, `save`, `defaults`) work only while
both channels are off. `imd`, `imd send` and `imd log` work any time (except `imd send CAL ...`).

| Command | Does |
|---|---|
| `help` | List the commands |
| `show` | Show both channels' settings, plus the IMD setting and state |
| `presets` | List the built-in contactor types |
| `preset <1\|2> <name>` | Load a built-in type into channel 1 or 2 |
| `set <1\|2> mode <off\|econ\|pass>` | Off, economize, or pass-through (plain 12 V) |
| `set <1\|2> pickup <A>` | Pick-up current, up to 5 A |
| `set <1\|2> pickup_ms <ms>` | Pick-up time, 20–1000 ms |
| `set <1\|2> hold <A>` | Hold current (must be less than pick-up) |
| `set <1\|2> ohms <Ω>` | Coil resistance as measured, 0.5–100 Ω |
| `set <1\|2> oc <A>` | Overcurrent trip, 0 = automatic, maximum 6.5 A |
| `save` | Store the settings in flash. Nothing changes permanently without this. |
| `imd <required\|optional>` | Refuse to close unless the IMD reports OK (section 8.4). Default `optional`. |
| `imd` | IMD_OK and the IMD's last status frame (section 8.5) |
| `imd send <text>` | Pass a command to the IMD, e.g. `imd send CAL`; replies show as `IMD> ...` |
| `imd log <on\|off>` | Also show the IMD's own status line |
| `defaults` | Reset both channels to unconfigured and IMD checking to optional (not saved until `save`) |
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

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| D5 not lit | 12 V at J1 pins 3/10 and GND at 5/12; fuse; polarity |
| Upload fails to connect | ST-Link wiring, board powered, try STM32CubeProgrammer "Under reset" (section 5.2) |
| Nothing in the serial monitor | TX/RX crossed over? Adapter at 3.3 V? 115200 baud? Correct COM port? |
| `Refused: remove both VCU commands first.` | A CMD line is being pulled low. Disconnect CMD_1/CMD_2 or turn off the VCU outputs. |
| Channel goes straight to FAULT 0x20 | No contactor type saved (section 5.3) |
| FAULT 0x01 every time | Coil wiring; on the bench, the supply current limit is too low for pick-up (needs at least 3 A) |
| FAULT 0x02 | Coil or harness short; pick-up set higher than the coil needs |
| FAULT 0x40 | IMD checking is on and IMD_OK wasn't OK for 2 s before the close. Check the IMD and J4, and the `imd` setting (`show`). Without an IMD, `imd optional` then `save`. |
| IMD board dead, F1 warm | F1 has tripped: a short or overload on the IMD board. Remove power and fix it; F1 resets as it cools. |
| Contactor chatters or drops out in hold | Hold current too low for that contactor; raise `hold` |
| Contactor slow to open | A diode fitted across the coil? Remove it. |

---

## 12. Ratings and limits

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
| Connector | Molex Micro-Fit 3.0, 14 pins (43045-1400, mates with 43025-1400) |
| IMD socket | 2×6 female, 2.54 mm; 12V_PROT fused at 0.2 A; logic 3.3 V |
| Serial port | 3.3 V logic, 115200 baud, 8N1 |
