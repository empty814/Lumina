# Lumina

你的桌面上运行的私人 AI 工具箱。不联网，不收费，不上传任何数据。

[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-black)](https://github.com/wnma3mz/Lumina)
[![License](https://img.shields.io/github/license/wnma3mz/Lumina)](LICENSE)

---

## 能做什么

### 📄 PDF 翻译 · 总结

在 Finder 右键选中 PDF，一键翻译或总结，结果直接保存到同目录。支持单文件、整个目录批量处理，以及 URL、arXiv 链接直接下载翻译。

### 📋 每日活动日报

自动采集你的 Shell 命令、Git 提交、浏览记录、备忘录、日历，每小时生成一份「今天做了什么」的简报，帮你找回上下文、追踪进展。

### 🌐 兼容浏览器翻译插件

把任意 OpenAI 兼容插件（沉浸式翻译、OpenAI Translator 等）的 API 地址填为 `http://127.0.0.1:31821/v1`，立即获得本地模型驱动的网页翻译。

---

## 快速开始

### 命令行安装

```bash
git clone https://github.com/wnma3mz/Lumina.git
cd Lumina
uv sync                        # 安装依赖（需要 uv）
uv run lumina server           # 启动服务
```

### 平台安装脚本

- macOS：`uv sync && uv run lumina server`
- Linux：`bash scripts/install_linux.sh`
- Windows：`powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1`

### 平台入口集成

- Linux 文件管理器入口：`bash scripts/install_linux_desktop_entry.sh`
- Windows 右键 `Send to`：`powershell -ExecutionPolicy Bypass -File scripts/install_windows_sendto.ps1`
- 通用文件动作脚本：`uv run python scripts/lumina_file_action.py <translate|summarize|polish> <files...>`

### 平台验证手册

- Windows / Linux 手动验收清单：`docs/windows-linux-validation.md`

### 支持矩阵

| 能力 | macOS | Windows | Linux |
|---|---|---|---|
| Web UI / HTTP API | ✅ | ✅ | ✅ |
| 本地模型默认后端 | MLX | llama.cpp | llama.cpp |
| ASR 默认后端 | mlx-whisper | faster-whisper | faster-whisper |
| PTT 录音转写粘贴 | ✅ | ✅ | ✅（依赖 `xdotool` / `ydotool` 等桌面工具时体验更完整） |
| 结果弹窗 | NSPanel | pywebview | pywebview |
| 系统通知 | ✅ | ✅ | ✅（依赖 `notify-send`） |
| Finder Quick Action / 系统服务 | ✅ | 入口形态不同 | 入口形态不同 |
| 日报 Apple 专属数据源（Notes / Calendar / Safari） | ✅ | — | — |

---

## 使用方式

### PDF 翻译 / 总结

macOS：选中 PDF → 右键 → **快速操作** → 翻译 / 总结  
Windows / Linux：可直接使用 Web UI 或命令行完成同样的翻译 / 总结流程

输出文件：
- `文件名-mono.pdf` — 纯中文版
- `文件名-dual.pdf` — 中英双语对照版
- `文件名-summary.txt` — 中文摘要

**命令行：**

```bash
lumina pdf paper.pdf                                # 翻译本地 PDF
lumina pdf https://arxiv.org/pdf/2104.09864        # 翻译 URL
lumina pdf ./papers/ -o ./translated               # 翻译整个目录
lumina summarize paper.pdf                         # 总结
lumina summarize paper.pdf --stdout                # 总结并打印到终端
uv run python scripts/lumina_file_action.py translate paper.pdf
uv run python scripts/lumina_file_action.py summarize paper.pdf
```

Windows / Linux 桌面入口可调用同一套文件动作脚本：
- PDF：翻译 / 总结
- TXT / MD：润色
- 输出默认写回源文件同目录

---

### 每日活动日报

服务启动后自动运行。访问 `http://127.0.0.1:31821` 查看网页界面，或：

```bash
curl http://127.0.0.1:31821/v1/digest             # 查看当前日报
curl -X POST http://127.0.0.1:31821/v1/digest/refresh  # 立即重新生成
curl http://127.0.0.1:31821/v1/digest/export      # 下载完整历史（.md 文件）
```

日报每小时自动更新，默认每天 20:00 推送系统通知。采集范围：

| 数据来源 | 说明 |
|---|---|
| Shell 历史 | zsh / bash / fish / PowerShell 历史 |
| Git 提交 | 所有扫描目录内的 git log |
| 浏览器历史 | Chrome / Edge / Brave / Chromium / Firefox / Safari（按平台可用） |
| 备忘录 | Notes.app 最近修改条目（macOS） |
| Markdown 笔记 | 扫描目录内 .md 文件 |
| 日历 | 今日及近期日程（macOS） |
| AI 对话 | Cursor IDE / Claude 等对话记录 |

---

### 浏览器插件接入

将插件的 API 地址设为：

```
http://127.0.0.1:31821/v1
```

模型名填 `lumina`，API Key 随便填。

手机 PWA 访问：在 Safari 打开 `http://Mac局域网IP:31821`，添加到主屏幕。

---

## 配置

配置文件位于 `~/.lumina/config.json`，不存在时使用默认值。

```json
{
  "provider": {
    "type": "local",
    "model_path": null
  },
  "whisper_model": "",
  "digest": {
    "scan_dirs": [],
    "history_hours": 24,
    "refresh_hours": 1,
    "notify_time": "20:00"
  }
}
```

| 字段 | 说明 | 默认值 |
|---|---|---|
| `provider.type` | `local`（本地模型；macOS=MLX，Win/Linux=llama.cpp）或 `openai`（远程接口） | `local` |
| `provider.model_path` | 本地模型路径，`null` 时按平台自动下载默认模型 | `null` |
| `provider.llama_cpp.model_path` | 显式指定 GGUF 模型路径 | `null` |
| `provider.openai.base_url` | 远程 API 地址（type=openai 时必填） | — |
| `whisper_model` | 语音模型 ID，留空时按平台使用默认值 | `""` |
| `digest.scan_dirs` | 日报扫描目录，空数组时扫描 Documents / Desktop 等默认目录 | `[]` |
| `digest.history_hours` | 采集时间窗口（小时） | `24` |
| `digest.refresh_hours` | 日报更新间隔（小时） | `1` |
| `digest.notify_time` | 每日通知时间，空字符串禁用 | `"20:00"` |

---

## 开发者文档

<details>
<summary>展开查看：架构、接口、打包</summary>

### 技术栈

| 层 | 实现 |
|---|---|
| LLM 推理 | macOS: mlx-lm；Windows / Linux: llama-cpp-python |
| HTTP 服务 | FastAPI + uvicorn，端口 `31821` |
| 桌面入口 | macOS: rumps；Windows / Linux: CLI + pywebview / 系统通知 |
| 打包 | macOS: PyInstaller `.app`；Windows / Linux: 源码运行 + 安装脚本 |
| 包管理 | uv |

### 架构

```
┌──────────────────────────────────────────────────────┐
│       浏览器 / PWA（http://127.0.0.1:31821）          │
│       浏览器插件 / lumina pdf / lumina summarize      │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│                  FastAPI Server                       │
│  GET  /          → Jinja2 模板渲染 Web UI（HTMX PWA）│
│  GET  /fragments/* → HTMX HTML 片段（局部刷新）      │
│  POST /v1/chat/completions  POST /v1/translate        │
│  POST /v1/pdf/*   GET /v1/digest  POST /v1/digest/refresh│
│  POST /v1/audio/transcriptions                        │
└──────────────────┬───────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  ProviderResolver   │  ←→  OpenAIProvider（远程）
        │  macOS: LocalProvider (mlx-lm)
        │  Win/Linux: LlamaCppProvider
        └─────────────────────┘
```

### HTTP 接口

```bash
# 翻译
POST /v1/translate
{"text": "The quick brown fox", "target_language": "zh"}

# 总结
POST /v1/summarize
{"text": "Long article..."}

# Chat（OpenAI 兼容）
POST /v1/chat/completions
{"model": "lumina", "messages": [{"role": "user", "content": "你好"}]}

# 语音转文字
POST /v1/audio/transcriptions
-F "file=@audio.wav" -F "language=zh"

# 日报
GET  /v1/digest
POST /v1/digest/refresh
GET  /v1/digest/export
```

### 版本说明

| 版本 | 说明 |
|------|------|
| **Full**（默认） | 首次启动按平台自动下载本地模型：macOS 下载 MLX 模型，Windows / Linux 下载 GGUF 模型，无需联网推理 |
| **Lite** | 不含模型，把请求转发到你自己的外部 OpenAI 兼容 API |

### 打包

```bash
bash scripts/build_full.sh      # 构建 Lumina.app
bash scripts/install_quick_action.sh  # 安装 Finder Quick Action
bash scripts/install_linux.sh   # Linux 源码安装
bash scripts/install_linux_desktop_entry.sh  # Linux 文件管理器入口
# Windows:
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/install_windows_sendto.ps1
```

### 目录结构

```
lumina/
  main.py              # CLI 入口
  config.py            # 配置加载
  api/
    server.py          # FastAPI 路由（含 PWA manifest、CORS）
    templates/         # Jinja2 模板（Web UI 主页 + HTMX 片段）
      index.html       # 主页面（PWA，内联 HTMX）
      panels/          # 各 tab 面板初始 HTML
    routers/
      fragments.py     # HTMX HTML 片段路由（/fragments/*）
    static/
      style.css        # 样式（含 bento-card 设计系统）
  providers/
    local.py           # mlx-lm 本地推理（Continuous Batching）
    openai.py          # OpenAI 兼容远程接口
  digest/
    core.py            # 日报生成调度
    collectors/        # 数据采集（shell / git / 浏览器 / 备忘录 / 日历 / AI）
  asr/                 # Whisper 语音转文字
  pdf_translate.py     # lumina pdf 实现
  pdf_summarize.py     # lumina summarize 实现
scripts/
  build_full.sh        # PyInstaller 打包
  install_quick_action.sh
```

</details>
