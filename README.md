# ASR Arena — 国产语音识别横评

录音或上传音频，同时发给多个语音识别服务，并排对比结果。

## 支持的服务（15 个）

| 供应商 | 服务 |
|---|---|
| **阿里云百炼** | Paraformer-v2、Fun-ASR、Qwen3-ASR、Qwen3-ASR-Realtime |
| **百度智能云** | 标准版、极速版 |
| **科大讯飞** | 语音听写、星火语音大模型 |
| **腾讯云** | 一句话识别、极速版、极速版(大模型) |
| **火山引擎** | Seed-ASR 1.0 流式/非流式、Seed-ASR 2.0 流式/非流式 |

## 快速开始

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- ffmpeg（音频格式转换）
- 至少一家供应商的 API 密钥

### 安装

```bash
git clone <repo-url>
cd asr-arena
uv sync
```

### 配置密钥

```bash
cp .env.example .env
# 编辑 .env，填写你有的供应商的密钥
```

### 启动

```bash
uv run python -m backend.main
```

浏览器打开 http://localhost:8000

### 命令行测试

不启动 Web 服务，直接用 `.env` 的密钥测试：

```bash
# 测试所有已配置的服务
uv run python -m backend.test_engines samples/tts_standard.mp3

# 指定服务
uv run python -m backend.test_engines samples/tts_standard.mp3 --engines ali_qwen3asr,baidu_standard

# 带参考文本计算 CER
uv run python -m backend.test_engines samples/tts_standard.mp3 --reference "今天天气不错，我们来测试一下语音识别的效果，看看各家引擎的表现如何。"
```

## 功能

- **浏览器录音**（WebM/Opus）或上传音频文件（支持 mp3/m4a/wav 等常见格式）
- **并发调用**多个服务，SSE 流式返回结果（先完成的先显示）
- **CER 计算**：输入参考文本，自动计算各服务的字错率
- **历史记录**：录音、服务选择、识别结果持久存储在浏览器 IndexedDB
- **服务信息**：hover 查看模型 ID、描述、官方文档链接
- **密钥加密**：API 密钥经后端加密后存储，浏览器本地不保留明文
- **速率限制**：按密钥组合限流，防止滥用

## 密钥获取

| 供应商 | 控制台地址 | 需要的字段 |
|---|---|---|
| 阿里云百炼 | https://bailian.console.aliyun.com/ | API Key |
| 百度智能云 | https://console.bce.baidu.com/ai/#/ai/speech/app/list | App ID, API Key, Secret Key |
| 科大讯飞 | https://console.xfyun.cn/services/bmc | App ID, API Key, API Secret |
| 腾讯云 | https://console.cloud.tencent.com/cam/capi | Secret ID, Secret Key, AppID |
| 火山引擎 | https://console.volcengine.com/speech/app | App ID, Access Token |

## 安全说明

API 密钥在浏览器端经后端加密后存储在 localStorage。每次识别时，密文发送至后端解密后调用各供应商 API。

**如果部署在公网：**

1. 务必在 `.env` 中设置自定义 `ENCRYPTION_KEY`
2. 使用 HTTPS
3. 用户应仅提供最小权限的密钥，短期试用后及时轮换

## 配置项（.env）

```bash
# 各供应商密钥（见 .env.example）

# 密钥加密密钥（生产环境务必自定义）
# 生成方法: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# 速率限制
RATE_LIMIT_DAILY=200        # 每组密钥每天最多调用次数
RATE_LIMIT_PER_MINUTE=10    # 每组密钥每分钟最多调用次数
```

## 项目结构

```
asr-arena/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── audio_utils.py       # 音频格式转换（pydub + ffmpeg）
│   ├── cer_utils.py         # CER 字错率计算
│   ├── key_crypto.py        # Fernet 加密/解密
│   ├── rate_limit.py        # 按密钥限流
│   ├── test_engines.py      # 命令行测试脚本
│   └── engines/
│       ├── base.py           # BaseASREngine 抽象类
│       ├── ali_dashscope.py  # 阿里云（4 个服务）
│       ├── baidu.py          # 百度（2 个服务）
│       ├── xunfei.py         # 讯飞（2 个服务）
│       ├── tencent.py        # 腾讯云（3 个服务）
│       └── volcengine_seedasr.py  # 火山引擎（4 个服务）
├── frontend/
│   ├── index.html
│   ├── app.js               # 服务定义、识别流程、SSE 读取
│   ├── api-keys.js           # 密钥管理（加密存储）
│   ├── recorder.js           # 录音、IndexedDB、历史记录
│   └── style.css
├── samples/                  # 测试音频及参考文本
├── pyproject.toml
├── .env.example
└── CLAUDE.md                 # 开发交接文档（AI 助手参考）
```
