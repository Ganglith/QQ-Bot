# QQ AI 机器人（路线 B：个人 QQ 小号 + DeepSeek）

把你的 **QQ 小号**变成一个有「人设」的 AI，任何人私聊它、或在群里 @ 它，都能得到口语化、像真人的回复。

```
QQ 小号  <->  NapCatQQ(OneBot v11)  <->  本程序(人设/记忆/分段)  <->  DeepSeek API
  登录收发            协议端                  业务逻辑                  大模型
```

> ⚠️ **风险提示**：个人 QQ 号跑机器人属于**非官方协议**，违反腾讯用户协议，有**被冻结/限制**的风险。
> 请**务必使用小号**，不要用主号。新号建议先正常挂着养几天再用。

---

## 一、目录结构

```
qq-ai-bot/
├── main.py                    # 主程序（连 OneBot、收消息、回消息）
├── config.yaml                # 连接 / 模型 / 行为 / 记忆 配置
├── persona.md                 # ★ 人设（改这里就能改变它的性格）
├── .env.example               # DeepSeek Key 模板
├── requirements.txt
├── run.sh                     # 本地一键启动
├── docker-compose.napcat.yml  # 用 Docker 部署 NapCat
├── DEPLOY.md                  # ★ 部署到服务器的完整文档
├── BAOTA.md                   # ★ 宝塔面板部署（无 SSH 场景）
├── CARDS.md                   # ★ 角色卡获取 & 转换说明
├── FEATURES.md                # ★ 功能可行性与风险清单
├── deploy/
│   ├── install.sh             # 服务器一键部署脚本
│   └── qqbot.service          # systemd 常驻服务模板
├── tools/
│   └── card2persona.py        # 酒馆角色卡(.png/.json) -> persona.md
└── bot/
    ├── config.py              # 配置加载
    ├── llm.py                 # DeepSeek 调用（含人设热更新）
    ├── memory.py              # 私聊：每个用户的短期记忆
    ├── groupctx.py            # 群聊：整个群的最近发言上下文
    ├── summarizer.py          # 群聊「爬楼总结」
    └── splitter.py            # 长回复拆成多条（像真人连打）
```

---

## 二、准备工作

1. 一台能 7×24 运行的机器（Linux 服务器 / 挂机的 Windows 都行）。
2. 一个 **QQ 小号**（专门给机器人用，别用主号）。
3. 一个 **DeepSeek API Key**：到 <https://platform.deepseek.com> 注册 → API Keys → 创建。
4. 服务器上装好 **Docker**（推荐）或 Python 3.10+。

---

## 三、第 1 步：部署 NapCat 并登录小号

在本项目目录下：

```bash
docker compose -f docker-compose.napcat.yml up -d
docker logs -f napcat        # 查看日志
```

- 打开 WebUI：`http://<你的服务器IP>:6099/webui`
- 首次登录需要 **access token**，在日志里找 `WebUI Token`（或看 `napcat/config/webui.json`）。
- 在 WebUI 里**扫码登录你的 QQ 小号**。

> 不想用 Docker？也可以直接下载 NapCat 发行版，或用 Lagrange.Core 等其它 OneBot v11 实现，只要它对外提供「正向 WebSocket」即可。

## 四、第 2 步：开启「正向 WebSocket」

进入 NapCat WebUI → **网络配置 → OneBot11**：

- 确认 **正向 WebSocket** 已启用，端口一般是 **3001**（`ws://0.0.0.0:3001`）。
- 可以设置一个 **access token**（可选）；如果设了，就把它填到本项目的 `.env` 里。

## 五、第 3 步：配置本项目

```bash
cp .env.example .env
vi .env          # 填入 DEEPSEEK_API_KEY=sk-xxxx
```

再确认 `config.yaml` 里的 `onebot.ws_url`：

- 程序和 NapCat **同一台机器**：`ws://127.0.0.1:3001`
- 不在同一台：`ws://<NapCat的IP>:3001`

## 六、第 4 步：启动机器人

```bash
chmod +x run.sh
./run.sh
```

看到 `连接成功，开始监听消息` 就 OK 了。

不想用脚本就手动：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 七、第 5 步：测试

- 用另一个 QQ **私聊**这个小号 → 应该会收到回复。
- 把它拉进一个群，**@ 它** 或喊一句「小满」→ 也会回复。

---

## 八、部署到服务器 & 保活

> **要部署到自己的服务器？直接看 [DEPLOY.md](./DEPLOY.md)**：上传项目 → 运行 `bash deploy/install.sh`（自动装 Docker/NapCat/依赖/注册 systemd 服务）→ SSH 隧道扫码。
> 下面是最简的本地保活方式，作为补充参考。

### 保活（后台常驻）

**方式一：tmux（最省事）**

```bash
tmux new -s qqbot
./run.sh
# Ctrl+B 然后按 D 让它后台运行
```

**方式二：systemd（开机自启、崩溃自动重启）**

`/etc/systemd/system/qqbot.service`：

```ini
[Unit]
Description=QQ AI Bot
After=network.target docker.service

[Service]
Type=simple
WorkingDirectory=/path/to/qq-ai-bot
ExecStart=/path/to/qq-ai-bot/.venv/bin/python /path/to/qq-ai-bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qqbot
```

---

## 九、怎么改「人设」

直接编辑 `persona.md`，**保存即生效——不用重启**（程序每次回复前会自动检测并热更新人设）。

> 注意：只有 `persona.md` 支持热更新；改 `config.yaml`（模型、延迟、白名单等）仍需重启程序。

**想用现成的角色卡？** 网上的卡基本都是「酒馆(SillyTavern)」格式（PNG 内嵌 JSON），但你**不用装酒馆**——用项目自带的脚本一键转换：

```bash
python tools/card2persona.py 你下载的卡.png -o persona.md
# 也支持 .json 格式：python tools/card2persona.py 你下载的卡.json -o persona.md
```

去哪找卡、卡怎么用、注意事项，详见 **[CARDS.md](./CARDS.md)**。常用卡站：`chub.ai`、`aicharactercards.com`。

## 十、常用调参（`config.yaml`）

| 配置 | 作用 |
|---|---|
| `llm.temperature` | 越高越活泼像人（建议 0.9~1.3） |
| `llm.model` | `deepseek-chat`（快）/ `deepseek-reasoner`（更聪明但慢） |
| `behavior.group_need_at` | 群里是否必须 @ 才回复（**建议 true**，防刷屏） |
| `behavior.wake_words` | 群里不做 @ 也能唤醒的词 |
| `behavior.max_split` | 长回复最多拆几条发（像真人连打，建议 2~3） |
| `behavior.group_max_split` | 群里回复最多拆几条（群里更克制，建议 1~2） |
| `behavior.group_context_size` | 记住群里最近多少条消息当上下文（看得见大家在聊什么） |
| `behavior.group_context_ttl` | 群上下文保留秒数，过期清空 |
| `behavior.bot_name` | 机器人在日志/上下文里的称呼 |
| `summarize.enabled` | 是否开启群聊「爬楼总结」 |
| `summarize.keywords` | 触发总结的词（@机器人 + 说到这些词） |
| `summarize.count` | 拉取最近多少条群消息 |
| `summarize.cooldown` | 同一个群多少秒内只能总结一次（防刷） |
| `behavior.min_delay` / `delay_per_char` | 打字延迟，越大越像真人（但别太长） |
| `memory.max_turns` | 记住最近几轮对话 |
| `memory.ttl_seconds` | 多久不说话就忘掉 |

### 群聊模式（和私聊完全不一样）

机器人在群里**不是**一对一聊天，它：

1. **记录整个群的最近发言**（默认最近 30 条，见 `group_context_size`）——所以它知道"大家在聊什么"、谁说了什么，能**接着话题聊、能接梗**，而不是只会跟你一问一答。
2. 只在**被 @** 或**叫到唤醒词**时回复（`group_need_at` / `wake_words`）；其他消息只默默记进上下文，不插嘴。
3. 走**群聊专用提示词**：回复更短（≤40 字、最多 1~2 条）、不抢话、不刷屏、直接叫大家的名字。
4. 私聊则走另一套提示词，可以更放松、更贴心。

> 群上下文是内存里的环形缓冲（`group_context_size` 条、`group_context_ttl` 秒过期），**重启服务会清空**。

### 群聊「爬楼总结」

在群里 **@机器人 + 说「总结一下」**（触发词可配：`总结` / `爬楼` / `复盘` / `简报`），它就会：

1. 从 NapCat 拉取最近 `summarize.count` 条群消息（默认 200）
2. 整理成简报：**聊了什么要点** + `📌 重点`（决定/待办/约定）+ 一句话概括
3. 直接发在群里，保留换行排版

细节：

- 触发时先回一句「稍等，我爬一下楼…」，避免以为没反应
- 同一个群有 `cooldown`（默认 30 秒）防刷
- 若拉取历史失败，会**自动回退**用内存里记录的群上下文
- 图片/表情/语音等非文本消息会转成 `[图片]` `[语音]` 占位

---

## 十一、防封建议（重要）

- **只用小号**，注册后先正常养几天再上机器人。
- 不要**主动群发、主动加好友、高频刷消息**（这些最容易触发风控）。
- 别在大量群里同时高强度发言。
- 用 `behavior.whitelist` 限制只回复指定好友，风险更低。

## 十二、常见问题

| 现象 | 排查 |
|---|---|
| 一直「连接断开，重连」 | NapCat 的正向 WS 没开 / 端口不对 / 程序与 NapCat 不在同机但地址写成了 127.0.0.1 |
| 连上了但私聊不回 | `behavior.private_reply` 是否为 true；或对方在 `whitelist` 白名单外 |
| 群里不回 | 是 `@` 它了吗？`group_need_at` 是否为 true？唤醒词是否写对？ |
| 报错缺 API Key | `.env` 里 `DEEPSEEK_API_KEY` 没填或没生效 |
| `deepseek-reasoner` 报参数错 | 该模型忽略 `temperature`，可在 `config.yaml` 把 temperature 设为 1.0 |

## 十三、可以继续升级的方向

- **流式输出**：边生成边按句发送，第一条回复更快（把 `llm.py` 改成 `stream=True`）。
- **图片/语音**：NapCat 支持收发多媒体消息段，可在 `main.py` 里扩展。
- **知识库**：接 LangChain / Dify，让机器人懂你的专属资料。
- **更省心的一体化方案**：直接用 **AstrBot** 或 **LangBot**（自带 WebUI，同样接 NapCat + DeepSeek）。
