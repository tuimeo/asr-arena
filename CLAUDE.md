# ASR Compare — 开发交接文档

> 本文档供 AI 助手或新开发者快速了解项目背景、设计决策和已知问题。

## 项目概述

多供应商 ASR（语音识别）引擎横向对比工具。用户通过网页录音或上传音频，同时发给多个 ASR 引擎，并排展示结果和 CER（字错率）。

**目标场景**：中文为主，夹杂英文，需兼容地方口音（软约束）。面向中国大陆用户。

## 技术栈

- **后端**：Python 3.12 + FastAPI + uvicorn
- **前端**：纯 HTML + CSS + vanilla JS（无框架）
- **包管理**：uv（不是 pip/requirements.txt）
- **音频转换**：pydub + ffmpeg（系统依赖）
- **CER 计算**：jiwer

## 启动方式

```bash
# 安装依赖
uv sync

# 开发测试（命令行直接调引擎，读 .env 的 key）
uv run python -m backend.test_engines samples/tts_standard.mp3 --engines ali_qwen3asr,baidu_standard

# 启动 Web 服务
uv run python -m backend.main
# 浏览器打开 http://localhost:8000
```

## 引擎清单（15 个，5 家供应商）

### 阿里云百炼（DashScope）— provider: "ali"
| engine_id | 模型 ID | API 类型 | 备注 |
|---|---|---|---|
| ali_paraformer | paraformer-realtime-v2 | Recognition WebSocket（流式） | SDK 内部控制发送节奏，不受 3x sleep 影响 |
| ali_funasr | fun-asr-realtime | Recognition WebSocket（流式） | 同上 |
| ali_qwen3asr | qwen3-asr-flash | MultiModalConversation（同步，传完整音频 base64） | 最适合"完整音频+最准结果"场景 |
| ali_qwen3asr_realtime | qwen3-asr-flash-realtime | OmniRealtimeConversation WebSocket（流式） | 3x speed sleep |

**注意**：
- `paraformer-v2`（非 realtime）和 `fun-asr`（非 realtime）是文件转写版，需要公网 URL + 异步轮询，不适合本工具。
- `qwen3-asr-flash` 通过 `MultiModalConversation.call()` 调用，支持本地文件路径和 base64 data URI。
- Recognition 类的 `call(file=)` 只接受文件路径（不接受 bytes/base64），所以 Paraformer/Fun-ASR 写临时文件。

### 百度智能云 — provider: "baidu"
| engine_id | 模型 ID | API 类型 |
|---|---|---|
| baidu_standard | dev_pid=1537 | REST API，server_api 端点 |
| baidu_pro | dev_pid=80001 | REST API，pro_api 端点 |

**注意**：`baidu-aip` SDK 的 `AipSpeech.asr()` 写死了 `server_api` URL，极速版需要手动覆盖 `client._AipSpeech__asrUrl`。

### 科大讯飞 — provider: "xunfei"
| engine_id | 模型 ID | API 类型 |
|---|---|---|
| xunfei_iat | domain=iat | WebSocket wss://iat-api.xfyun.cn/v2/iat |
| xunfei_spark | domain=slm | WebSocket wss://iat.xf-yun.com/v1 |

**注意**：
- 两个引擎的 WebSocket 协议结构不同（旧版用 common/business/data，星火用 header/parameter/payload）。
- 星火的 `parameter.iat` 必须包含 `result` 块（encoding/compress/format），否则报 10106 错误。
- 官方 `xfyunsdkspark` SDK 内部 `WAIT_MILLIS=40` 写死 1x 速度发送，75s 音频必超时。已改为自己的 WebSocket 实现。
- wpgs 动态修正协议：星火模型每次 `rpl` 的 text 是累积的完整文本（不是增量），`_WpgsCollector` 能正确处理。

### 腾讯云 — provider: "tencent"
| engine_id | 模型 ID | API 类型 |
|---|---|---|
| tencent_sentence | 16k_zh | SentenceRecognition，官方 SDK |
| tencent_flash | 16k_zh | 极速版，自签名 HTTP |
| tencent_flash_large | 16k_zh_large | 极速版大模型引擎，同上 |

**注意**：
- 极速版不在 `tencentcloud-sdk-python-asr` 里，需要自己做 HMAC-SHA1 签名。
- 签名构造：`POSTasr.cloud.tencent.com/asr/flash/v1/{appid}?{sorted_params}`，appid 在 path 不在 query。签名放 `Authorization` header。
- 官方 GitHub 有 `tencentcloud-speech-sdk-python` 但不是标准 PyPI 包。

### 火山引擎（字节跳动） — provider: "volcengine"
| engine_id | 模型 ID | API 类型 |
|---|---|---|
| volcengine_seedasr | 1.0 bigmodel | WebSocket 二进制协议，双向流式 |
| volcengine_seedasr_nostream | 1.0 bigmodel_nostream | WebSocket 二进制协议，流式输入 |
| volcengine_seedasr2 | 2.0 bigmodel_async | WebSocket 二进制协议，优化版双向流式 |
| volcengine_seedasr2_nostream | 2.0 bigmodel_nostream | WebSocket 二进制协议，流式输入 |

**注意**：
- 没有官方 Python SDK，自己实现二进制协议（4 字节 header + gzip 压缩）。
- 1.0 resource_id: `volc.bigasr.sauc.duration`，2.0: `volc.seedasr.sauc.duration`。
- 2.0 双向流式用 `bigmodel_async`（不是 `bigmodel`），否则 400。
- 鉴权通过 HTTP headers（X-Api-App-Key, X-Api-Access-Key, X-Api-Resource-Id, X-Api-Connect-Id）。
- websockets v16 用 `additional_headers`（不是 `extra_headers`）。

## 流式引擎发送配速

统一 3 倍速发送（chunk 实际音频时长 / 3）：

| 引擎 | chunk | 音频时长 | sleep |
|---|---|---|---|
| 讯飞（两个） | 1280B | 40ms | 0.013s |
| 阿里 Qwen3-RT | 3200B | 100ms | 0.033s |
| 火山（四个） | 6400B | 200ms | 0.067s |

75 秒音频最慢约 25s 发完。引擎超时设为 60s。

## 前端架构

### 浏览器存储
| 存储位置 | 内容 |
|---|---|
| localStorage `asr_compare_encrypted_keys` | API 密钥密文（Fernet 加密） |
| localStorage `asr_compare_configured_providers` | 已配置的供应商列表（用于 checkbox 状态） |
| IndexedDB `asr_compare_db` | 录音记录（blob、名称、时间、参考文本、引擎列表、识别结果） |

### JS 文件依赖关系
加载顺序：`app.js` → `api-keys.js` → `recorder.js`
- `app.js`：定义 `ALL_ENGINES`、`buildResultMetaHtml()`、引擎 checkbox、识别流程
- `api-keys.js`：依赖 `ALL_ENGINES`（通过 `getEngineProviders()`）
- `recorder.js`：依赖 `ALL_ENGINES`、`buildResultMetaHtml()`、`createRecord()`

### 密钥管理流程
1. 用户填写明文 key → 前端调 `/api/merge-keys`（发新 key + 旧密文）
2. 后端解密旧密文、合并新 key、重新加密 → 返回新密文 + providers 列表
3. 前端存密文到 localStorage，清空输入框
4. 识别时前端发密文 → 后端 `/api/recognize` 解密后调 API
5. 加密密钥可通过 .env `ENCRYPTION_KEY` 配置，默认用 hardcoded passphrase 派生

### 识别结果流式传输（SSE）
后端用 `StreamingResponse` + `asyncio.as_completed`，每完成一个引擎立即推送。前端用 `fetch` + `ReadableStream` 读取，逐个更新卡片。

## 已知限制

1. **录音最长 75 秒**（前端自动停止 + 后端校验）
2. **百度短语音识别限制 60 秒**（超过会被百度拒绝）
3. **讯飞星火 `xfyunsdkspark` SDK 已弃用**（内部 1x 速度写死，长音频必超时，改为自己的 WebSocket）
4. **阿里文件转写类模型不可用**（需公网 URL + 异步，不适合快速对比）
5. **Fernet 默认加密密钥在源码中**（生产环境必须通过 .env 配置自定义密钥）

## 测试样本

| 文件 | 时长 | 用途 |
|---|---|---|
| samples/tts_standard.mp3 + .txt | 5.6s | 短音频快速测试 |
| samples/tts_long_75s.mp3 + .txt | 75s | 长音频回归测试（流式引擎 3x 配速） |

音频由阿里云 CosyVoice TTS 生成（非真人），可公开。
