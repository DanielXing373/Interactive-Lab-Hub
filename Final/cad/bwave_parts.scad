// B'Wave mechanism - printed parts (parametric OpenSCAD)
// Axes: XY = drawing-board plane (+Y points toward the top of the cards), Z = away from the board, toward the audience
// Card index: 0 = front (closest to the audience), 3 = back (closest to the board)
// Usage: set PART, render (F6), File > Export > STL
//   "layout"         full assembly preview (not printed)
//   "bracket"        swing-servo bracket x1
//   "arm0".."arm3"   the four arms, already in print orientation (front face on the bed, column up)
// The card clips are not printed: off-the-shelf clips glued onto the flip-servo horns (see CLIP_OFF / CLIP_T)
PART    = "layout";
GIMMICK = 2;   // which card is the gimmick card (0-based, front to back)
STATE   = 0;   // preview only: 0 stacked, 1 fanned (reveal 1), 2 gimmick card out, 3 blanks spread
BRANCH  = 1;   // preview only: 1 = hearts branch, -1 = diamonds branch (all angles mirrored)
$fn = 40;

// ================= Measured dimensions =================
// "measured" = taken from the 11/18 sketches (see ../measurements/); "est." = not measured yet
// Swing servo: Miuzei MS24-F (20 kg, 270 deg, 25T spline, d5.9)
SW_L = 40.4; SW_W = 20.2;   // measured: body length (sketch shows 40 and 40.4, took the larger) / width
SW_H       = 39.3;  // measured: body top = 28 + 11.3
SW_SPLINE_TOP = 46.5; // measured: spline top above body bottom
SW_TAB_Z   = 28.0;  // measured: ear underside above body bottom
SW_TAB_L   = 54.6;  // measured: overall length including ears
SW_SHAFT   = 9.0;   // measured: output shaft center from the near end of the body
SW_WIRE_W  = 8;     // est.: wire-exit block width (preview only)
SW_WIRE_P  = 3.2;   // measured: wire-exit block sticks out of the end face (preview only)
HORN_TOP   = 9.5;   // est.: horn top above body top (preview only)
HORN_D     = 24.0;  // est.: horn diameter (preview only)

// Flip servo: MG90S
FL_L = 22.7;        // measured: body length (without ears)
FL_T = 12.2;        // measured: body thickness (~12, nominal 12.2)
FL_H = 22.5;        // est.: body height (bottom to top, without boss); only shifts card height, same for all four
FL_SHAFT   = 5.9;   // est.: shaft center from the near (wire) end; only shifts card left/right, same for all four
FL_TAB_FROM_TOP = 6.5; // ear underside below body top (preview only; seat wall and plate stay below it)
FL_TAB_SPAN = 32.3; // measured: overall length including ears
FL_BOSS = 7; FL_SPLINE = 5;           // measured: plastic boss 7 + metal spline 5 above the body top
FL_ABOVE   = FL_BOSS + FL_SPLINE + 1; // est.: horn top above body top
// Flip-servo seat (3-face locating): body bottom on the bar, far end against the end wall, front face on the plate.
// The wire end and the board side stay open; the ears are not touched. Push into the corner, then glue.
SEAT_BAR    = 6;    // bottom bar height
SEAT_WALL   = 3;    // end wall thickness
SEAT_WALL_H = 12;   // end wall height above the body bottom (below the ears)
PLATE_T     = 1.6;  // front plate thickness (on the bed when printing, so the face touching the servo is flat)
PLATE_H     = 14;   // front plate height above the body bottom (below the ears)
RELIEF_D    = 1.2;  // inside-corner relief grooves (keep printed fillets off the servo edges)
// Off-the-shelf clip glued on the flip-servo horn (card plane passes through the shaft axis)
CLIP_OFF   = 3.0;   // est.: horn top to card bottom edge
CLIP_T     = 10.0;  // est.: clip thickness toward the audience (must stay below the layer pitch)
CLIP_W     = 15.0;  // est.: clip width (preview only)
CLIP_H     = 12.0;  // est.: clip height (preview only)
CARD_W = 63.5; CARD_H = 88.9;

// ================= Layout =================
PITCH_X = 34;     // swing-axis spacing (min clearance arm-to-neighbor-column ~8 mm)
PITCH_Z = 15;     // layer step built into the arm columns (arms are printed, do not change).
                  // Real layer pitch = PITCH_Z + LAYER_LIFT (see bracket) = 18 mm
ARM_L   = 150;    // swing axis to card bottom edge
BEAM_W  = 10;
ZC0     = 5;                          // card plane (= flip-servo shaft) above the arm back face
ARM_T   = ZC0 + FL_T / 2 + PLATE_T;   // arm thickness, back face to front plate (~12.7); whole front is flat for the bed
COL_D   = 20;     // column diameter
CLR     = 0.3;

function px(i)   = (i - 1.5) * PITCH_X;
function colh(i) = (3 - i) * PITCH_Z;   // column height on arm i
function zc(i)   = colh(i) + ZC0;       // card plane above this arm's horn top

// ---------------- Bracket ----------------
// v3 (11/24): with the arms already glued to the horns, the layers touched at the far end
// (flip-servo back to the next plate was only 1.2 mm). Arms unchanged; instead the bracket gets a floor
// and each pocket floor is raised per layer by LAYER_LIFT. Servos are located by the floor only
// (no glue under them) and glued on the side walls. Wall tops sit EAR_GAP below the ears so an ear can
// never prop a servo up on one side. No screw holes.
BR_WALL    = 6;
BR_Y       = SW_TAB_L + 12;
BR_FLOOR   = 2;   // floor thickness
LAYER_LIFT = 3;   // extra lift per layer (conservative, not measured powered): motor-to-plate gap 1.2 -> 4.2 mm
EAR_GAP    = 1;   // wall top below the ear underside
pocket_cy  = -(SW_L / 2 - SW_SHAFT);
function seat(i) = BR_FLOOR + (3 - i) * LAYER_LIFT;   // swing-servo body bottom height
// Output-shaft end (+Y) fully open, pocket width, floor to top: wire block and cable are never blocked
module open_end(z0, h, len) translate([-(SW_W + 2*CLR) / 2, 0, z0 - 0.01]) cube([SW_W + 2*CLR, len, h + 0.02]);
module bracket() {
  difference() {
    union() for (i = [0:3])
      translate([px(i) - PITCH_X / 2 + (i == 0 ? -BR_WALL : 0), pocket_cy - BR_Y / 2, 0])
        cube([PITCH_X + (i == 0 || i == 3 ? BR_WALL : 0), BR_Y, seat(i) + SW_TAB_Z - EAR_GAP]);
    for (i = [0:3]) translate([px(i), pocket_cy, 0]) {
      translate([-(SW_W + 2*CLR) / 2, -(SW_L + 2*CLR) / 2, seat(i)]) cube([SW_W + 2*CLR, SW_L + 2*CLR, SW_TAB_Z + 1]);
      open_end(seat(i), SW_TAB_Z + 2, BR_Y / 2 + 1);
    }
  }
}

// ---------------- Arms ----------------
FL_TOP_Y = ARM_L - CLIP_OFF - FL_ABOVE;   // flip-servo body top, derived from "axis to card bottom = ARM_L"
FL_BOT_Y = FL_TOP_Y - FL_H;
FL_TAB_Y = FL_TOP_Y - FL_TAB_FROM_TOP;
module beam(a, b, w, t) { hull() { translate([a[0], a[1], 0]) cylinder(d = w, h = t); translate([b[0], b[1], 0]) cylinder(d = w, h = t); } }
// Flip-servo seat (arm-local: z = 0 is the arm back face, z = ARM_T the front plate face). cx = shaft x.
SEAT_Y0 = FL_BOT_Y - SEAT_BAR;   // lowest edge of the seat
module fl_seat(cx) {
  xa = cx - FL_SHAFT;            // near (wire) end of the body, open
  xb = xa + FL_L;                // far end of the body, against the end wall
  zf = ZC0 + FL_T / 2;           // front face of the body, against the plate
  difference() {
    union() {
      translate([xa, SEAT_Y0, 0]) cube([xb + SEAT_WALL - xa, SEAT_BAR, ARM_T]);                // bottom bar
      translate([xb, SEAT_Y0, 0]) cube([SEAT_WALL, SEAT_BAR + SEAT_WALL_H, ARM_T]);            // end wall
      translate([xa, SEAT_Y0, zf]) cube([xb + SEAT_WALL - xa, SEAT_BAR + PLATE_H, PLATE_T]);   // front plate
    }
    // inside-corner reliefs
    translate([xa - 1, FL_BOT_Y, zf]) rotate([0, 90, 0]) cylinder(d = RELIEF_D, h = FL_L + 2, $fn = 12);
    translate([xb, FL_BOT_Y - 1, zf]) rotate([-90, 0, 0]) cylinder(d = RELIEF_D, h = PLATE_H + 2, $fn = 12);
    translate([xb, FL_BOT_Y, -1]) cylinder(d = RELIEF_D, h = zf + 1.01, $fn = 12);
  }
}
module arm(i) {
  cx = -px(i);
  tip = [cx, SEAT_Y0 + SEAT_BAR / 2];
  difference() {
    union() {
      cylinder(d = COL_D, h = colh(i) + ARM_T);
      translate([0, 0, colh(i)]) {
        beam([0, 0], tip, BEAM_W, ARM_T);
        fl_seat(cx);
      }
    }
    translate([0, 0, -1]) cylinder(d = 6.2, h = colh(i) + ARM_T + 2);   // through-hole for the horn center screw
    // v2 (11/22): keep the flip-servo body space clear (plus 5 mm past the wire end).
    // The round beam end used to stick 2 mm into it.
    translate([cx - FL_SHAFT - 5, FL_BOT_Y, colh(i) - 1])
      cube([FL_L + 5, FL_H + FL_ABOVE + 5, 1 + ZC0 + FL_T / 2]);
  }
}
// Print orientation: flipped so the front plate is on the bed and the column points up; no supports
module arm_print(i) translate([0, 0, colh(i) + ARM_T]) mirror([0, 0, 1]) arm(i);

// ---------------- Preview-only dummies ----------------
module sw_dummy() {
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_L / 2, 0]) cube([SW_W, SW_L, SW_H]);
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_TAB_L / 2, SW_TAB_Z]) cube([SW_W, SW_TAB_L, 2.5]);
  color("dimgray") translate([-SW_WIRE_W / 2 + 2, pocket_cy + SW_L / 2, 0]) cube([SW_WIRE_W - 4, SW_WIRE_P, 4]);   // wire block
  color("silver") translate([0, 0, SW_H]) cylinder(d = HORN_D, h = HORN_TOP);
}
module fl_dummy(i) {
  cx = -px(i);
  color("black") translate([cx - FL_SHAFT, FL_BOT_Y, zc(i) - FL_T / 2]) cube([FL_L, FL_H, FL_T]);
  color("black") translate([cx - FL_SHAFT + FL_L / 2 - FL_TAB_SPAN / 2, FL_TAB_Y, zc(i) - FL_T / 2]) cube([FL_TAB_SPAN, 2.5, FL_T]);
  translate([cx, FL_TOP_Y, zc(i)]) rotate([-90, 0, 0]) {
    color("dimgray") cylinder(d = 11, h = FL_BOSS);
    color("silver") translate([0, 0, FL_BOSS]) cylinder(d = 4.8, h = FL_SPLINE);
    color("white") translate([0, 0, FL_ABOVE - 1.5]) cylinder(d = 7, h = 1.5);   // horn hub
  }
}
// Axis markers (preview only): red = swing axis (toward the audience), green = flip axis (card center line)
SHOW_AXES = true;
module swing_axis(i) color("red") translate([0, 0, -SW_H - HORN_TOP - 5]) cylinder(d = 1.5, h = SW_H + HORN_TOP + colh(i) + ARM_T + 35);
module flip_axis(i) color("lime") translate([-px(i), FL_BOT_Y - 10, zc(i)]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = ARM_L + CARD_H - FL_BOT_Y + 25);
module label(s, p) color("black") translate(p) linear_extrude(1) text(s, size = 7, halign = "center", valign = "center");
module card(i) {
  cx = -px(i);
  color(i == GIMMICK ? "orangered" : "white") translate([cx - CARD_W / 2, ARM_L, zc(i) - 0.15]) cube([CARD_W, CARD_H, 0.3]);
  color("gold") translate([cx - CLIP_W / 2, ARM_L - CLIP_OFF, zc(i) - CLIP_T / 2]) cube([CLIP_W, CLIP_H, CLIP_T]);   // clip
}
// Swing angles (simulator defaults; blank-spread angles still to be tuned; diamonds = hearts mirrored)
SP = [for (i = [0:3]) (i - 1.5) * 3.5];
function ang0(i) =
  STATE == 0 ? 0 :
  STATE == 1 ? SP[i] :
  STATE == 2 ? (i == GIMMICK ? 40 : SP[i]) :
  (i == GIMMICK ? 40 : [-44, -16, 12][i < GIMMICK ? i : i - 1]);
function ang(i) = BRANCH * ang0(i);
module layout() {
  color("tan") translate([-180, -90, -3]) cube([360, 360, 3]);   // drawing board
  color("lightsteelblue") bracket();
  for (i = [0:3]) translate([px(i), 0, seat(i)]) {
    sw_dummy();
    translate([0, 0, SW_H + HORN_TOP]) {
      if (SHOW_AXES) {
        swing_axis(i);
        label(str("S", i), [0, -42, colh(i) + ARM_T + 40]);
      }
      rotate(ang(i)) {
        color(i == GIMMICK ? "salmon" : "steelblue") arm(i);
        fl_dummy(i); card(i);
        if (SHOW_AXES) flip_axis(i);
      }
    }
  }
}

if (PART == "layout") layout();
else if (PART == "bracket") bracket();
else if (PART == "arm0") arm_print(0);
else if (PART == "arm1") arm_print(1);
else if (PART == "arm2") arm_print(2);
else if (PART == "arm3") arm_print(3);
