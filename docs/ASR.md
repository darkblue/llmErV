# 真实中文语音识别

## 本阶段方案
新增 Vosk 中文 CPU 流式识别，采用 `vosk-model-small-cn-0.22`（模型源 https://alphacephei.com/vosk/models ，Apache-2.0）。浏览器按播放时钟发送 PCM16/16kHz/mono，模型逐块处理并输出 Partial，检测到语句结束后立即保存 Final；停止/EOF 会冲刷剩余结果。不会预先转写整个文件，也不会把 Mock 输出冒充真实识别。

模型权重共享，每个会话拥有独立 KaldiRecognizer；默认单会话控制资源。忙时返回 ASR_BUSY，不回退 Mock。逐词时间戳用于 Final 音频关联；模型提供时显示词置信度均值，不能将它视为准确率。中文词间空格仅作显示整理，original_text 保留模型原文；人工修订另存 corrected_text。

## 当前 Render 免费实例如何启用
1. 合并对应 feature PR，确认 Render 用 `main` 最新提交重新构建。仍使用仓库根目录的 `docker/backend.Dockerfile`。
2. Render → Environment：把 `ASR_PROVIDER=mock` 改为 **`ASR_PROVIDER=vosk`**。
3. 设置 **`ASR_MODEL=/opt/llmerv-models/vosk-model-small-cn-0.22`**、**`ASR_MAX_SESSIONS=1`**。
4. 保留 `FRONTEND_URL=https://llm-er-v.vercel.app`；保存并重新部署。无需 API 密钥、GPU或外部识别付费账号。
5. 检查 `/health`：`asr_provider=vosk`，`asr.ready=true`，`mode=真实流式识别 · vosk`。只有 HTTP 200 并不证明模型已就绪。
6. Vercel 更新到相同版本；后端地址变量不变。选择语音文件并“开始识别”，顶部显示真实流式模式。
7. 首次使用 `tests/fixtures/mandarin-example.wav`（MIT 许可，见同目录通知）。`tone.wav` 是音调，不包含讲话，不应产生真实字幕。

镜像构建时从官方 HTTPS 源下载约 42 MB 中文模型，校验仓库固定 SHA256 后安全解压；权重不进 Git，不在每次会话中联网下载。构建网络或校验失败会使构建失败，不能跳过验证。模型包含在镜像中，不依赖免费实例的持久化磁盘。用户上传文件/SQLite 仍可能随免费实例重建而丢失。

免费实例会休眠，冷启动需要唤醒并加载模型。ASR 速度取决于 CPU 配额；当 RTF>1 时会慢于播放、字幕滞后。客户端保持单分片背压，不丢音频，播放结束后可继续处理已播放的剩余输入。不要将 CI 性能视作 Render 性能保证。该方案用于普通话试用，机场专业术语、无线电噪声、呼号及数字必须回听核实；单卡不会被用于猜填事实。当前模型不提供词典原生热词加权。

## 本地开发
```bash
pip install -r backend/requirements-dev.txt
python scripts/provision_vosk_model.py --destination models
ASR_PROVIDER=vosk ASR_MODEL=models/vosk-model-small-cn-0.22 uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
系统还需要 FFmpeg 和 Poppler。默认不设置 provider 时仍是明确标记的 Mock。

## 状态与错误
`GET /asr/capabilities` 返回 provider/ready/status/error_code、原生热词、分句、采样率等能力。模型缺失/加载失败时 REST 保持可诊断，识别不启动。
- ASR_DEPENDENCY_MISSING：安装/部署新版依赖。
- ASR_MODEL_MISSING：确认模型目录，不要将旧的 `paraformer-zh-streaming` 当作 Vosk 路径。
- ASR_MODEL_LOAD_FAILED：检查镜像模型、模型版本和实例内存。
- ASR_BUSY：已有真实会话占用默认单会话资源。

识别完全为空时提示没有可确认语音，不生成虚假 Final。Partial 更新同一个未确认片段；Final 固定后下一个片段使用新的 segment_id。停止、断线均释放会话资源。

## 验证和限制
新增适配器状态/隔离/忙时清理、WebSocket 多段 Final、缺模型状态、固定模型 SHA256/安全解压测试。CI 的 Real ASR job 使用真实中文模型，通过 REST 上传及 WebSocket 识别 MIT 许可的 FunASR 普通话样例并核对内容关键词、Partial、停止前 Final 和历史保存。模板测试替身只验证协议，不作为识别证据。Real ASR 工作流另用 `frontend/playwright.real.config.ts` 在真实模型后台上执行浏览器上传、按播放分片、暂停/继续及 Final 验收；默认 Mock 浏览器测试与之分开计数。

一次样例实际输出：参考“欢迎大家来体验达摩院推出的语音识别模型”，识别为“欢迎大家来体验打磨远推出的语音识别模型”。约 7.55 秒（含 2 秒尾部静音）输入产生 23 次 Partial、停止前 Final；该次 CI 测得峰值 RSS 236.9 MiB、RTF 0.24。不是代表性数据集，不据此声称机场录音准确率。早期 eSpeak 合成中文测试因声音质量差未通过内容断言，未据此宣布准确率达标。

FunASR 适配器仍保留，需单独安装 `requirements-asr.txt`、配置模型并提供更充足资源；本阶段免费实例交付与验收使用 Vosk。Whisper、SenseVoice、云端 API 不是已实现提供商。未来可通过统一 ASRAdapter 增加，须保留流式/离线区别。
