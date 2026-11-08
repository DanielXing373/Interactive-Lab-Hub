# Mouse Game 测试流程

三台 Pi 各接一个传感器，只负责把动作发到 MQTT；笔记本运行游戏主机并显示画面。

| 角色 | 硬件 | 脚本 | 环境 |
|---|---|---|---|
| 主机 | 笔记本 | `host.py` | `Lab 6/mouse_game/.venv` |
| Pi 1 瞄准 | SparkFun Qwiic Joystick | `pi_aim.py` | 同上，各自在自己的机器上建 |
| Pi 2 攻击 | VCNL4040 接近传感器 | `pi_attack.py` | 同上 |
| Pi 3 灯光 | USB 摄像头 | `pi_light.py` | 同上 |

MQTT topic：`IDD/mousegame/mouse-game/{aim,attack,light}`，broker 与 Lab 6 相同。

## 0. 一次性准备（每台 Pi，同一套命令）

```bash
cd ~/Interactive-Lab-Hub && git checkout Fall2026 && git pull
cd ~/Interactive-Lab-Hub/Lab\ 6/mouse_game
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

三台 Pi 都装这份完整依赖，用不到的包留着即可。以后每次先 `cd ~/Interactive-Lab-Hub/Lab\ 6/mouse_game && source .venv/bin/activate`。

接线后用 `i2cdetect -y 1` 确认：摇杆在 `0x20`，接近传感器在 `0x60`。

## 1. 启动主机（笔记本）

新电脑第一次使用（需要 Python 3.10+）：

```powershell
cd "Lab 6\mouse_game"
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux 用 `python3 -m venv .venv` 和 `.venv/bin/python`。之后每次启动：

```powershell
cd "Lab 6\mouse_game"
.\.venv\Scripts\python host.py
```

换端口：`$env:HOST_PORT=8080` 后再启动（macOS/Linux：`HOST_PORT=8080 python host.py`）。其他设备访问 `http://<笔记本IP>:5050`；Windows 第一次运行时防火墙弹窗要点“允许”。

浏览器打开 `http://127.0.0.1:5050`，右上角应显示 `MQTT ✓`。
只开一个 `host.py`；重启前先关掉旧窗口。

先用键盘玩一局确认画面：Enter 开始，方向键瞄准，空格攻击，O 亮度 100%，P 亮度 0%，数字 1–9 设为 10%–90%，M 开关音效。每局 30 秒、3 块奶酪；撑到 30 秒且还有奶酪就算赢（胜利音效），奶酪被偷光算输。
亮度低于 50% 时老鼠会随亮度变透明（0% 时只剩 12%），更难看清。

### 连击（击中/打空不论来自 Pi 还是键盘都计入；摇杆移动和灯光只统计 Pi 输入，`COMBO_KEYBOARD=1` 可让键盘方向键/灯光也计入）

连击数显示在分数旁边（🔥N ×倍率），右侧徽章也同步显示。

| 连击数 | 每次击中得分 |
|---|---|
| 0–4 | ×1.0 |
| 5–9 | ×1.2 |
| 10–19 | ×1.5 |
| 20 及以上 | ×2.0 |

- +1 连击：每次摇杆移动、每次击中、每次灯光跨过 50%（开灯↔关灯）。连续调亮度不跨 50% 不计。
- 清零：打空；奶酪被偷（老鼠带着奶酪逃走）；任意一台 Pi 掉线（算一次 miss）。主机自己断开 MQTT 时，所有在线 Pi 都按掉线处理。
- 背景逐渐染上粉紫色，连击 20 时最明显。

### 锤击音效与连杀（只影响声音，不影响计分）

- 连杀由主机按实际挥锤结果计算：命中 +1；连击一断就清零（打空、奶酪被偷、Pi 掉线），开新局也清零，下一击回到 D4。晕眩本身不改连杀；红老鼠每挨一锤都算一次命中；晕眩期间打中照常 +1；两次命中之间没有超时。Pi 和键盘的挥锤走同一条判定路径。声音只由主机推送的 hit/miss 事件触发，状态快照、重连、重绘不会重播。
- 每次命中 = 锤击底音（低频"咚"+极短噪声"嗒"）+ 主音 + 和声音，同时起音。D 小调五声音阶：

  | 连杀 | 主音 | 和声音 |
  |---|---|---|
  | 1 | D4 | — |
  | 2 | F4 | — |
  | 3 | G4 | D3、A3 |
  | 4 | A4 | — |
  | 5 | C5 | G3、D4、G4 |
  | 6 | D5（尾音更长） | D3、A3、F4 |

  每组结尾的 D 就是下一组开头的 D，不重复：第 7–11 击为高一个八度的 F5 G5 A5 C6 D6，第 12–16 击为高两个八度的 F6 G6 A6 C7 D7（和声同样升八度）。第 16 击是顶点：主音 D7，下面是经典的 2-4-6-˙2 D 小三和弦（D4 F4 A4 D5），垫着 D2 A2 D3 低音，再在高八度叠一层 F5 A5 D6；锤击声更重，尾音约 0.4 秒，干脆收住；之后每一击都重复这个和弦。打空后回到 D4。
- 可调：`HIT_OCTAVE_GROUPS`（升八度组数，默认 2），用环境变量设置后重启主机。
- 打空只响一声低音 F♯2（92.5 Hz）。
- 试听：游戏页面按 F12 → Console，先点一下页面激活声音，输入 `previewHits(1, 20)` 依次播放第 1–20 击。实际游戏中用键盘：方向键对准老鼠、空格挥锤。
- 主机重启后旧页面会自动刷新。每个打开的游戏标签页都会发声，测试时只开一个。
- 隐身：亮度低于 50% 时老鼠和它的进度条一起变透明（0% 时约 12% 不透明度）。
- 掉线检测：每台 Pi 连接时在 `IDD/mousegame/mouse-game/status/<aim|attack|light>` 发 `{"online": true}`，并设置遗嘱消息 `{"online": false}`；正常退出时主动发 false。keepalive 5 秒，异常断线约 7–8 秒后被发现（`PI_KEEPALIVE` 可调）。页面底部显示三台 Pi 的在线状态。

## 2. 校准（每台 Pi，各约 2 分钟）

以下命令都在 `~/Interactive-Lab-Hub/Lab 6/mouse_game` 下运行，`--calibrate` 只打印，不发消息。

**Pi 1 摇杆**：`python pi_aim.py --calibrate`
- 启动时保持摇杆居中 1 秒。
- 往右推应显示 `right`，往上推应显示 `up`。反了就加环境变量重跑：
  `JOY_INVERT_X=1 python pi_aim.py --calibrate`（或 `JOY_INVERT_Y=1`）。

**Pi 2 接近传感器**：`python pi_attack.py --calibrate`
- 记下空手读数和手靠近时的读数。默认触发 `20`（沿用 Patroller），释放 `10`。
- 不合适就改：`PROX_TRIGGER=60 PROX_RELEASE=25 python pi_attack.py --calibrate`
- 手靠近一次应只出现一次 `swing`；手收回后才能再次触发。

**Pi 3 摄像头**：`python pi_light.py --calibrate --web`
- 浏览器打开终端里打印的 `http://<pi-ip>:8000` 看画面。
- 终端每 0.5 秒打印 `openness`（0–100）和四根手指的 `ratios`。张开手应接近 100，握拳接近 0，半张开在中间；亮度变化时会打印 `SEND -> brightness N`。
- 握拳时记下 ratios 的典型值，设为 `HAND_CLOSED_RATIO`；张开时的典型值设为 `HAND_OPEN_RATIO`。例如：
  `HAND_CLOSED_RATIO=1.0 HAND_OPEN_RATIO=2.0 python pi_light.py --calibrate --web`
- 其他可调参数：`LIGHT_PUBLISH_HZ`（每秒最多发几条，默认 10）、`LIGHT_STEP`（亮度精度，默认 5%）、`LIGHT_SMOOTHING`（平滑，1.0 为不平滑）。
- 没画面就试 `CAMERA_INDEX=1`。保持摄像头周围光线充足。

## 3. 正式测试

1. 三台 Pi 去掉 `--calibrate` 运行（校准时用的环境变量照样带上）：
   - Pi 1：`python pi_aim.py`
   - Pi 2：`python pi_attack.py`
   - Pi 3：`python pi_light.py`
2. 笔记本上点 **Start**。
3. 每个设备单独检查一次，主机终端会打印 `[MQTT] aim up` 等：
   - 推一次摇杆 → 准星移动一格。
   - 手靠近一次 → 当前格出现 `🔨`。
   - 慢慢张开/合上手 → 画面亮度和 `Light N%` 连续变化，`spawn every` 秒数随之变化（0% 为 0.4 秒，100% 为 2.8 秒，线性插值；50% 为 1.6 秒）。
   - 亮度从 50% 以下升到 50% 以上（“开灯”），且显示 `Stun ready` 时 → 全屏闪一下并冻结所有老鼠。
4. 三人同时玩完整一局，然后点 **Play Again** 再玩。

### 验收清单

- [ ] 一直按住摇杆 / 手一直放在传感器前：只动一次 / 只打一次。
- [ ] 老鼠拿着奶酪逃跑时打中：分数 +1，奶酪不变。
- [ ] 眩晕只暂停读条：期间老鼠不动、读条停住、不生成新老鼠；结束后老鼠留在原地，读条从停住的位置继续（总时间顺延 1.2 秒）。眩晕本身不扣奶酪。
- [ ] 红老鼠：平均约 10 秒出现一只（7–13 秒随机，场上最多一只），要打 3 下（头顶红心显示剩余次数），偷奶酪读条 4 秒、逃跑 1.2 秒，逃走扣 1 块奶酪。每一下都得分、加连击、加连杀。眩晕同样冻结红老鼠。可调：`BOSS_INTERVAL`、`BOSS_JITTER`、`BOSS_HP`、`BOSS_CRAVE_SECONDS`、`BOSS_RETREAT_SECONDS`。
- [ ] 眩晕期间关灯再开灯：不会触发第二次眩晕。
- [ ] 冷却结束后一直开着灯：显示 `Stun ready`，但要关灯再开灯才触发。
- [ ] 亮度在 50% 以上来回变化（例如 60%↔90%）：只改变生成速度，不触发眩晕。
（“开灯”指亮度 ≥ 50%，“关灯”指 < 50%，阈值可用 `LIGHT_ON_THRESHOLD` 调整。）
- [ ] 30 秒到（赢，胜利音效）或 3 块奶酪全被偷走（输）：立即结束，排行榜新增一条。
- [ ] Pi 连续操作时连击上升、得分出现 ×1.2/×1.5/×2；打空、奶酪被偷、或拔掉一台 Pi 的网线/Ctrl+C 退出时连击清零并提示。
- [ ] 重启 `host.py` 后排行榜还在。

逻辑部分可以在笔记本上自动验证：`.\.venv\Scripts\python -m unittest test_game -v`

## 4. 没有硬件时的替代

在笔记本上模拟任意一台 Pi：
```powershell
.\.venv\Scripts\python fake_pi.py aim up
.\.venv\Scripts\python fake_pi.py attack
.\.venv\Scripts\python fake_pi.py light 30   # 亮度 0-100
.\.venv\Scripts\python fake_pi.py offline attack   # 模拟攻击 Pi 掉线
.\.venv\Scripts\python fake_pi.py listen     # 查看三个 topic 上的所有消息
```

## 常见问题

| 现象 | 处理 |
|---|---|
| 页面显示 `MQTT ✗` | 检查网络；`fake_pi.py listen` 能否连上 broker |
| Pi 打印 `offline, dropped` | Pi 未连上 broker，等待自动重连或检查 Wi-Fi |
| 摇杆方向反了 | `JOY_INVERT_X=1` / `JOY_INVERT_Y=1` |
| 一次挥手触发多次 | 提高 `PROX_TRIGGER`，降低 `PROX_RELEASE` 拉开间距 |
| 手势识别不稳定 | 补光；手离摄像头 30–60 cm；`POSE_CONFIDENCE=0.6` |
| 亮度到不了 0 或 100 | 按校准时看到的 ratios 调 `HAND_CLOSED_RATIO` / `HAND_OPEN_RATIO` |
| 亮度抖动 | 降低 `LIGHT_SMOOTHING`（如 0.3）或增大 `LIGHT_STEP`（如 10） |
| 游戏太难或太简单 | 不影响验收；如需调整可设环境变量 `SPAWN_DARK`（最暗间隔，默认 0.4 秒）和 `SPAWN_LIT`（最亮间隔，默认 2.8 秒），例如 `$env:SPAWN_DARK=0.3` 后再启动主机 |
