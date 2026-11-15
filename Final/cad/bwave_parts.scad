// B'Wave 机构 - 打印件（参数化，OpenSCAD）
// 坐标：XY = 画板平面（Y 指向牌的上方），Z = 离开画板、朝观众
// 牌的编号：0 = 最前面（离观众最近），3 = 最后面（最靠画板）
// 用法：改 PART，F6 渲染，File > Export > STL
//   "layout"  整体预览（不打印）
//   "bracket" 摆动舵机支架 x1
//   "arm0".."arm3" 四根臂（已转成打印朝向：梁贴床，立柱朝上）
//   "clip"    牌夹 x4（+备用）——缝宽要按 cliptest 的结果改 CARD_T
//   "cliptest" 牌夹缝宽测试片（只跟牌厚有关，现在就能打）
//   "fittest"  装配测试件：摆动舵机卡槽 + 舵盘轮毂 + 翻牌舵机托架（量完尺寸后先打这个）
PART  = "layout";
STYLE = "column";   // "column" = 平支架，臂上有立柱（已选定）；"step" = 阶梯支架，臂是平的
GIMMICK = 2;        // 结局牌是第几张（0 起，从前往后），默认第 3 张
STATE = 0;          // 预览用：0 叠放，1 展开·揭示1，2 结局牌移出，3 白板散开
BRANCH = 1;         // 预览用：1 = 红桃分支，-1 = 方块分支（所有角度镜像，结局牌移出方向相反）
$fn = 40;

// ================= 到货后用卡尺量，改这里 =================
SW_L = 40.0; SW_W = 20.0; SW_H = 40.5;  // DS3218 机身长/宽/高（零售页标称）
SW_TAB_Z   = 28.0;  // 【量】耳朵下表面离机身底面
SW_TAB_L   = 54.5;  // 【量】含耳朵总长
SW_HOLE_DX = 49.5;  // 【量】两端耳朵孔距
SW_HOLE_DY = 10.0;  // 【量】同一耳朵两孔距
SW_SHAFT   = 10.0;  // 【量】输出轴中心离机身近端
HORN_TOP   = 7.0;   // 【量】舵盘顶面高出机身顶盖
HORN_D     = 24.0;  // 【量】舵盘外径
HORN_PCD   = 16.0;  // 【量】舵盘固定孔所在圆直径
HORN_HOLE  = 3.2;

FL_L = 22.8; FL_T = 12.2; FL_H = 22.5;  // MG90S 机身长/厚/高（零售页标称）
FL_SHAFT   = 5.9;   // 【量】输出轴中心离机身近端
FL_TAB_FROM_TOP = 6.5; // 【量】耳朵下表面离顶盖
FL_TAB_SPAN = 32.3; // 【量】含耳朵总长
FL_HOLE_DX = 27.8;  // 【量】耳朵孔距
FL_ABOVE   = 9.0;   // 【量】舵盘顶面高出顶盖
CARD_T     = 0.30;  // 【量】牌厚
CARD_W = 63.5; CARD_H = 88.9;

// ================= 布局 =================
PITCH_X = STYLE == "step" ? 50 : 34;  // 转轴左右间隔（碰撞检查：立柱 34mm 时最小余量约 10mm）
PITCH_Z = 15;     // 层间距
ARM_L   = 150;    // 转轴到牌下边缘
BEAM_W  = 10; BEAM_T = 10;
COL_D   = 20;     // 立柱直径（碰撞余量按 20mm 核对过）
HORN_BOLTS = false; // 舵盘用胶粘（false）还是打 M3 螺丝孔（true，要求立柱够粗，到货后再定）
CLIP_H  = 10; CLIP_GRIP = 8;
CLR     = 0.3;

function px(i)    = (i - 1.5) * PITCH_X;
function riser(i) = STYLE == "step"   ? (3 - i) * PITCH_Z : 0;  // 舵机垫高
function colh(i)  = STYLE == "column" ? (3 - i) * PITCH_Z : 0;  // 臂上立柱
function zc(i)    = colh(i) + BEAM_T / 2;                       // 牌面相对本舵盘顶面

// ---------------- 支架 ----------------
BR_WALL = 6;
BR_Y = SW_TAB_L + 12;
pocket_cy = -(SW_L / 2 - SW_SHAFT);
module bracket() {
  difference() {
    union() for (i = [0:3])
      translate([px(i) - PITCH_X / 2 + (i == 0 ? -BR_WALL : 0), pocket_cy - BR_Y / 2, 0])
        cube([PITCH_X + (i == 0 || i == 3 ? BR_WALL : 0), BR_Y, riser(i) + SW_TAB_Z]);
    for (i = [0:3]) translate([px(i), pocket_cy, 0]) {
      translate([-(SW_W + 2*CLR) / 2, -(SW_L + 2*CLR) / 2, riser(i)]) cube([SW_W + 2*CLR, SW_L + 2*CLR, SW_TAB_Z + 1]);
      translate([-5, -BR_Y / 2 - 1, riser(i)]) cube([10, BR_Y / 2, 4]);   // 出线槽
      for (sx = [-1, 1], sy = [-1, 1]) translate([sy * SW_HOLE_DY / 2, sx * SW_HOLE_DX / 2, riser(i) + SW_TAB_Z - 12]) cylinder(d = 2.6, h = 13);
    }
  }
}

// ---------------- 臂 ----------------
FL_TOP_Y = ARM_L - CLIP_H + CLIP_GRIP - FL_ABOVE;
FL_BOT_Y = FL_TOP_Y - FL_H;
FL_TAB_Y = FL_TOP_Y - FL_TAB_FROM_TOP;
module beam(a, b, w, t) { hull() { translate([a[0], a[1], 0]) cylinder(d = w, h = t); translate([b[0], b[1], 0]) cylinder(d = w, h = t); } }
module arm(i) {
  cx = -px(i); bx0 = cx - FL_SHAFT; bx1 = bx0 + FL_L;
  lugw = (FL_TAB_SPAN - FL_L) / 2 + 2;
  difference() {
    union() {
      cylinder(d = COL_D + (STYLE == "step" ? 10 : 0), h = colh(i) + BEAM_T);
      translate([0, 0, colh(i)]) {
        beam([0, 0], [cx, FL_BOT_Y - 6], BEAM_W, BEAM_T);
        translate([bx0 - lugw, FL_BOT_Y - 8, 0]) cube([FL_L + 2 * lugw, 7, BEAM_T]);
        for (x = [bx0 - lugw, bx1]) translate([x, FL_BOT_Y - 8, 0]) cube([lugw, FL_TAB_Y - FL_BOT_Y + 8, BEAM_T]);
      }
    }
    if (HORN_BOLTS) for (k = [0:3]) rotate(45 + 90 * k) translate([HORN_PCD / 2, 0, -1]) cylinder(d = HORN_HOLE, h = colh(i) + BEAM_T + 2);
    translate([0, 0, -1]) cylinder(d = 6.2, h = colh(i) + BEAM_T + 2);   // 舵盘中心螺丝的通孔（螺丝刀从顶上伸进去）
    translate([bx0 - CLR, FL_BOT_Y - CLR, colh(i) - 1]) cube([FL_L + 2 * CLR, FL_TAB_Y - FL_BOT_Y + 2 * CLR, BEAM_T + 2]);
    for (s = [-1, 1]) translate([bx0 + FL_L / 2 + s * FL_HOLE_DX / 2, FL_TAB_Y - 8, zc(i)]) rotate([-90, 0, 0]) cylinder(d = 1.7, h = 9);
    translate([0, 0, colh(i) + BEAM_T - 3]) beam([0, 0], [cx, FL_BOT_Y - 6], 4, 4);
  }
}

// ---------------- 牌夹 ----------------
module clip() {
  w = 24; d = BEAM_T;
  difference() {
    translate([-w / 2, 0, -d / 2]) cube([w, CLIP_H, d]);
    translate([-w / 2 - 1, CLIP_H - CLIP_GRIP, -(CARD_T + 0.15) / 2]) cube([w + 2, CLIP_GRIP + 1, CARD_T + 0.15]);
    translate([-3, -1, -d / 2 - 1]) cube([6, 3.5, d + 2]);
  }
}
module cliptest() {
  ws = [0.30, 0.40, 0.50, 0.60, 0.70];
  difference() {
    cube([len(ws) * 12 + 4, 14, 10]);
    for (k = [0:len(ws) - 1]) translate([4 + k * 12, -1, 2]) cube([ws[k], 16, 9]);
  }
  for (k = [0:len(ws) - 1]) for (m = [0:k]) translate([3 + k * 12 + m * 2, 14, 0]) cube([1.2, 2, 2]);
}

// 打印朝向：上下翻转，让梁和托架贴打印床，立柱朝上，不需要支撑
module arm_print(i) translate([0, 0, colh(i) + BEAM_T]) mirror([0, 0, 1]) arm(i);

// ---------------- 装配测试件 ----------------
// 三小块，几分钟打完，用来确认量出来的尺寸对不对
module fittest() {
  // A 摆动舵机卡槽（6mm 高的框，舵机插进去看松紧，耳朵孔对不对得上）
  difference() {
    translate([-(SW_W + 12) / 2, -SW_TAB_L / 2 - 3, 0]) cube([SW_W + 12, SW_TAB_L + 6, 6]);
    translate([-(SW_W + 2*CLR) / 2, -(SW_L + 2*CLR) / 2, -1]) cube([SW_W + 2*CLR, SW_L + 2*CLR, 8]);
    for (sx = [-1, 1], sy = [-1, 1]) translate([sy * SW_HOLE_DY / 2, sx * SW_HOLE_DX / 2, -1]) cylinder(d = 2.6, h = 8);
  }
  // B 立柱底座（试粘到舵盘上，看中心螺丝能否从孔里拧到）
  translate([45, 0, 0]) difference() {
    cylinder(d = COL_D, h = 10);
    translate([0, 0, -1]) cylinder(d = 6.2, h = 12);
  }
  // C 翻牌舵机托架（臂末端那一段）
  translate([95, -FL_BOT_Y - 20, 0]) intersection() {
    translate([-60, FL_BOT_Y - 12, 0]) cube([120, FL_TAB_Y - FL_BOT_Y + 14, BEAM_T]);
    translate([px(1.5 - 0), 0, 0]) arm_flat_end();
  }
}
module arm_flat_end() {   // 与 arm() 相同的托架几何（取 1.5 号位，即牌中心正对转轴）
  bx0 = -FL_SHAFT; bx1 = bx0 + FL_L; lugw = (FL_TAB_SPAN - FL_L) / 2 + 2;
  translate([-px(1.5), 0, 0]) difference() {
    union() {
      translate([bx0 - lugw, FL_BOT_Y - 8, 0]) cube([FL_L + 2 * lugw, 7, BEAM_T]);
      for (x = [bx0 - lugw, bx1]) translate([x, FL_BOT_Y - 8, 0]) cube([lugw, FL_TAB_Y - FL_BOT_Y + 8, BEAM_T]);
    }
    translate([bx0 - CLR, FL_BOT_Y - CLR, -1]) cube([FL_L + 2 * CLR, FL_TAB_Y - FL_BOT_Y + 2 * CLR, BEAM_T + 2]);
    for (s = [-1, 1]) translate([bx0 + FL_L / 2 + s * FL_HOLE_DX / 2, FL_TAB_Y - 8, BEAM_T / 2]) rotate([-90, 0, 0]) cylinder(d = 1.7, h = 9);
  }
}

// ---------------- 预览用假零件 ----------------
module sw_dummy() {
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_L / 2, 0]) cube([SW_W, SW_L, SW_H]);
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_TAB_L / 2, SW_TAB_Z]) cube([SW_W, SW_TAB_L, 2.5]);
  color("silver") translate([0, 0, SW_H]) cylinder(d = HORN_D, h = HORN_TOP);
}
module fl_dummy(i) {
  cx = -px(i);
  color("black") translate([cx - FL_SHAFT, FL_BOT_Y, zc(i) - FL_T / 2]) cube([FL_L, FL_H, FL_T]);
  color("black") translate([cx - FL_SHAFT + FL_L / 2 - FL_TAB_SPAN / 2, FL_TAB_Y, zc(i) - FL_T / 2]) cube([FL_TAB_SPAN, 2.5, FL_T]);
}
module card(i) {
  cx = -px(i);
  color(i == GIMMICK ? "orangered" : "white") translate([cx - CARD_W / 2, ARM_L, zc(i) - 0.15]) cube([CARD_W, CARD_H, 0.3]);
  color("gold") translate([cx - 12, ARM_L - CLIP_H + CLIP_GRIP - CLIP_H + 2, zc(i) - BEAM_T / 2]) cube([24, CLIP_H, BEAM_T]);
}
// 摆角（模拟器默认值，白板散开角度待重新调；方块分支 = 红桃分支取反）
SP = [for (i = [0:3]) (i - 1.5) * 3.5];
function ang0(i) =
  STATE == 0 ? 0 :
  STATE == 1 ? SP[i] :
  STATE == 2 ? (i == GIMMICK ? 40 : SP[i]) :
  (i == GIMMICK ? 40 : [-44, -16, 12][i < GIMMICK ? i : i - 1]);
function ang(i) = BRANCH * ang0(i);
module layout() {
  color("tan") translate([-180, -90, -3]) cube([360, 360, 3]);          // 画板
  color("lightsteelblue") bracket();
  for (i = [0:3]) translate([px(i), 0, riser(i)]) {
    sw_dummy();
    translate([0, 0, SW_H + HORN_TOP]) rotate(ang(i)) {
      color(i == GIMMICK ? "salmon" : "steelblue") arm(i);
      fl_dummy(i); card(i);
    }
  }
}

if (PART == "layout") layout();
else if (PART == "bracket") bracket();
else if (PART == "arm0") arm_print(0);
else if (PART == "arm1") arm_print(1);
else if (PART == "arm2") arm_print(2);
else if (PART == "arm3") arm_print(3);
else if (PART == "fittest") fittest();
else if (PART == "clip") clip();
else if (PART == "cliptest") cliptest();
