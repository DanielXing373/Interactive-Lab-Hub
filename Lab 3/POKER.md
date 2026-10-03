# 德州语音：Pi 是玩家

代码在 `speech-scripts/poker_player.py`。你负责发牌和翻牌。Pi 坐在对面，听你说话，再决定自己的行动。

在这台电脑上先用键盘测，不用麦克风：

```powershell
cd "C:\Workspace\Projects\Interactive-Lab-Hub\Lab 3\speech-scripts"
python poker_player.py --text
```

每句话后面多看一行内部状态：

```powershell
python poker_player.py --text --trace
```

把下面的案例全部自动跑一遍：

```powershell
python poker_player.py --check
```

`quit` 退出文字模式。Pi 上接麦克风时，在 `speech-scripts` 里激活 `.venv` 后直接运行 `python poker_player.py`。下注时的静音阈值是 1.2 秒。

文字模式和麦克风模式都会把对话写进 `Lab 3/transcripts/`。`session.txt` 是这一整场，从打招呼开始。每一手发牌到结束，另存一份 `hand_001.txt`、`hand_002.txt`。一手的文件从 `deal` 记到这手结束，里面有每一句当时的阶段。设筹码那些话在 `session.txt` 里，不在这一手的文件里。

## 两层记忆

一整场都活着的，不放进状态枚举：

| 字段 | 含义 | 默认 |
|---|---|---|
| `small_blind` | 小盲 | 10 |
| `big_blind` | 大盲 | 20 |
| `chips["human"]` | 你的筹码 | 还没说之前是空的 |
| `chips["pi"]` | Pi 的筹码 | 还没说之前是空的 |

每一手结束只改筹码。盲注不变，除非你在两手之间重新说。

这一手才有的：当前阶段、底池、Pi 的两张底牌、公共牌、这一条街双方已经投入的筹码。

`alt_personality` 是第二个人格的开关，默认 `False`。两套台词现在指向同一段文字。底牌和胜率无论开关开没开都说真话。

## 状态

```text
idle → preflop → flop → turn → river → showdown → idle
                ↘ await_amount
                ↘ await_confirm
```

单挑位置是固定的：你是按钮，下小盲，翻牌前先行动。Pi 下大盲，翻牌后先行动。

| 阶段 | 在等什么 |
|---|---|
| `idle` | 盲注、双方筹码、`deal` |
| `preflop` / `flop` / `turn` / `river` | 你的行动，或下一条街的牌 |
| `await_amount` | 一个数字。问题可以插进来，问完还停在这里 |
| `await_confirm` | 你重说一个数字，或说 `no` |
| `showdown` | `you win`、`I win` 或 `split` |

这些问题在每个阶段都是回到自己的边，不改筹码、不改阶段：

- 多少筹码
- 桌上有什么牌
- 你有什么牌
- 胜率多少
- 底池多少
- 你在等什么 / 下一步是什么（`what are you waiting for`、`what's next`、`where are we`）

麦克风模式里，Pi 说话时会屏蔽听筒，并丢掉刚说完后一小段回声。发牌之后它会明确说自己在等两张底牌，并让你慢慢来。

## 一句话怎么读

先看是不是问题。是问题就只回答，不去抓里面的数字。所以 `how many chips do you have if the bet is 50` 不会把 50 写进底池。

然后才看行动。数字必须跟这一下动作绑在一起：

| 你说的话 | 用哪个数 |
|---|---|
| `I raise your 20 to 50` | `to` 后面的 50。前面的 20 丢掉 |
| `I raise` | 没有数字，进入 `await_amount` |
| `I raise 40 or 50` | 两个数又没有 `to`，先问你是哪一个，筹码不动 |
| `I call 5` | 该跟的不是 5，就拒绝，不扣筹码 |
| `your cards are the ten of spades and the seven of hearts` | `ten` 是牌点，因为后面有花色 |

报牌必须带花色，例如 `ace of spades`。没有花色的 `two` 会被当成筹码。

你说没听清时，Pi 把上一句原话再说一遍，阶段和筹码都不变。听得懂的说法包括 `what did you say`、`say that again`、`pardon`、`repeat`，以及 `没听清`、`再来一遍`、`再说一遍`。它还没说过话时，回答 `I have not said anything yet.`

## 同一句问题，不同阶段的说法

| 问题 | `idle` | 一手牌进行中 | 筹码已经是 0 |
|---|---|---|---|
| 你有多少筹码 | `I have 1500 chips. Blinds are 10 and 20.` | `I have 1480 chips. The pot is 30.` | `I am all in. The pot is 80.` |
| 桌上有什么牌 | `There are no community cards yet.` | `The board is ace of hearts, king of diamonds, seven of clubs.` | 同左 |
| 你有什么牌 | `You have not told me my cards.` | `I have ace of spades and king of hearts.` | 同左，照实说 |
| 胜率 | `Tell me my cards before I can estimate.` | `About 61 percent against a random hand.` | 同左 |

胜率是 Pi 自己算的：拿它的底牌和已知公共牌，对一手随机的对手牌做 200 次发牌。平分算半个赢。同一副牌每次报的百分比相同。它说的是相对随机手牌，不是看见了你的牌。

## Pi 自己怎么行动

翻牌前你先说。你 `call` 之后，大盲还有一次选择，Pi 才会行动。翻牌、转牌、河牌由 Pi 先行动，所以你报完牌，它的回答里就带着 check 或 bet。

| 局面 | 胜率 | Pi 说 |
|---|---|---|
| 没人下注 | 低于 50% | `I check.` |
| 没人下注 | 至少 50% | `I bet` 底池的一半，并且至少一大盲 |
| 面对下注 | 低于 40% | `I fold.` |
| 面对下注 | 40% 到 65% | `I call.` |
| 面对下注 | 至少 65% | `I raise to ...`，加注额至少一大盲 |
| 跟注会把 Pi 打空，胜率低于 45% | | `I fold.` |
| 跟注会把 Pi 打空，胜率至少 45% | | `I call all in.` |
| 大盲已经跟平，Pi 还没表态 | 低于 65% | `I check.` |
| 大盲已经跟平，Pi 还没表态 | 至少 65% | `I raise to ...` |

## 测试案例

下面每一张表都是从头开始的一段对话。你打左边，Pi 应回答右边。`--check` 锁的就是这些句子。

### 1. 还没开局

| 你说 | Pi 说 |
|---|---|
| `how many chips do you have` | Tell me both stacks first. |
| `what is on the board` | There are no community cards yet. |
| `what cards do you have` | You have not told me my cards. |
| `what is your win rate` | Tell me my cards before I can estimate. |
| `I fold` | There is no hand. Say deal to start. |
| `blinds are 10 and 20` | Blinds are 10 and 20. |
| `you have 1500` | I have 1500 chips. |
| `I have 1500` | You have 1500 chips. |
| `how many chips do you have` | I have 1500 chips. Blinds are 10 and 20. |
| `how many chips do I have` | You have 1500 chips. Blinds are 10 and 20. |

非法的盲注和筹码：

| 你说 | Pi 说 |
|---|---|
| `blinds are 20 and 10` | The big blind has to be larger than the small blind. |
| `blinds are five` | Tell me the small blind and the big blind. |
| `you have 5` | A stack has to cover at least the big blind. |
| `you have 1500` | I have 1500 chips. |
| `deal` | Tell me both stacks first. |

不说盲注也可以发牌，这时用默认的 10 和 20。

### 2. 数字槽

`ten of spades` 不能变成 10 个筹码。问题里的 50 也不能变成下注。没说金额的 raise 会停住；中途提问之后，筹码还是 1480，底池还是 30。

| 你说 | Pi 说 |
|---|---|
| `you have 1500` | I have 1500 chips. |
| `I have 1500` | You have 1500 chips. |
| `deal` | New hand. You post 10. I post 20. I am waiting for my two hole cards. Take your time. |
| `your cards are the ten of spades and the seven of hearts` | I have ten of spades and seven of hearts. Your action. |
| `what is the pot` | The pot is 30. |
| `how many chips do you have if the bet is 50` | I have 1480 chips. The pot is 30. |
| `I check` | You cannot check. It is 10 to call. |
| `I raise your 20 to 50` | You raise to 50. … |

最后一句的 20 被丢掉，Pi 的记录里你这条街投入的是 50，不是 20。后面的省略号是 Pi 根据胜率做的自己的行动。

口袋对 A 会把没写金额的 raise 问清楚。提问不会把阶段弄丢：

| 你说 | Pi 说 |
|---|---|
| `deal` 之前同样先各设 1500 | |
| `your cards are the ace of clubs and the ace of diamonds` | I have ace of clubs and ace of diamonds. Your action. |
| `I raise` | Raise to how many? |
| `what cards do you have` | I have ace of clubs and ace of diamonds. I still need the amount. |
| `how many chips do you have` | I have 1480 chips. The pot is 30. I still need the amount. |
| `fifty` | You raise to 50. I raise to 85. |

两个数，又没有 `to`：先问，`no` 之后底池仍是 30。下一句用 `to` 绑定 50。

| 你说 | Pi 说 |
|---|---|
| `your cards are the ace of clubs and the king of diamonds` | I have ace of clubs and king of diamonds. Your action. |
| `I raise 40 or 50` | Do you mean 40 or 50? Say the amount again. |
| `what is the pot` | The pot is 30. Say the amount again. |
| `no` | Cancelled. Say the action again. |
| `I raise your twenty to fifty` | You raise to 50. I raise to 85. |

在等金额时说 `I fold`，这一手结束，底池按还没加注之前结算：`You fold. I take the pot of 30.`

### 3. 非法行动和发牌顺序

| 你说 | Pi 说 |
|---|---|
| `your cards are the ace of spades` | Tell me exactly two cards. |
| `your cards are the ace of spades and the ace of spades` | A card cannot appear twice. |
| `your cards are the ace of spades and the king of hearts` | I have ace of spades and king of hearts. Your action. |
| `I check` | You cannot check. It is 10 to call. |
| `I raise to 30` | A raise must be to at least 40. |
| `I call 5` | It is 10 to call. |
| `I check and raise` | Say one action: fold, check, call, bet, or raise. |
| `I call` | You call. I check. I am waiting for the flop. Take your time. |
| `turn is the two of spades` | The turn does not come now. |
| `flop is the two of clubs and the three of diamonds` | The flop needs three cards. |
| `flop is the ace of spades, the four of diamonds, and the five of clubs` | That card is already out. |
| `blinds are 50 and 100` | Finish this hand before changing the blinds. |
| `you have 900` | Stacks are already in this hand. |

翻牌前还没告诉 Pi 底牌就报 flop：`Tell me my cards first.` 这一手还没打完就说 `deal`：`Finish this hand before the next deal.`

### 4. 一条打完的牌，以及筹码留到下一手

7♥2♣ 翻牌前低于 65%，所以你跟注之后 Pi 会 check。A-K-Q 的牌面它继续 check。摊牌时胜率句子会变成大约 9%。

| 你说 | Pi 说 |
|---|---|
| `you have 200` | I have 200 chips. |
| `I have 200` | You have 200 chips. |
| `deal` | New hand. You post 10. I post 20. I am waiting for my two hole cards. Take your time. |
| `your cards are the seven of hearts and the two of clubs` | I have seven of hearts and two of clubs. Your action. |
| `I call` | You call. I check. I am waiting for the flop. Take your time. |
| `flop is the ace of spades, the king of diamonds, and the queen of clubs` | The board is ace of spades, king of diamonds, queen of clubs. I check. |
| `I check` | You check. I am waiting for the turn. Take your time. |
| `turn is the three of hearts` | The board is ace of spades, king of diamonds, queen of clubs, three of hearts. I check. |
| `I check` | You check. I am waiting for the river. Take your time. |
| `river is the nine of clubs` | The board is ace of spades, king of diamonds, queen of clubs, three of hearts, nine of clubs. I check. |
| `I check` | You check. Showdown. Tell me who won. |
| `what is your win rate` | About 9 percent against a random hand. |
| `what is on the board` | The board is ace of spades, king of diamonds, queen of clubs, three of hearts, nine of clubs. |
| `deal` | Tell me who won before the next deal. |
| `I win` | You take the pot of 40. |
| `how many chips do you have` | I have 180 chips. Blinds are 10 and 20. |
| `how many chips do I have` | You have 220 chips. Blinds are 10 and 20. |
| `deal` | New hand. You post 10. I post 20. I am waiting for my two hole cards. Take your time. |
| `your cards are the ace of clubs and the ace of diamonds` | I have ace of clubs and ace of diamonds. Your action. |
| `I fold` | You fold. I take the pot of 30. |

同一条街用 `split` 结束时，底池 40：`Split. You take 20. I take 20.` 如果底池是奇数，多出来的 1 个筹码给你。这句是 `Split. You take 16. I take 15. You take the odd chip.`

### 5. 全下，以及 Pi 自己弃牌

双方各 40。你加到 40 会把两个人都打空。之后翻牌不再问行动，只收牌，直到摊牌。

| 你说 | Pi 说 |
|---|---|
| `you have 40` | I have 40 chips. |
| `I have 40` | You have 40 chips. |
| `deal` | New hand. You post 10. I post 20. I am waiting for my two hole cards. Take your time. |
| `your cards are the ace of spades and the ace of hearts` | I have ace of spades and ace of hearts. Your action. |
| `I raise to 40` | You raise all in. I call all in. I am waiting for the flop. Take your time. |
| `how many chips do you have` | I am all in. The pot is 80. |
| `flop is the two of clubs, the three of diamonds, and the four of hearts` | The board is two of clubs, three of diamonds, four of hearts. I am waiting for the turn. Take your time. |
| `turn is the five of spades` | The board is two of clubs, three of diamonds, four of hearts, five of spades. I am waiting for the river. Take your time. |
| `river is the nine of clubs` | The board is two of clubs, three of diamonds, four of hearts, five of spades, nine of clubs. Showdown. Tell me who won. |
| `you win` | I take the pot of 80. |

7♥2♣ 面对大加注会弃牌：

| 你说 | Pi 说 |
|---|---|
| 各 1500，发牌，底牌 `seven of hearts` 和 `two of clubs` | Your action. |
| `I raise to 80` | You raise to 80. I fold. You take the pot of 100. |

翻牌后最小下注是一个大盲。金额太小就整手拒绝，不会扣掉那 10 个筹码。

| 你说 | Pi 说 |
|---|---|
| 7♥2♣，你 `I call`，翻牌 A-K-Q | Pi check |
| `I bet` | Bet how many? |
| `I bet 10` | The minimum bet is 20. |
| `I fold` | You fold. I take the pot of 40. |

口袋对 A 在你只是跟注时会加注：`You call. I raise to 40.`
