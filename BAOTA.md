# 在宝塔面板部署（Ubuntu + Docker 已装，无需 SSH）

前提：**Ubuntu 26.04**、**宝塔面板已装**、**Docker 已装**，全程在面板里操作，不用 SSH 客户端。

宝塔面板里你会用到的 4 个入口（左侧菜单）：

| 入口 | 用途 |
|---|---|
| **文件** | 上传/解压项目、编辑 `.env` |
| **Docker** | 起 NapCat 容器（也可用 Compose 模板） |
| **终端** | 执行命令（等价于 SSH，默认 root） |
| **安全** | 放行/关闭端口 |

---

## 步骤 1：上传项目

1. 在你**本地电脑**上把项目打包（**务必排除 `.venv` 和 `napcat`**，否则跨平台会出问题）：

   ```bash
   # 在项目上一级目录执行
   zip -r qq-ai-bot.zip qq-ai-bot -x "qq-ai-bot/.venv/*" -x "qq-ai-bot/napcat/*"
   ```

2. 宝塔面板 → **文件** → 进入 `/www/wwwroot/` → **上传** `qq-ai-bot.zip` → 右键 **解压**。
   最终路径：**`/www/wwwroot/qq-ai-bot`**

> ⚠️ 如果上传的包里带了 `.venv`，请先在文件管理器里**删掉它**（那是你本地电脑的 Linux/Windows 环境，不能直接用）。

---

## 步骤 2：用宝塔 Docker 管理器起 NapCat

### 方式 A：Compose 模板（推荐，纯图形化）

1. 宝塔 → **Docker** → 左侧 **Compose 模板** → **添加**。
2. 名称填 `napcat`，把下面内容整段粘贴进去，然后**部署**：

   ```yaml
   services:
     napcat:
       image: mlikiowa/napcat-docker:latest
       container_name: napcat
       environment:
         - NAPCAT_UID=0
         - NAPCAT_GID=0
       ports:
         - "3001:3001"
         - "6099:6099"
       volumes:
         - /www/wwwroot/qq-ai-bot/napcat/config:/app/napcat/config
         - /www/wwwroot/qq-ai-bot/napcat/QQ:/app/.config/QQ
       restart: unless-stopped
   ```

   > ⚠️ **不要再映射 `3000:3000`**：NapCat 的 OneBot HTTP 用不到，而你自己服务器上很可能已经有别的容器（比如 convertx、宝塔应用）占着 3000，映射了就直接端口冲突起不来。只要 **3001 + 6099** 就够。

> 若你的宝塔 Docker 管理器不识 `services:` 顶层的 Compose v2 写法，可改用 v1 旧格式：把 `services:` 这一行删掉，把 `napcat:` 顶格即可。

### 方式 B：终端

宝塔 → **终端**：

```bash
cd /www/wwwroot/qq-ai-bot
docker compose -f docker-compose.napcat.yml up -d
# 若提示没有 compose 子命令，就试： docker-compose -f docker-compose.napcat.yml up -d
```

拉镜像慢的话：宝塔 → **Docker** → **设置/配置** → 配好**镜像加速地址**，再重试。

#### ⚠️ 执行完却在 Docker 里看不到容器？按顺序排查

宝塔 → **终端**，逐条执行：

```bash
cd /www/wwwroot/qq-ai-bot
ls -l docker-compose.napcat.yml     # 1. 文件在不在当前目录
docker compose version              # 2. 有没有 compose 插件(v2)
docker-compose --version            # 3. 有没有 compose 命令(v1)，2/3 有其一即可
docker images | grep napcat         # 4. 镜像到底拉下来没有
docker ps -a                        # 5. 所有容器（含已停止）——必须带 -a
docker compose -f docker-compose.napcat.yml logs --tail=80   # 6. 容器日志
```

对照判断：

| 现象 | 含义 | 处理 |
|---|---|---|
| 第 2、3 条都提示 `not a docker command` / 未找到 | **根本没装 compose**，`up -d` 必然失败 | 安装 `docker-compose-plugin`，或改用上面「方式 A：Compose 模板」图形化部署 |
| 第 4 条查不到 napcat | **镜像没拉下来**（网络超时，up 卡在 pulling 会报错） | 配镜像加速源后重试；或先单独 `docker pull mlikiowa/napcat-docker:latest` 看具体报错 |
| 第 5 条查不到 napcat | **容器压根没创建** → up 命令其实报错了 | 重跑 `up -d`，把**完整输出**（别只看最后一行）发出来 |
| 第 5 条有 napcat，STATUS 是 `Exited` / `Restarting` | 容器起来就崩了 | 看第 6 条日志定位原因 |
| 第 5 条有 napcat，STATUS 是 `Up` | **容器正常，只是面板没刷** | 宝塔 → Docker → 容器列表点**刷新**，或切到「全部 / 已停止」筛选 |

> 补充：如果第 5 条显示 `Up` 但宝塔 Docker 管理器始终空白，检查宝塔的 Docker 模块是否连的同一个守护进程：终端执行 `docker context ls`，正常应该是 `default` 指向 `/var/run/docker.sock`；若宝塔用的是自带的 docker，重启一下面板的 Docker 模块。

---

#### 🌐 如果 `docker images | grep napcat` 是空的（镜像根本没拉下来）

国内直连 Docker Hub 基本不通，`up -d` 会卡在拉镜像并失败。**别一个个试，直接跑下面这段循环**——它会自动挑一个能用的源，并把镜像打回官方 tag（这样 compose 文件不用改）：

```bash
IMAGE=mlikiowa/napcat-docker:latest
for P in \
  swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io \
  docker.m.daocloud.io \
  docker.1ms.run \
  docker.1panel.live \
  hub.rat.dev \
  docker.kejilion.pro \
  dockerproxy.net ; do
  echo "===== 尝试 $P ====="
  if docker pull "$P/$IMAGE"; then
    docker tag "$P/$IMAGE" "$IMAGE"
    echo ">>> 成功：$P"
    break
  fi
done
docker images | grep napcat
```

> 报 `502` / `429` / 超时 都是**镜像站自己**的毛病，跟你的服务器无关，换个源就行。
> 华为云那个源（`swr.cn-north-4.myhuaweicloud.com`）对国内机器通常最稳，优先试它。

拉成功后起容器：

```bash
docker compose -f docker-compose.napcat.yml up -d
docker ps | grep napcat
```

想一劳永逸：宝塔 → **Docker** → **设置/配置** → 配好 `registry-mirrors` 加速地址，之后 `docker pull` 自动走加速。

---

## 步骤 3：登录 QQ 小号（无 SSH 的关键一步）

没有 SSH 隧道，就用「**临时开放端口 + 强 token**」这一招：

1. 宝塔 → **安全** → 放行端口 **6099**（顺便可放行 3000，3001 不需要）。
2. 宝塔 → **终端**，拿到 WebUI 登录 token：

   ```bash
   docker logs napcat 2>&1 | grep -i -A2 token
   ```

3. 浏览器打开：`http://<你的服务器IP>:6099/webui`，输入上一步的 token 登录。
4. **扫码登录你的 QQ 小号**。
5. 登录成功后，**立刻回宝塔 → 安全 → 删除 6099 的放行规则**（很重要，别让 WebUI 长期暴露在公网）。

> 也可以直接在终端看二维码字符画：`docker logs -f napcat`，但不好扫，还是用 WebUI 靠谱。

> ✅ **登录成功后**：WebUI 顶部会显示机器人 QQ 号和在线状态；也可 `docker logs --tail=20 napcat` 看登录日志。
> ⚠️ **没登录 QQ 时最容易踩的坑**：容器照样 `Up`、WebSocket 也"连接成功"，但**不会有任何消息事件**，机器人看起来像坏了。**「连接成功却收不到消息」九成是这个原因**——先去 NapCat WebUI 确认账号已登录。

#### 🚨 打开 6099 显示「未发送任何数据 / ERR_EMPTY_RESPONSE」

含义：**宿主机的端口映射在，但容器里 6099 没有服务在监听**（不是防火墙问题）。

```bash
docker ps | grep napcat                  # 状态是 Up 还是 Restarting
docker logs napcat --tail=150            # 看有没有报错
docker logs napcat 2>&1 | grep -i webui  # 关键：日志会打印真实端口 + token
curl -v http://127.0.0.1:6099/webui      # 在服务器本机测（本机都不通就是容器问题）
```

| 原因 | 处理 |
|---|---|
| 首次启动还没就绪 | 等 1~2 分钟再刷新 |
| 容器内 6099 被占，**WebUI 自动 +1** → 映射错位 | 以日志里 `WebUi User Panel Url: http://127.0.0.1:xxxx/webui?token=` 的**真实端口**为准 |
| 主进程崩了、容器在反复重启 | 看日志报错 |
| 想一次到位 | 按下面「干净重建」 |

**干净重建**（你还没登录过 QQ，删掉数据目录是安全的）：

```bash
docker rm -f napcat
rm -rf /www/wwwroot/qq-ai-bot/napcat
docker run -d --name napcat --restart=unless-stopped \
  -e MODE=ws \
  -e WEBUI_TOKEN='自己设一个强随机密码' \
  -e NAPCAT_UID=0 -e NAPCAT_GID=0 \
  -p 3001:3001 -p 6099:6099 \
  -v /www/wwwroot/qq-ai-bot/napcat/config:/app/napcat/config \
  -v /www/wwwroot/qq-ai-bot/napcat/QQ:/app/.config/QQ \
  mlikiowa/napcat-docker:latest
docker logs -f napcat
```

> `MODE=ws` 是官方推荐值（启用正向 WebSocket，正好给本机器人用）；
> `WEBUI_TOKEN` 只在**配置缺失时**初始化，所以重建前要先删 `napcat/` 目录才会生效。
> 然后访问 `http://你的IP:6099/webui`，用你设的 `WEBUI_TOKEN` 登录。

#### 🌍 服务器本机 curl 正常、但外网还是打不开

说明容器没问题，是「**外网 → 6099**」这段被拦住了。**两个地方都要放行，缺一不可**：

1. 宝塔 → **安全** → 放行端口 `6099`
2. **云服务器安全组**（华为云/腾讯云/阿里云控制台里的「安全组 / 入方向规则」）→ 放行 TCP `6099`

> ⚠️ **宝塔只管系统防火墙，管不到云安全组**——这是最常被漏掉的一步。华为云默认安全组一般只开 22/80/443。

在**你自己的电脑**上验证是否通（不是在服务器上）：

```bash
# Mac / Linux
nc -vz 106.13.29.146 6099
# Windows PowerShell
Test-NetConnection 106.13.29.146 -Port 6099
```

通了再访问（**记得带 `/` 和 token**）：

```
http://106.13.29.146:6099/webui/?token=你的token
```

#### 🔌 建立 OneBot 正向 WebSocket（机器人能不能连上就看这步）

NapCat 默认**不建任何 WebSocket 服务**，所以必须手动加一个：

NapCat WebUI → **网络配置** → 切到 **「Websocket服务器」** 标签 → **新建**：

| 字段 | 填什么 |
|---|---|
| 名称 | 随意，如 `ws` |
| 启用 | ✅ |
| Host / 地址 | `0.0.0.0` |
| 端口 | `3001` |
| Token | 留空；若填了，必须同步到 `.env` 的 `ONEBOT_ACCESS_TOKEN` |
| 消息格式 | `array`（默认，不要改） |

> ⚠️ 选 **「Websocket服务器」**（正向，机器人来连它），**不要**选「Websocket客户端」（反向，逻辑相反）。

> 💡 **主机必须是 `0.0.0.0`，不能是 `127.0.0.1`**：NapCat 在容器里，只监听回环的话宿主机的端口映射转发不进去，机器人会一直报 `did not receive a valid HTTP response`。
> WebUI 改不动就直接改配置文件：
> ```bash
> sed -i 's#"host": *"127.0.0.1"#"host": "0.0.0.0"#' /www/wwwroot/qq-ai-bot/napcat/config/onebot11_*.json
> docker restart napcat
> ```
> 兜底方案：重建容器时加 `--network host`，容器内 `127.0.0.1` 即等于宿主机。

保存后机器人 5 秒内自动重连，**无需重启机器人**；日志出现 `连接成功，开始监听消息` 即成功。若没生效：`docker restart napcat`。

---

## 步骤 4：配置 DeepSeek Key

宝塔 → **文件** → 进入 `/www/wwwroot/qq-ai-bot`：

1. 复制 `.env.example` → 重命名为 `.env`（右键复制/粘贴后改名）。
2. 双击 `.env` 编辑，填入：

   ```
   DEEPSEEK_API_KEY=sk-你的key
   ```

保存。

---

## 步骤 5：跑机器人（两种方式，选一个）

### 方式 A：终端 + systemd（脚本一键）

宝塔 → **终端**：

```bash
cd /www/wwwroot/qq-ai-bot
bash deploy/install.sh
```

脚本会自动：跳过 Docker 安装 → 建 `.venv` → 装依赖 → 注册 `systemd` 服务并启动。

常用命令：

```bash
systemctl status qqbot          # 状态
journalctl -u qqbot -f          # 实时日志
systemctl restart qqbot         # 只有改了 config.yaml 才需要重启
```

> 💡 **改人设不用重启**：直接编辑 `persona.md` 保存，下一条消息就生效（程序会自动热更新）。

### 方式 B：宝塔「Python 项目」（纯图形化守护）

如果你不想碰 systemd，用宝塔自带的守护：

1. 宝塔 → **网站** → **Python 项目** → **添加项目**。
2. 项目路径：`/www/wwwroot/qq-ai-bot`
3. Python 版本：3.10 及以上（没有就在面板里装一个）
4. 启动方式/框架：选 **其他 / 自定义命令**
5. 启动命令：`python main.py`（或 `.venv/bin/python main.py`）
6. 依赖文件：`requirements.txt`（面板会帮你装）
7. 保存并启动，确认已开启**守护/常驻**。

> 两种方式**只选一个**，别同时开（会导致重复回复）。

---

## 步骤 6：验证

1. `journalctl -u qqbot -f` 看到 `连接成功，开始监听消息`。
2. 用**另一个 QQ** 私聊这个小号 → 有回复即成功。
3. 拉进群 → `@` 它 或 喊「小满」→ 有回复。

---

## 安全清单

- ✅ 3001、3000 **不要**对公网放行（容器与本机通信即可）。
- ✅ 6099 只在**扫码时临时放行**，扫完就关。
- ✅ `.env` 含 API Key，不要放进网站公开目录，也不要提交 git。
- ✅ 宝塔面板本身端口别用默认，开好面板密码/二次验证。

---

## 「发消息不回复」排查顺序（从上到下，逐条确认）

```bash
# 1. 机器人服务到底在不在运行？（跑过探针停掉忘了启动，最常见）
systemctl status qqbot --no-pager | head -8
#    不在运行 → systemctl start qqbot

# 2. NapCat 里的 QQ 登录了吗？
docker logs --tail=30 napcat
#    没有登录日志 / 掉线 → 去 WebUI 扫码登录

# 3. 停掉机器人，跑探针，用【另一个 QQ】发消息，看事件有没有到
systemctl stop qqbot
cd /www/wwwroot/qq-ai-bot && ./.venv/bin/python tools/probe.py
#    —— 测完务必启动回来 ——
systemctl start qqbot
```

对照结果：

| 现象 | 结论 | 处理 |
|---|---|---|
| 第 1 步显示 `inactive` / `failed` | 服务没跑 | `systemctl start qqbot`，再看 `journalctl -u qqbot -n 50` |
| 第 2 步没有登录成功记录 | QQ 没登录 / 掉线 | NapCat WebUI 重新扫码 |
| 第 3 步发消息后**没有** `>>> 收到消息事件` | 消息没到 NapCat | 确认是发给**机器人小号**、用**另一个 QQ** 发、双方是好友 |
| 第 3 步**有** `>>> 收到消息事件`，但机器人不回 | NapCat 正常，是机器人逻辑 | 把探针输出 + `journalctl -u qqbot -n 50` 发给开发者 |

---

## 宝塔常见问题

| 现象 | 解决 |
|---|---|
| `docker compose` 不认 | 用 `docker-compose`（v1），或在 Docker 管理器里用 Compose 模板 |
| 拉 NapCat 镜像超时 | 宝塔 Docker 设置里配镜像加速源后重试 |
| `install.sh` 卡在装依赖 | 面板 Python 版本太老，装个 3.10+，或先 `apt-get install -y python3-venv` |
| 机器人起来就退出 | 终端 `journalctl -u qqbot -n 100` 看报错，多半是 `.env` 的 Key 没填对 |
| 上传的包里有 `.venv` | 删掉它，让 `install.sh` 重新创建 |
| 一直「连接断开：`did not receive a valid HTTP response`」 | NapCat 的**正向 WebSocket 没启用**（端口映射在、但容器里没服务在听 3001）。去 NapCat WebUI → **网络配置 → OneBot11** → 开启「**WebSocket 服务**（正向）」，host `0.0.0.0`、端口 `3001` → 保存。机器人会在 5 秒内自动重连，**不用重启机器人** |
| 换人设要在 NapCat 面板里操作吗？ | **不用也不能**。NapCat 只管 QQ 协议（登录/网络/日志），人设属于机器人程序。改项目根目录的 **`persona.md`** 即可（宝塔「文件」双击编辑，**保存即生效、不用重启**）。想要网页里改人设，就得换 AstrBot / LangBot 这类自带 WebUI 的框架 |
| 连接成功但发消息不回复 | 一边发消息一边看 `journalctl -u qqbot -f`：**没有任何输出** = 消息没到机器人（群里必须 **@它或叫唤醒词**，或把 `behavior.group_need_at` 改 false；私聊要发给**机器人小号**）；**输出 `调用大模型失败`** = DeepSeek 报错（key/余额/模型名）；**输出 `[private:xx] … -> …`** 但对方没收到 = NapCat 发送被拒，查 `docker logs --tail=50 napcat` |
| `ModuleNotFoundError: No module named 'websockets'` | 依赖没装上（`pip install` 失败多半是网络）。用国内源重装：`./.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt` |
| 重启服务器后机器人没起来 | `systemctl is-enabled qqbot` 应为 `enabled`；NapCat 容器已带 `restart: unless-stopped` 自启 |
| 登录后那个 QQ 还能正常用吗 | **手机端可以同时在线**（不影响）；但**电脑端再登会顶掉 NapCat**（NapCat 用的就是电脑端协议）。也**不建议当日常号用**：机器人会自动回复该号收到的所有私聊，会和你手动回消息打架。手机端登着别聊天、只用来收验证码就最好 |
| 忘了 WebUI token / token 登不进去 | 读配置最可靠：`cat /www/wwwroot/qq-ai-bot/napcat/config/webui.json`（看 `token` 字段）。也可 `docker logs napcat 2>&1 \| grep -i token`（**只在启动时打印一次**）。注意：**扫码登录 QQ 后 token 会刷新**，以 `webui.json` 里的为准 |
| 机器人能联网搜索吗？ | 默认**不能**，只调用 DeepSeek 对话接口（模型本身不联网）。可以加：用 **function calling** 接一个搜索后端（SearXNG 自建免费 / 博查 API），只在需要时自动联网并给出来源 |

---

## 多人协作改人设（把 bot 分享给朋友）

> ⚠️ **先澄清一个常见误解**：如果给朋友开的是 **NapCat 面板**（6099），那是**没用的**——NapCat 只管 QQ 协议（登录 / 网络配置 / 日志），**没有文件管理，也看不到你项目里的 `persona.md`**。人设属于机器人程序，必须用下面任一种方式给他。

**另外：宝塔免费版不支持「只把某个文件夹授权给另一个面板用户」。** 你有两条可行路径：

### 路径 A：朋友已有面板权限 → 他现在其实就能改

宝塔 → **文件** → `/www/wwwroot/qq-ai-bot/` → 双击 `persona.md` → 编辑保存。**保存即生效**，不用重启。

### 路径 B：只想开放这一个目录（推荐）

**不要给整台服务器的面板权限**——面板 = 能看到你所有站点、数据库，还有能执行 root 命令的终端。改用 **FTP 只暴露这一个文件夹**：

1. 宝塔 → **FTP** → 添加 FTP
2. 用户名 / 密码自定
3. **根目录填 `/www/wwwroot/qq-ai-bot`**
4. 权限给「读写」
5. 朋友用 FileZilla / WinSCP 连，**只能看到这个目录**，直接改 `persona.md`

### 注意事项

- ⚠️ **权限**：FTP 是独立系统用户，改完文件属主可能变，注意别让它误删 `.venv` / `napcat`。`persona.md` 是热更新的，改完即生效。
- ⚠️ **冲突**：两人同时编辑 `persona.md` 会互相覆盖（没有版本管理）。建议轮流改，或用 git。
- 💡 **更干净的方案**：给 bot 加一个「小型网页人设编辑器」（带密码，只改 `persona.md`），朋友浏览器打开链接就能改，**完全不用给服务器权限**。
