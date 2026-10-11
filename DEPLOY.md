# 部署到你的服务器

目标：把 `qq-ai-bot` 跑到你的服务器上，7×24 常驻，QQ 小号一直在线当 AI。

> 🅱 **用宝塔面板、且不方便用 SSH 客户端？直接看 [BAOTA.md](./BAOTA.md)**（本文是通用 Linux/SSH 流程）。

---

## 0. 服务器要求

| 项 | 建议 |
|---|---|
| 系统 | Linux（Ubuntu 22.04 / Debian 12 最省心），Windows 也行见文末 |
| 配置 | **1 核 2G 内存** 起步（NapCat 跑 QQ 客户端比较吃内存） |
| 网络 | 只需**能出网**（连 DeepSeek、登 QQ）。**不需要**对外开放 3001 端口 |
| 软件 | Docker（脚本会帮装）、Python 3.10+ |

> NapCat 本质是在服务器上跑一个 QQ 客户端，**至少 1G 内存**，1 核 1G 的小鸡可能不够。

---

## 1. 把项目传到服务器

**方式 A：本地打包上传（推荐，简单）**

在你自己的电脑上，进入项目**上一级目录**执行：

```bash
# 打包（自动排除 .venv 等）
zip -r qq-ai-bot.zip qq-ai-bot -x "qq-ai-bot/.venv/*" -x "qq-ai-bot/napcat/*"

# 上传到服务器
scp qq-ai-bot.zip <用户>@<服务器IP>:~/
```

然后登录服务器解压：

```bash
ssh <用户>@<服务器IP>
unzip -q qq-ai-bot.zip -d ~/ && cd ~/qq-ai-bot
```

**方式 B：git（如果你已经推到仓库）**

```bash
git clone <你的仓库地址> qq-ai-bot && cd qq-ai-bot
```

---

## 2. 一键部署

```bash
bash deploy/install.sh
```

这个脚本会自动做：

1. 检测/安装 Docker
2. 用 `docker-compose.napcat.yml` 启动 NapCat 容器
3. 创建 `.venv` 并安装 Python 依赖
4. 检查 `.env`（没有就生成模板并暂停，让你填 Key）
5. 注册 `systemd` 服务并启动（开机自启 + 崩溃自动重启）

> 第一次运行会在第 4 步停下，让你填 DeepSeek Key。填完再跑一次即可：
> ```bash
> vi .env            # 填入 DEEPSEEK_API_KEY=sk-xxxx
> bash deploy/install.sh
> ```

### 手动部署（不用脚本）

```bash
# 1) 起 NapCat
docker compose -f docker-compose.napcat.yml up -d

# 2) Python 环境
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) 配置
cp .env.example .env && vi .env     # 填 DEEPSEEK_API_KEY

# 4) 注册服务
sudo cp deploy/qqbot.service /etc/systemd/system/qqbot.service
sudo sed -i "s#__PROJECT_DIR__#$PWD#g" /etc/systemd/system/qqbot.service
sudo systemctl daemon-reload && sudo systemctl enable --now qqbot
```

---

## 3. 扫码登录 QQ 小号

NapCat 的 WebUI 监听在服务器的 `6099` 端口。**安全起见不要把它暴露到公网**，用 SSH 隧道访问：

在**你自己的电脑**上执行：

```bash
ssh -L 6099:127.0.0.1:6099 <用户>@<服务器IP>
```

保持这个 SSH 窗口不要关，然后本地浏览器打开：

```
http://127.0.0.1:6099/webui
```

- 首次需要 **access token**：在服务器上执行 `docker logs napcat | grep -i token`，或查看 `napcat/config/webui.json`。
- 进入后**扫码登录你的 QQ 小号**（用手机 QQ 扫）。
- 顺便在 **网络配置 → OneBot11** 里确认 **正向 WebSocket 端口是 3001**（和 `config.yaml` 里一致）。

> 如果你确实要从公网访问 WebUI，请务必改默认 token 并加防火墙白名单，**扫码页面泄露 = 别人能登你的号**。

---

## 4. 验证

```bash
# 看机器人日志
sudo journalctl -u qqbot -f

# 看 NapCat 日志
docker logs -f napcat
```

看到 `连接成功，开始监听消息` 后，用**另一个 QQ** 私聊这个小号，收到回复即成功。

---

## 5. 日常运维

```bash
# 查看状态
sudo systemctl status qqbot

# 重启机器人（比如改完 persona.md 后）
sudo systemctl restart qqbot

# 停止 / 启动
sudo systemctl stop qqbot && sudo systemctl start qqbot

# 看最近 200 行日志
sudo journalctl -u qqbot -n 200
```

**更新代码后**：

```bash
cd ~/qq-ai-bot
git pull                       # 或重新上传文件
./.venv/bin/pip install -r requirements.txt
sudo systemctl restart qqbot
```

**改人设**：直接编辑 `persona.md`，**保存即生效，无需重启**（`persona.md` 已支持热更新；改 `config.yaml` 才需要 `systemctl restart qqbot`）。

---

## 6. 防火墙 / 安全清单

- ✅ 只需要放行 **SSH(22)**；3001/3000 **不用**对公网开放（本机通信）。
- ✅ 6099 建议**只走 SSH 隧道**；若必须公网开放，改掉默认 token + 加 IP 白名单。
- ✅ `.env` 含 API Key，**不要提交到 git**（`.gitignore` 已排除）。
- ⚠️ `.venv`、`napcat/` 目录不要上传/提交。

---

## 7. Windows 服务器（可选）

1. 安装 Python 3.10+ 和 Git。
2. 从 NapCat 官方仓库下载 **Windows 版**，扫码登录小号，确认开启正向 WS（3001）。
3. 项目里：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # 用记事本填 DEEPSEEK_API_KEY
python main.py
```

4. 常驻：用「任务计划程序」设为开机启动，或用 `nssm` 把 `python main.py` 注册成 Windows 服务。

---

## 8. 常见问题

| 现象 | 原因/解决 |
|---|---|
| `docker compose` 报错 `unknown command` | 缺 compose 插件，装 `docker-compose-plugin` |
| 一直「连接断开，重连」 | NapCat 正向 WS 没开 / 端口不是 3001 / `config.yaml` 的 `ws_url` 不对 |
| NapCat 容器起不来 | 内存不足（升级到 2G）或镜像名变了（以官方 README 为准） |
| 服务起来又退出 | `journalctl -u qqbot -n 100` 看报错，常见是 `.env` 没填 Key |
| 私聊不回 / 群里不回 | 检查 `config.yaml` 的 `private_reply`、`group_need_at`、`wake_words` |
| 服务器重启后没自动起 | `sudo systemctl is-enabled qqbot` 应为 `enabled`；NapCat 容器 `restart: unless-stopped` 已带自启 |
