### Design & Strategy

#### Core Strategy: Locked Left-Rail Vertical Hunter (`sub_x = 1`, facing right)
In Seaquest, all enemies, enemy bullets, and divers move purely horizontally across every column, and **only `sub_front` has a hitbox** (`sub_back` never collides). Locking the submarine to a single vertical rail at **`sub_x = 1` facing right** (`sub_back = 0`, `sub_front = 1`) solves both gameplay and network capacity simultaneously:

1. **Zero Left-Side Bullet Threat & Maximum Firing Coverage:** Because right-moving enemy submarines always move from `x = 0` to `x = 1` before their first shot (`move_speed <= 5`, `enemy_shot_interval = 10`), **no enemy bullet ever enters `x = 1` from the left**. Facing right from `x = 1` never requires turning, covers 80% of the board (`x = 2..9`) with every shot, and lets friendly bullets intercept left-moving submarines before they can shoot.
2. **Alignment & Permanent Rail Lock:** Starting in safe Row 0 (`sub_x = 5`), the policy moves left to `(0, 0)` and steps right once to `(0, 1, facing right)`. Once underwater, `left` and `right` have logit `-100`, preventing drift (even under 10% sticky actions, any overshoot at Row 0 immediately re-aligns).
3. **3-Step-Ahead Bullet Dodging & Graded Risk:** For each underwater row `r = 1..8`, danger is graded into four levels: **lethal** (`ch1` at `x = 0, 1, 2`), **warning** (`ch1` at `x = 3`), **early bullet warning** (`ch1 - ch2 = 1` at `x = 4`), and **safe**. Our current row escapes immediately on any danger in `x = 0..3` or incoming bullet at `x = 4` (giving 2–3 steps of margin against 10% sticky actions). Adjacent rows hard-block lethal rows (`-69.3`), softly avoid `x = 3` warnings (`-22.6`, still usable for emergency escape from a lethal row), and give a `+5.4` bonus to step into adjacent safe rows containing un-targeted enemies.
4. **Exact Gauge Disambiguation & Surfacing:** Because Channel 5 merges `oxygen_guage` (`cols 0..oxygen//20-1`) and `diver_guage` (`cols 9-divers..8`), we distinguish:
   - **Safe-to-surface (`has_diver_certain`):** `ch5(9, 8) == 1` **and** at least one `0` exists in `ch5(9, 0..7)` — mathematically guaranteeing `diver_count >= 1` even when full oxygen lights `0..8`. Entering Row 0 from Row 1 is hard-blocked (`-75`) whenever unconfirmed, soft-guarded (`-24.9`) when confirmed with plenty of oxygen (allowing emergency lifesaving escape), and wide open when `oxygen < 60` (`ch5(9, 2) == 0`), triggering a strong upward climb (`+30`) that still refuses to step into lethal rows.
   - **Diver urgency (`diver_need`):** Uses `ch5(9, 8)` and `ch5(9, 7)` directly: maximum priority when `0` divers are held (`ch5(9, 8) == 0`), moderate when `1` backup diver is held, and off when `>= 2` divers are held so the agent maximizes enemy-shooting rate.
5. **Shot Efficiency & Active Hunting:** Friendly bullets in `x = 2..5` directly indicate `shot_timer > 0` (`cooldown`), suppressing `fire` so the sub immediately moves to the next target row. Subtracting `ch3(r, 2..9)` from each row's enemy detector turns off a row as soon as its enemy already has a bullet heading for it, preventing redundant shots. Non-adjacent enemies are hunted via a centered row-moment signal, while a global danger-repel signal biases escapes toward the less crowded half of the board.

---

#### Hidden Unit Allocation

**Layer 1 (`h1`, 32 units):**
- `h1[0]` (`align`): `+1` if `ch0` occupies `c = 2..9` (move left), `-1` if at `(0, 0, left)` (`ch4(0,1) = 1`, move right), `0` when aligned at `(sub_x = 1, right)`.
- `h1[1..8]` (`Y_ge[1..8]`): Thermometer encoding of `sub_y` (`+1` if `sub_y >= r`, `-1` otherwise), enabling exact linear 1-hot row selection `p_r = (Y_ge[r] - Y_ge[r+1]) / 2` in Layer 2.
- `h1[9..16]` (`D[1..8]`): 4-level danger per row `r = 1..8`: `+1.00` (lethal `x = 0..2`), `-0.50` (`x = 3`), `-0.74` (bullet at `x = 4`), `-0.98` (safe).
- `h1[17..24]` (`SE[1..8]`): Safe un-targeted shootable enemy per row `r = 1..8` (`ch1 + ch2` in `x = 4..9`, minus `ch3` friendly bullets in `x = 2..9`, suppressed by any danger in `x = 0..3`).
- `h1[25]` (`has_diver_certain`): `+1` iff `ch5(9, 8) == 1` and `sum ch5(9, 0..7) <= 7`.
- `h1[26]` (`low_oxygen`): `+1` iff `ch5(9, 2) == 0` (`oxygen < 60`).
- `h1[27]` (`cooldown`): `+1` iff any friendly bullet is in `c = 2..5` (`shot_timer > 0`).
- `h1[28]` (`diver_dir`): Signed vertical offset from `sub_y` to catchable divers (`ch2 - ch1` in `c = 0..3`).
- `h1[29]` (`diver_present`): `+1` iff a catchable diver exists in `c = 0..3`.
- `h1[30]` (`diver_need`): 3-level urgency (`+1` for 0 divers, `0` for 1 diver, `-1` for `>= 2` divers / full oxygen).
- `h1[31]`: Unused (`0`).

**Layer 2 (`h2`, 32 units):**
- `h2[0]` (`align`): Drives `left` / `right` (`+100` when misaligned, `-100` when aligned).
- `h2[1..8]` (`cur_good[1..8]`): Analog MUX selecting our current row `sub_y`: outputs `+1` (safe & enemy -> `fire`), `0` (safe & empty -> move), `-1` (dangerous or Row 0 -> escape / don't fire).
- `h2[9..15]` (`up_state[2..8]`): Analog MUX of `row[sub_y - 1]` combining lethal block (`-69.3`), warning avoidance (`-22.6`), bullet-at-4 avoidance (`-11.7`), empty (`-5.5`), and adjacent-enemy attraction (`-0.06`).
- `h2[16..23]` (`down_state[0..7]`): Analog MUX of `row[sub_y + 1]` with the same 5-level valuation.
- `h2[24]` (`walls`): `-1` at `sub_y = 0` (pushes `down` `+32` into safe Row 1), `0` in `1..7`, `+1` at `sub_y = 8` (blocks useless `down` `-32`).
- `h2[25]` (`row1_up_guard`): Active only at `sub_y = 1`; gives `-75` (no diver), `-24.9` (diver held, high oxygen), or `-0.17` (ready to surface).
- `h2[26]` (`want_surface`): `has_diver_certain AND low_oxygen` -> adds `+30` to `up`.
- `h2[27]` (`cooldown`): Suppresses `fire` by `-35` during shot cooldown.
- `h2[28..29]` (`diver_dn`, `diver_up`): Symmetric gated diver-seeking pair, scaled by `diver_present` and `diver_need`.
- `h2[30]` (`enemy_seek`): Global vertical guidance toward non-adjacent safe enemies (and gentle centering at Rows 4–5 when empty).
- `h2[31]` (`danger_repel`): Global danger moment steering escapes away from the more dangerous half of the screen.

```edits
# ==============================================================================
# LAYER 1 (W1: 600 x 32, b1: 32)
# Input index: (row * 10 + col) * 6 + ch
# Channels: 0=player, 1=danger, 2=reward, 3=projectile, 4=trail, 5=gauge
# ==============================================================================

# h1[0]: align (+1 => move left, -1 => move right, 0 => aligned at sub_x=1 right)
W1[12:540:60, 0] = 20
W1[18:540:60, 0] = 20
W1[24:540:60, 0] = 20
W1[30:540:60, 0] = 20
W1[36:540:60, 0] = 20
W1[42:540:60, 0] = 20
W1[48:540:60, 0] = 20
W1[54:540:60, 0] = 20
W1[10, 0] = -10

# h1[1..8]: Y_ge[1..8] (+1 if sub_y >= r else -1)
W1[60:540:6, 1] = 6
W1[120:540:6, 2] = 6
W1[180:540:6, 3] = 6
W1[240:540:6, 4] = 6
W1[300:540:6, 5] = 6
W1[360:540:6, 6] = 6
W1[420:540:6, 7] = 6
W1[480:540:6, 8] = 6
b1[1:9] = -6

# h1[9..16]: D[1..8] (4-level danger per row r=1..8)
# Lethal: ch1 at c=0..2 (+14); Warning: ch1 at c=3 (+1.65); Bullet-4: ch1-ch2 at c=4 (+1.25)
W1[61:78:6, 9] = 14
W1[79, 9] = 1.65
W1[85, 9] = 1.25
W1[86, 9] = -1.25

W1[121:138:6, 10] = 14
W1[139, 10] = 1.65
W1[145, 10] = 1.25
W1[146, 10] = -1.25

W1[181:198:6, 11] = 14
W1[199, 11] = 1.65
W1[205, 11] = 1.25
W1[206, 11] = -1.25

W1[241:258:6, 12] = 14
W1[259, 12] = 1.65
W1[265, 12] = 1.25
W1[266, 12] = -1.25

W1[301:318:6, 13] = 14
W1[319, 13] = 1.65
W1[325, 13] = 1.25
W1[326, 13] = -1.25

W1[361:378:6, 14] = 14
W1[379, 14] = 1.65
W1[385, 14] = 1.25
W1[386, 14] = -1.25

W1[421:438:6, 15] = 14
W1[439, 15] = 1.65
W1[445, 15] = 1.25
W1[446, 15] = -1.25

W1[481:498:6, 16] = 14
W1[499, 16] = 1.65
W1[505, 16] = 1.25
W1[506, 16] = -1.25

b1[9:17] = -2.2

# h1[17..24]: SE[1..8] (safe un-targeted shootable enemy in row r=1..8)
W1[61:84:6, 17] = -60
W1[85:120:6, 17] = 4
W1[86:120:6, 17] = 4
W1[75:120:6, 17] = -8

W1[121:144:6, 18] = -60
W1[145:180:6, 18] = 4
W1[146:180:6, 18] = 4
W1[135:180:6, 18] = -8

W1[181:204:6, 19] = -60
W1[205:240:6, 19] = 4
W1[206:240:6, 19] = 4
W1[195:240:6, 19] = -8

W1[241:264:6, 20] = -60
W1[265:300:6, 20] = 4
W1[266:300:6, 20] = 4
W1[255:300:6, 20] = -8

W1[301:324:6, 21] = -60
W1[325:360:6, 21] = 4
W1[326:360:6, 21] = 4
W1[315:360:6, 21] = -8

W1[361:384:6, 22] = -60
W1[385:420:6, 22] = 4
W1[386:420:6, 22] = 4
W1[375:420:6, 22] = -8

W1[421:444:6, 23] = -60
W1[445:480:6, 23] = 4
W1[446:480:6, 23] = 4
W1[435:480:6, 23] = -8

W1[481:504:6, 24] = -60
W1[505:540:6, 24] = 4
W1[506:540:6, 24] = 4
W1[495:540:6, 24] = -8

b1[17:25] = -6

# h1[25]: has_diver_certain (+1 iff ch5(9,8)==1 and sum ch5(9,0..7)<=7)
W1[545:590:6, 25] = -6
W1[593, 25] = 48
b1[25] = -3

# h1[26]: low_oxygen (+1 iff ch5(9,2)==0, i.e., oxygen < 60)
W1[557, 26] = -6
b1[26] = 3

# h1[27]: cooldown (+1 iff any friendly bullet in r=1..8, c=2..5)
W1[75:540:60, 27] = 6
W1[81:540:60, 27] = 6
W1[87:540:60, 27] = 6
W1[93:540:60, 27] = 6
b1[27] = -3

# h1[28]: diver_dir (>0 if catchable diver below sub_y, <0 if above)
W1[0:60:6, 28] = 1.8
W1[60:120:6, 28] = 1.4
W1[120:180:6, 28] = 1.0
W1[180:240:6, 28] = 0.6
W1[240:300:6, 28] = 0.2
W1[300:360:6, 28] = -0.2
W1[360:420:6, 28] = -0.6
W1[420:480:6, 28] = -1.0
W1[480:540:6, 28] = -1.4

W1[62:84:6, 28] = -2.8
W1[61:84:6, 28] = 2.8
W1[122:144:6, 28] = -2.0
W1[121:144:6, 28] = 2.0
W1[182:204:6, 28] = -1.2
W1[181:204:6, 28] = 1.2
W1[242:264:6, 28] = -0.4
W1[241:264:6, 28] = 0.4
W1[302:324:6, 28] = 0.4
W1[301:324:6, 28] = -0.4
W1[362:384:6, 28] = 1.2
W1[361:384:6, 28] = -1.2
W1[422:444:6, 28] = 2.0
W1[421:444:6, 28] = -2.0
W1[482:504:6, 28] = 2.8
W1[481:504:6, 28] = -2.8

# h1[29]: diver_present (+1 iff catchable diver in r=1..8, c=0..3)
W1[62:540:60, 29] = 6
W1[68:540:60, 29] = 6
W1[74:540:60, 29] = 6
W1[80:540:60, 29] = 6
W1[61:540:60, 29] = -6
W1[67:540:60, 29] = -6
W1[73:540:60, 29] = -6
W1[79:540:60, 29] = -6
b1[29] = -3

# h1[30]: diver_need (+1: 0 divers, 0: 1 diver, -1: >=2 divers or full O2)
W1[593, 30] = -4
W1[587, 30] = -2
b1[30] = 4

# ==============================================================================
# LAYER 2 (W2: 32 x 32, b2: 32)
# ==============================================================================

# h2[0]: align passthrough
W2[0, 0] = 4

# h2[1..8]: cur_good[1..8] (MUX of current row: +1 fire, 0 safe empty, -1 danger/inactive)
W2[1, 1] = 14
W2[2, 1] = -14
W2[9, 1] = -9
W2[17, 1] = 2

W2[2, 2] = 14
W2[3, 2] = -14
W2[10, 2] = -9
W2[18, 2] = 2

W2[3, 3] = 14
W2[4, 3] = -14
W2[11, 3] = -9
W2[19, 3] = 2

W2[4, 4] = 14
W2[5, 4] = -14
W2[12, 4] = -9
W2[20, 4] = 2

W2[5, 5] = 14
W2[6, 5] = -14
W2[13, 5] = -9
W2[21, 5] = 2

W2[6, 6] = 14
W2[7, 6] = -14
W2[14, 6] = -9
W2[22, 6] = 2

W2[7, 7] = 14
W2[8, 7] = -14
W2[15, 7] = -9
W2[23, 7] = 2

b2[1:8] = -34.78

W2[8, 8] = 14
W2[16, 8] = -9
W2[24, 8] = 2
b2[8] = -20.78

# h2[9..15]: up_state[2..8] (MUX of row sub_y - 1 for sub_y = 2..8)
W2[2, 9] = 12.5
W2[3, 9] = -12.5
W2[9, 9] = 1.8
W2[17, 9] = -1.15

W2[3, 10] = 12.5
W2[4, 10] = -12.5
W2[10, 10] = 1.8
W2[18, 10] = -1.15

W2[4, 11] = 12.5
W2[5, 11] = -12.5
W2[11, 11] = 1.8
W2[19, 11] = -1.15

W2[5, 12] = 12.5
W2[6, 12] = -12.5
W2[12, 12] = 1.8
W2[20, 12] = -1.15

W2[6, 13] = 12.5
W2[7, 13] = -12.5
W2[13, 13] = 1.8
W2[21, 13] = -1.15

W2[7, 14] = 12.5
W2[8, 14] = -12.5
W2[14, 14] = 1.8
W2[22, 14] = -1.15

b2[9:15] = -25.62

W2[8, 15] = 12.5
W2[15, 15] = 1.8
W2[23, 15] = -1.15
b2[15] = -13.12

# h2[16..23]: down_state[0..7] (MUX of row sub_y + 1 for sub_y = 0..7)
W2[1, 16] = -12.5
W2[9, 16] = 1.8
W2[17, 16] = -1.15
b2[16] = -13.12

W2[1, 17] = 12.5
W2[2, 17] = -12.5
W2[10, 17] = 1.8
W2[18, 17] = -1.15

W2[2, 18] = 12.5
W2[3, 18] = -12.5
W2[11, 18] = 1.8
W2[19, 18] = -1.15

W2[3, 19] = 12.5
W2[4, 19] = -12.5
W2[12, 19] = 1.8
W2[20, 19] = -1.15

W2[4, 20] = 12.5
W2[5, 20] = -12.5
W2[13, 20] = 1.8
W2[21, 20] = -1.15

W2[5, 21] = 12.5
W2[6, 21] = -12.5
W2[14, 21] = 1.8
W2[22, 21] = -1.15

W2[6, 22] = 12.5
W2[7, 22] = -12.5
W2[15, 22] = 1.8
W2[23, 22] = -1.15

W2[7, 23] = 12.5
W2[8, 23] = -12.5
W2[16, 23] = 1.8
W2[24, 23] = -1.15

b2[17:24] = -25.62

# h2[24]: walls (-1 at Row 0, 0 in Rows 1..7, +1 at Row 8)
W2[1, 24] = 2
W2[8, 24] = 2

# h2[25]: row1_up_guard (blocks fatal surfacing at sub_y=1; opens when ready to surface)
W2[1, 25] = 12.5
W2[2, 25] = -12.5
W2[25, 25] = -2.8
W2[26, 25] = -1.35
b2[25] = -23.9

# h2[26]: want_surface (has_diver_certain AND low_oxygen)
W2[25, 26] = 4
W2[26, 26] = 4
b2[26] = -4

# h2[27]: cooldown passthrough
W2[27, 27] = 4

# h2[28..29]: gated diver seeking (diver_dn, diver_up)
W2[28, 28] = 2.5
W2[29, 28] = 3.5
W2[30, 28] = 1.8
b2[28] = -5.3

W2[28, 29] = -2.5
W2[29, 29] = 3.5
W2[30, 29] = 1.8
b2[29] = -5.3

# h2[30]: enemy_seek (+ => move down toward safe enemies / center, - => move up)
W2[1:9, 30] = -0.3
W2[17:25, 30] = [-1.05, -0.75, -0.45, -0.15, 0.15, 0.45, 0.75, 1.05]
b2[30] = 0.3

# h2[31]: danger_repel (+ => bottom more dangerous -> move up, - => top more dangerous -> move down)
W2[9:17, 31] = [-0.875, -0.625, -0.375, -0.125, 0.125, 0.375, 0.625, 0.875]

# ==============================================================================
# LAYER 3 (W3: 32 x 6, b3: 6)
# Actions: 0=no-op, 1=left, 2=up, 3=right, 4=down, 5=fire
# ==============================================================================

# Action 0: no-op
W3[1:9, 0] = 16

# Action 1: left
W3[0, 1] = 200

# Action 2: up
W3[9:16, 2] = -35
W3[25, 2] = -37.5
W3[26, 2] = 15
W3[28, 2] = -2.2
W3[29, 2] = 2.2
W3[30, 2] = -2.2
W3[31, 2] = 1.5

# Action 3: right
W3[0, 3] = -200

# Action 4: down
W3[16:24, 4] = -35
W3[24, 4] = -32
W3[28, 4] = 2.2
W3[29, 4] = -2.2
W3[30, 4] = 2.2
W3[31, 4] = -1.5

# Action 5: fire
W3[1:9, 5] = 28
W3[27, 5] = -17.5

b3[0:6] = [92.0, -100.0, -267.5, -100.0, -280.0, 166.5]
```