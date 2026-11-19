// B'Wave 机构 - 打印件（参数化，OpenSCAD）
// 坐标：XY = 画板平面（Y 指向牌的上方），Z = 离开画板、朝观众
// 牌的编号：0 = 最前面（离观众最近），3 = 最后面（最靠画板）
// 用法：改 PART，F6 渲染，File > Export > STL
//   "layout"  整体预览（不打印）
//   "bracket" 摆动舵机支架 x1
//   "arm0".."arm3" 四根臂（已转成打印朝向：梁贴床，立柱朝上）
//   "fit_big" / "fit_small" / "fit_col"  装配测试件（大 motor 卡槽 / 小 motor 底座 / 立柱底座），"fittest" = 三块合一
// 牌夹不打印：用现成的夹子，胶粘在翻牌舵机的舵盘上（见 CLIP_OFF / CLIP_T）
PART  = "layout";
STYLE = "column";   // "column" = 平支架，臂上有立柱（已选定）；"step" = 阶梯支架，臂是平的
GIMMICK = 2;        // 结局牌是第几张（0 起，从前往后），默认第 3 张
STATE = 0;          // 预览用：0 叠放，1 展开·揭示1，2 结局牌移出，3 白板散开
BRANCH = 1;         // 预览用：1 = 红桃分支，-1 = 方块分支（所有角度镜像，结局牌移出方向相反）
$fn = 40;

// ================= 到货后用卡尺量，改这里 =================
// 摆动舵机：实际到货的是 Miuzei MS24-F（20kg，270°，25T 花键 Ø5.9）
// 【已量】= 11/18 草图上的数；【量】= 还没量
SW_L = 40.4; SW_W = 20.2;  // 【已量】机身长（草图有 40 和 40.4 两个数，取大的，卡槽宁松勿紧）/ 宽
SW_H       = 39.3;  // 【已量】机身顶盖高度 = 28 + 11.3
SW_SPLINE_TOP = 46.5; // 【已量】花键顶面离机身底面
SW_TAB_Z   = 28.0;  // 【已量】耳朵下表面离机身底面（草图标 ≈28）
SW_TAB_L   = 54.6;  // 【已量】含耳朵总长
SW_HOLE_DX = 49.5;  // 【量】两端耳朵孔距（现在是 DS3218 标称值；耳朵是开口槽，胶粘时不影响）
SW_HOLE_DY = 10.0;  // 【量】同一耳朵两孔距（同上）
SW_SHAFT   = 9.0;   // 【已量】输出轴中心离机身近端（草图标 ≈9）
SW_WIRE_W  = 12; SW_WIRE_H = 5;  // 出线口：草图上出线块高 4、凸出 3.2，在输出轴那一端的底部
HORN_TOP   = 9.5;   // 【量】舵盘顶面高出机身顶盖（只影响预览图）
HORN_D     = 24.0;  // 【量】舵盘外径（只影响预览图）
HORN_PCD   = 16.0;  // 【量】舵盘固定孔所在圆直径
HORN_HOLE  = 3.2;

FL_L = 22.7;        // 【已量】MG90S 机身长（不含耳朵）
FL_T = 12.2;        // 【已量】机身厚约 12，按标称 12.2 算
FL_H = 22.5;        // 【量】机身高（底面到顶盖，不含上面的凸台）——只影响牌的高度，四个一样，不影响整齐
FL_SHAFT   = 5.9;   // 【量】输出轴中心离机身近端（出线那一端）——同上，只影响牌的左右位置，四个一样
FL_TAB_FROM_TOP = 6.5; // 耳朵下表面离顶盖（托架不碰耳朵，只用于预览；挡墙和面板高度已避开 4–6.5 的范围）
FL_TAB_SPAN = 32.3; // 【已量】含耳朵总长
FL_BOSS = 7; FL_SPLINE = 5;  // 【已量】顶盖上面：塑料凸台 7 + 金属花键 5 = 12
FL_ABOVE   = FL_BOSS + FL_SPLINE + 1;   // 【量】装上舵盘后舵盘顶面高出顶盖（花键顶 + 约 1，待量）
// 小 motor 底座（三面定位）：底面贴横梁、远离输出轴那一端贴挡墙、朝观众那一面贴面板。
// 出线那一端（输出轴端）和画板一侧敞开；不碰耳朵。舵机往角里一推，三面贴紧再上胶。
SEAT_BAR   = 6;     // 底部横梁高
SEAT_WALL  = 3;     // 挡墙厚
SEAT_WALL_H = 12;   // 挡墙高（从机身底面算，低于耳朵）
PLATE_T    = 1.6;   // 面板厚（打印时贴床，贴舵机那一面最平）
PLATE_H    = 14;    // 面板高（从机身底面算，低于耳朵）
RELIEF_D   = 1.2;   // 内角退让槽直径（防止打印出来的内圆角顶住舵机棱边）
// 现成夹子（胶粘在翻牌舵机舵盘上，夹口朝外，牌面要过舵机输出轴的轴线）
CLIP_OFF   = 3.0;   // 【量】舵盘顶面到牌下边缘（牌插到底后）的距离
CLIP_T     = 10.0;  // 【量】夹子最厚处（朝观众方向），翻牌时要小于层间距
CLIP_W     = 15.0;  // 【量】夹子宽度（只影响预览图）
CLIP_H     = 12.0;  // 【量】夹子高度（只影响预览图）
CARD_W = 63.5; CARD_H = 88.9;

// ================= 布局 =================
PITCH_X = STYLE == "step" ? 50 : 34;  // 转轴左右间隔（碰撞检查：立柱 34mm 时最小余量约 10mm）
PITCH_Z = 15;     // 层间距
ARM_L   = 150;    // 转轴到牌下边缘
BEAM_W  = 10;
ZC0     = 5;                          // 牌面（= 小 motor 输出轴）离臂背面的距离
ARM_T   = ZC0 + FL_T / 2 + PLATE_T;   // 臂的厚度：背面 → 面板正面（≈12.7），整根臂正面齐平，打印时整面贴床
COL_D   = 20;     // 立柱直径（碰撞余量按 20mm 核对过）
HORN_BOLTS = false; // 舵盘用胶粘（false）还是打 M3 螺丝孔（true，要求立柱够粗，到货后再定）
CLR     = 0.3;

function px(i)    = (i - 1.5) * PITCH_X;
function riser(i) = STYLE == "step"   ? (3 - i) * PITCH_Z : 0;  // 舵机垫高
function colh(i)  = STYLE == "column" ? (3 - i) * PITCH_Z : 0;  // 臂上立柱
function zc(i)    = colh(i) + ZC0;                              // 牌面相对本舵盘顶面

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
      translate([-SW_WIRE_W / 2, 0, riser(i) - 0.01]) cube([SW_WIRE_W, BR_Y / 2 + 1, SW_WIRE_H]);   // 出线槽：线从输出轴那一端（+Y）的底部出来
      for (sx = [-1, 1], sy = [-1, 1]) translate([sy * SW_HOLE_DY / 2, sx * SW_HOLE_DX / 2, riser(i) + SW_TAB_Z - 12]) cylinder(d = 2.6, h = 13);
    }
  }
}

// ---------------- 臂 ----------------
FL_TOP_Y = ARM_L - CLIP_OFF - FL_ABOVE;   // 翻牌舵机顶盖的位置，由"转轴到牌下边缘 = ARM_L"倒推
FL_BOT_Y = FL_TOP_Y - FL_H;
FL_TAB_Y = FL_TOP_Y - FL_TAB_FROM_TOP;
module beam(a, b, w, t) { hull() { translate([a[0], a[1], 0]) cylinder(d = w, h = t); translate([b[0], b[1], 0]) cylinder(d = w, h = t); } }
// 小 motor 底座（臂局部坐标：z = 0 是臂背面，z = ARM_T 是臂正面/面板正面）。cx = 输出轴的 x。
SEAT_Y0 = FL_BOT_Y - SEAT_BAR;   // 底座最下沿
module fl_seat(cx) {
  xa = cx - FL_SHAFT;            // 机身近端（出线端，敞开）
  xb = xa + FL_L;                // 机身远端（贴挡墙）
  zf = ZC0 + FL_T / 2;           // 机身正面（贴面板）
  difference() {
    union() {
      translate([xa, SEAT_Y0, 0]) cube([xb + SEAT_WALL - xa, SEAT_BAR, ARM_T]);                       // 底部横梁
      translate([xb, SEAT_Y0, 0]) cube([SEAT_WALL, SEAT_BAR + SEAT_WALL_H, ARM_T]);                   // 远端挡墙
      translate([xa, SEAT_Y0, zf]) cube([xb + SEAT_WALL - xa, SEAT_BAR + PLATE_H, PLATE_T]);          // 正面面板
    }
    // 内角退让槽
    translate([xa - 1, FL_BOT_Y, zf]) rotate([0, 90, 0]) cylinder(d = RELIEF_D, h = FL_L + 2, $fn = 12);
    translate([xb, FL_BOT_Y - 1, zf]) rotate([-90, 0, 0]) cylinder(d = RELIEF_D, h = PLATE_H + 2, $fn = 12);
    translate([xb, FL_BOT_Y, -1]) cylinder(d = RELIEF_D, h = zf + 1.01, $fn = 12);
  }
}
module arm(i) {
  cx = -px(i);
  tip = [cx, SEAT_Y0 + SEAT_BAR / 2];
  u = tip / norm(tip);
  difference() {
    union() {
      cylinder(d = COL_D + (STYLE == "step" ? 10 : 0), h = colh(i) + ARM_T);
      translate([0, 0, colh(i)]) {
        beam([0, 0], tip, BEAM_W, ARM_T);
        fl_seat(cx);
      }
    }
    if (HORN_BOLTS) for (k = [0:3]) rotate(45 + 90 * k) translate([HORN_PCD / 2, 0, -1]) cylinder(d = HORN_HOLE, h = colh(i) + ARM_T + 2);
    translate([0, 0, -1]) cylinder(d = 6.2, h = colh(i) + ARM_T + 2);   // 舵盘中心螺丝的通孔（螺丝刀从顶上伸进去）
    translate([0, 0, colh(i) - 1]) beam(u * (COL_D / 2 + 2), [cx, SEAT_Y0 + 2], 4, 4);   // 走线槽：在臂背面（画板一侧），观众看不到
  }
}

// 打印朝向：上下翻转，让臂正面（面板）贴打印床，立柱朝上，不需要支撑
module arm_print(i) translate([0, 0, colh(i) + ARM_T]) mirror([0, 0, 1]) arm(i);

// ---------------- 装配测试件 ----------------
// 可以分开打："fit_big" 大 motor 卡槽，"fit_col" 立柱底座，"fit_small" 小 motor 托架；"fittest" = 三块一起
// 量得不准没关系：改参数、重新导出、再打，每块几分钟
module fit_big() {   // 大 motor 收纳盒的一圈（6mm 高），舵机插进去看松紧，出线口在输出轴那端
  difference() {
    translate([-(SW_W + 12) / 2, -SW_TAB_L / 2 - 3, 0]) cube([SW_W + 12, SW_TAB_L + 6, 6]);
    translate([-(SW_W + 2*CLR) / 2, -(SW_L + 2*CLR) / 2, -1]) cube([SW_W + 2*CLR, SW_L + 2*CLR, 8]);
    translate([-SW_WIRE_W / 2, 0, -1]) cube([SW_WIRE_W, SW_TAB_L, SW_WIRE_H + 1]);
    for (sx = [-1, 1], sy = [-1, 1]) translate([sy * SW_HOLE_DY / 2, sx * SW_HOLE_DX / 2, -1]) cylinder(d = 2.6, h = 8);
  }
}
module fit_col() {   // 立柱底座：试粘到舵盘上，看中心螺丝能否从孔里拧到
  difference() {
    cylinder(d = COL_D, h = 10);
    translate([0, 0, -1]) cylinder(d = 6.2, h = 12);
  }
}
module fit_small() { // 小 motor 底座（和臂末端完全一样，多带 15mm 梁），已是打印朝向：面板贴床
  translate([0, -SEAT_Y0, ARM_T]) mirror([0, 0, 1]) {
    fl_seat(0);
    translate([-BEAM_W / 2, SEAT_Y0 - 15, 0]) cube([BEAM_W, 15.01, ARM_T]);
  }
}
module fittest() {
  fit_big();
  translate([40, 0, 0]) fit_col();
  translate([85, -20, 0]) fit_small();
}

// ---------------- 预览用假零件 ----------------
module sw_dummy() {
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_L / 2, 0]) cube([SW_W, SW_L, SW_H]);
  color("dimgray") translate([-SW_W / 2, pocket_cy - SW_TAB_L / 2, SW_TAB_Z]) cube([SW_W, SW_TAB_L, 2.5]);
  color("dimgray") translate([-SW_WIRE_W / 2 + 2, pocket_cy + SW_L / 2, 0]) cube([SW_WIRE_W - 4, 3.2, 4]);   // 出线块
  color("silver") translate([0, 0, SW_H]) cylinder(d = HORN_D, h = HORN_TOP);
}
module fl_dummy(i) {
  cx = -px(i);
  color("black") translate([cx - FL_SHAFT, FL_BOT_Y, zc(i) - FL_T / 2]) cube([FL_L, FL_H, FL_T]);
  color("black") translate([cx - FL_SHAFT + FL_L / 2 - FL_TAB_SPAN / 2, FL_TAB_Y, zc(i) - FL_T / 2]) cube([FL_TAB_SPAN, 2.5, FL_T]);
  translate([cx, FL_TOP_Y, zc(i)]) rotate([-90, 0, 0]) {
    color("dimgray") cylinder(d = 11, h = FL_BOSS);
    color("silver") translate([0, 0, FL_BOSS]) cylinder(d = 4.8, h = FL_SPLINE);
    color("white") translate([0, 0, FL_ABOVE - 1.5]) cylinder(d = 7, h = 1.5);   // 舵盘轮毂
  }
}
// 轴线标记（只在预览里）：红 = 摆动轴（指向观众），绿 = 翻牌轴（沿牌的竖中线）
SHOW_AXES = true;
EXPLODE = 0;   // seatdemo 用：把舵机往画板方向拉开多少 mm
module swing_axis(i) color("red") translate([0, 0, -SW_H - HORN_TOP - 5]) cylinder(d = 1.5, h = SW_H + HORN_TOP + colh(i) + ARM_T + 35);
module flip_axis(i) color("lime") translate([-px(i), FL_BOT_Y - 10, zc(i)]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = ARM_L + CARD_H - FL_BOT_Y + 25);
module label(s, p) color("black") translate(p) linear_extrude(1) text(s, size = 7, halign = "center", valign = "center");
module card(i) {
  cx = -px(i);
  color(i == GIMMICK ? "orangered" : "white") translate([cx - CARD_W / 2, ARM_L, zc(i) - 0.15]) cube([CARD_W, CARD_H, 0.3]);
  color("gold") translate([cx - CLIP_W / 2, ARM_L - CLIP_OFF, zc(i) - CLIP_T / 2]) cube([CLIP_W, CLIP_H, CLIP_T]);   // 现成夹子（粘在舵盘上）
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

// 底座特写（只预览）：一个底座 + 小 motor + 夹子 + 牌的下半截
module seat_demo(explode = 0) {
  color("steelblue") fl_seat(0);
  color("steelblue") translate([-BEAM_W / 2, SEAT_Y0 - 20, 0]) cube([BEAM_W, 20.01, ARM_T]);
  translate([0, 0, -explode]) {
    color("black") translate([-FL_SHAFT, FL_BOT_Y, ZC0 - FL_T / 2]) cube([FL_L, FL_H, FL_T]);
    color("black") translate([-FL_SHAFT + FL_L / 2 - FL_TAB_SPAN / 2, FL_TOP_Y - FL_TAB_FROM_TOP, ZC0 - FL_T / 2]) cube([FL_TAB_SPAN, 2.5, FL_T]);
    color("orange") translate([-FL_SHAFT - 6, FL_BOT_Y + 3, ZC0 - 1]) cube([6, 2, 2.5]);   // 出线
    translate([0, FL_TOP_Y, ZC0]) rotate([-90, 0, 0]) {
      color("dimgray") cylinder(d = 11, h = FL_BOSS);
      color("silver") translate([0, 0, FL_BOSS]) cylinder(d = 4.8, h = FL_SPLINE);
      color("white") translate([0, 0, FL_ABOVE - 1.5]) cylinder(d = 7, h = 1.5);
    }
    color("gold") translate([-CLIP_W / 2, ARM_L - CLIP_OFF, ZC0 - CLIP_T / 2]) cube([CLIP_W, CLIP_H, CLIP_T]);
    color("white") translate([-CARD_W / 2, ARM_L, ZC0 - 0.15]) cube([CARD_W, 40, 0.3]);
    color("lime") translate([0, FL_BOT_Y - 8, ZC0]) rotate([-90, 0, 0]) cylinder(d = 1.2, h = ARM_L + 50 - FL_BOT_Y);
  }
}

if (PART == "layout") layout();
else if (PART == "seatdemo") seat_demo(EXPLODE);
else if (PART == "bracket") bracket();
else if (PART == "arm0") arm_print(0);
else if (PART == "arm1") arm_print(1);
else if (PART == "arm2") arm_print(2);
else if (PART == "arm3") arm_print(3);
else if (PART == "fittest") fittest();
else if (PART == "fit_big") fit_big();
else if (PART == "fit_col") fit_col();
else if (PART == "fit_small") fit_small();
