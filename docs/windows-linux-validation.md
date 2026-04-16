# Windows / Linux 验收清单

这份清单用于你后续在真实 `Windows` / `Linux` 环境上做手动验证。

默认前提：
- 已完成基础安装
- 能运行 `uv run lumina server`
- 本地模型首次下载允许较长等待

## 通用准备

1. 启动服务：`uv run lumina server`
2. 打开 `http://127.0.0.1:31821`
3. 记录当前平台、桌面环境、Python 版本、是否有代理
4. 如果是 Linux，先确认是否安装了这些桌面工具：
   - `notify-send`
   - `xdotool` 或 `ydotool`
   - Wayland 环境下如果前台粘贴失败，记录桌面会话类型

## 验收 1：本地模型默认后端

目标：
- macOS 之外默认不再走 MLX
- Windows / Linux 默认 `provider.type=local` 时能正常启动

步骤：
1. 删除或临时备份 `~/.lumina/config.json`
2. 启动 `uv run lumina server`
3. 观察首次模型下载行为
4. 访问 `GET /v1/config`

预期：
- `provider.type` 仍是 `local`
- `provider.backend` 为 `llama_cpp`
- 不出现 `mlx` 导入报错
- 模型路径指向 `.gguf`

需要记录：
- 下载的实际模型文件名
- 首次加载耗时
- CPU / GPU 使用情况是否符合预期

## 验收 2：Web UI 与基础 API

步骤：
1. 打开首页
2. 测试翻译、总结、润色各一次
3. 请求：
   - `GET /health`
   - `GET /v1/config`
   - `GET /v1/models`

预期：
- 页面正常渲染
- API 无 500
- `/v1/config` 中的 `provider.backend` 与平台一致

## 验收 3：PDF 翻译 / 总结

步骤：
1. 准备一个真实 PDF
2. 命令行执行：
   - `uv run lumina pdf your.pdf -o .`
   - `uv run lumina summarize your.pdf`
3. 再用桌面入口执行一次：
   - Linux：安装 `bash scripts/install_linux_desktop_entry.sh` 后，从文件管理器 `Open With` 触发
   - Windows：安装 `powershell -ExecutionPolicy Bypass -File scripts/install_windows_sendto.ps1` 后，用 `Send to`

预期：
- 生成 `*-mono.pdf`
- 生成 `*-dual.pdf`
- 生成 `*-summary.txt`
- 输出文件在原文件同目录

需要记录：
- 非 ASCII 路径是否正常
- 多选文件时入口脚本是否都能处理

## 验收 4：文本润色入口

步骤：
1. 准备 `txt` / `md` 文件
2. 命令行执行：
   - `uv run lumina polish file.md`
3. 桌面入口执行：
   - Linux：`Open With -> Lumina Polish Text`
   - Windows：`Send to -> Lumina Polish Text`

预期：
- 生成 `*-polished.txt` 或 `*-polished.md`
- `README*` 或 `*-en*` 文件默认按英文处理

## 验收 5：Popup

步骤：
1. 执行：
   - `uv run lumina popup --action polish --text "hello world"`
2. 观察弹窗行为
3. 点击复制并关闭

预期：
- Windows / Linux 使用 `pywebview` 弹窗
- 文本可流式展示
- 复制后自动关闭

需要记录：
- 窗口是否总在前台
- 是否被桌面环境拦截

## 验收 6：通知

步骤：
1. 运行服务
2. 手动触发可见通知场景，例如启动完成或端口冲突

预期：
- Windows 有系统气泡通知
- Linux 在装有 `notify-send` 时能看到系统通知
- 没装通知工具时，功能静默降级但主流程不报错

## 验收 7：PTT

步骤：
1. 在配置里开启 `ptt.enabled=true`
2. 重启服务
3. 在文本输入框中测试录音、转写、回贴

预期：
- 热键能触发
- 能录音并转写
- 能复制并尝试粘贴回前台窗口

Linux 特别关注：
- X11 与 Wayland 行为差异
- `xdotool` / `ydotool` 缺失时是否只是“无法自动粘贴”，而不是整个流程失败

## 验收 8：Digest

步骤：
1. 配置 `digest.enabled=true`
2. 准备一些测试活动：
   - PowerShell / bash / zsh / fish 命令
   - 打开浏览器页面
   - Cursor / Claude / Codex 对话
3. 触发：
   - `POST /v1/digest/refresh`

预期：
- Windows 能看到 PowerShell 历史
- Windows / Linux 能看到 Chromium 系浏览器历史
- Windows / Linux 能看到 Cursor 对话记录
- Apple 专属源缺失时是合理降级，不会报错

## 验收 9：桌面入口体验

### Linux

步骤：
1. 执行 `bash scripts/install_linux_desktop_entry.sh`
2. 在文件管理器中找到 PDF / TXT / MD
3. 尝试通过 `Open With` 调用 Lumina

预期：
- 可看到 Lumina 相关项
- 触发后会在终端中运行并写出结果文件

### Windows

步骤：
1. 执行 `powershell -ExecutionPolicy Bypass -File scripts/install_windows_sendto.ps1`
2. 右键文件 -> `Send to`
3. 触发对应 Lumina 项

预期：
- `Send to` 菜单中能看到 3 个 Lumina 入口
- 处理完成后结果写回原目录

## 建议回传的信息

验证完成后，建议把下面这些结果发回来：
- 平台与桌面环境
- 成功项 / 失败项
- 控制台报错原文
- 哪些功能是“完全不可用”，哪些是“可用但体验欠佳”
- 如果是 Linux，补充 `echo $XDG_SESSION_TYPE`
