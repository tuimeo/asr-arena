# 部署指南（非容器化）

在 Linux 服务器上部署 ASR Arena，使用 Nginx + systemd。

## 架构

```
用户 → Nginx (HTTPS, 限流) → uvicorn (FastAPI, 前端 + API)
```

FastAPI 同时提供前端静态文件和 API 接口，Nginx 作为反向代理负责 HTTPS 终止、IP 限流和请求体限制。

## 前置条件

- Ubuntu 22.04+ / Debian 12+（其他发行版类似）
- Python 3.12+
- ffmpeg
- Nginx
- 至少一家 ASR 供应商的 API 密钥

## 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y ffmpeg nginx
```

## 2. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后确认：

```bash
uv --version
```

## 3. 部署应用代码

```bash
# 创建部署目录
sudo mkdir -p /opt/asr-arena
sudo chown www-data:www-data /opt/asr-arena

# 拉取代码（以 www-data 身份）
sudo -u www-data git clone https://github.com/tuimeo/asr-arena.git /opt/asr-arena

# 安装 Python 依赖
cd /opt/asr-arena
sudo -u www-data uv sync --frozen
```

## 4. 配置环境变量

```bash
sudo -u www-data cp .env.example .env
sudo -u www-data nano .env
```

**必须配置**：

```bash
# 至少填写一家供应商的密钥（用于服务端命令行测试）
# 公网部署时，用户通过浏览器提供自己的密钥，这里可以留空

# 生产环境务必自定义加密密钥
# 生成方法：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=你生成的密钥

# 可选：调整限流
# RATE_LIMIT_DAILY=200
# RATE_LIMIT_PER_MINUTE=10
# MAX_CONCURRENT_RECOGNITIONS=5
```

## 5. 验证应用能跑起来

```bash
cd /opt/asr-arena
sudo -u www-data uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开终端测试：

```bash
curl http://127.0.0.1:8000/api/health
# 预期输出：{"status":"ok"}
```

确认无误后 Ctrl+C 停掉。

## 6. 配置 systemd 服务

```bash
sudo cp /opt/asr-arena/asr-arena.service /etc/systemd/system/
```

如果 uv 不在 `/usr/local/bin/uv`，修改 `ExecStart` 中的路径：

```bash
# 查看 uv 实际路径
which uv

# 编辑 service 文件
sudo nano /etc/systemd/system/asr-arena.service
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now asr-arena
```

检查状态：

```bash
sudo systemctl status asr-arena
sudo journalctl -u asr-arena -f   # 实时日志
```

## 7. 配置 Nginx

```bash
sudo cp /opt/asr-arena/nginx.conf.example /etc/nginx/sites-available/asr-arena
sudo nano /etc/nginx/sites-available/asr-arena
```

**需要修改**：

1. `server_name your-domain.com` → 改为你的域名
2. `limit_req_zone` 两行需要放到 `/etc/nginx/nginx.conf` 的 `http {}` 块中（不能放在 server 块里）

```bash
# 把 limit_req_zone 行移到 nginx.conf 的 http 块
sudo nano /etc/nginx/nginx.conf

# 在 http { 下面加：
# limit_req_zone $binary_remote_addr zone=asr_general:10m rate=30r/m;
# limit_req_zone $binary_remote_addr zone=asr_recognize:10m rate=10r/m;
```

然后从 `sites-available/asr-arena` 里删掉这两行。

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/asr-arena /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # 可选：移除默认站点
sudo nginx -t
sudo systemctl reload nginx
```

## 8. 配置 HTTPS（推荐）

使用 Let's Encrypt：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

certbot 会自动修改 Nginx 配置，添加 SSL 证书和重定向。

## 验证部署

```bash
# 健康检查
curl https://your-domain.com/api/health

# 检查服务列表
curl https://your-domain.com/api/engines

# 浏览器访问
# https://your-domain.com
```

## 常用运维命令

```bash
# 查看服务状态
sudo systemctl status asr-arena

# 查看实时日志
sudo journalctl -u asr-arena -f

# 重启服务（更新代码后）
cd /opt/asr-arena && sudo -u www-data git pull && sudo -u www-data uv sync --frozen
sudo systemctl restart asr-arena

# 查看 Nginx 访问日志
sudo tail -f /var/log/nginx/access.log
```

## 故障排查

| 现象 | 检查 |
|---|---|
| 502 Bad Gateway | `systemctl status asr-arena` 看后端是否在跑 |
| 连接拒绝 | `ss -tlnp \| grep 8000` 看端口是否监听 |
| 音频转码失败 | `ffmpeg -version` 确认 ffmpeg 已安装 |
| 密钥解密失败 | `.env` 中 `ENCRYPTION_KEY` 是否变更过（变更后旧密文失效） |
| 429 Too Many Requests | 正常限流行为，等一分钟或调整 `RATE_LIMIT_*` |
