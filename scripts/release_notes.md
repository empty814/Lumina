## 安装方法

1. 下载下方的 **Lumina.zip**
2. 解压，双击 **`install.command`**
3. 安装完成后，双击「应用程序」中的 Lumina 启动

首次启动会自动下载模型（约 622MB），右上角有进度通知，完成后弹出「Lumina 已就绪」即可使用。

---

## v0.4.0 更新内容

- **PTT 语音输入**：按一次 Command 键开始录音，再按一次停止，自动转写并粘贴到当前窗口；热键可在 config.json 中配置，修改后 1 秒内热加载无需重启
- **菜单栏状态反馈**：录音中显示「● Lumina」，转写中显示「◌ Lumina」
- **语音识别升级**：切换至 Whisper small-4bit 模型，中文准确率显著提升；修复多次识别时上下文污染问题
- **每日日报通知**：每天 20:00 自动推送今日日报系统通知
- **日报采集器开关**：支持在 config.json 中按需禁用指定采集来源
- **PDF 临时文件清理**：修复翻译任务完成后临时目录残留问题
- **API 规范统一**：PDF URL 接口改用 Pydantic 模型，修复版本号不一致

---

## 功能

- **翻译 PDF**：右键 → 快速操作 → 用 Lumina 翻译 PDF（生成中文版 + 双语版）
- **总结 PDF**：右键 → 快速操作 → 用 Lumina 总结 PDF
- **浏览器插件**：API 地址填 `http://127.0.0.1:31821/v1`，模型名填 `lumina`
- **手机 PWA**：Safari 访问 `http://Mac局域网IP:31821`，添加到主屏幕
- **语音转文字**：配合 Raycast / Alfred 使用
- **每日日报**：自动汇总 Git 提交、Shell 历史、剪贴板等活动

右键菜单安装：打开终端运行
```
bash /Applications/Lumina.app/Contents/MacOS/scripts/install_quick_action.sh
```

---

## 系统要求

- macOS 13+（Apple Silicon）
- 首次启动需要网络下载模型（约 622MB）
