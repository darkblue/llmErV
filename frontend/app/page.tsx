"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Radio,
  Upload,
  Play,
  Pause,
  Square,
  RotateCcw,
  Headphones,
  Activity,
  ShieldCheck,
  Trash2,
  Download,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { EventAnalysis, type EventInfo } from "../components/event-analysis";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
type AudioFile = {
  id: string;
  name: string;
  duration: number;
  sample_rate: number;
  channels: number;
  codec: string;
  size: number;
};
type Segment = {
  segment_id: string;
  session_id: string;
  source_id: string;
  text: string;
  original_text?: string;
  corrected_text?: string;
  start_time?: number;
  end_time: number;
  confidence?: number | null;
  asr_engine: string;
  recognition_mode?: string;
  radio_digits?: { digits: string; readings: string } | null;
};
export default function Home() {
  const [files, setFiles] = useState<AudioFile[]>([]),
    [selected, setSelected] = useState<AudioFile>(),
    [query, setQuery] = useState(""),
    [mode, setMode] = useState("连接中"),
    [asrInfo, setAsrInfo] = useState<{
      provider: string;
      ready: boolean;
      status: string;
      error_code?: string | null;
    }>(),
    [status, setStatus] = useState("idle"),
    [error, setError] = useState(""),
    [progress, setProgress] = useState(0),
    [level, setLevel] = useState(0),
    [latency, setLatency] = useState(0),
    [rtf, setRtf] = useState(0),
    [partial, setPartial] = useState(""),
    [segments, setSegments] = useState<Segment[]>([]),
    [events, setEvents] = useState<EventInfo[]>([]),
    [words, setWords] = useState(""),
    [history, setHistory] = useState<
      { id: string; status: string; audio_time: number }[]
    >([]),
    [chunkMs, setChunkMs] = useState(200),
    [recognitionMode, setRecognitionMode] = useState("general"),
    [radioStart, setRadioStart] = useState(0),
    [radioEnd, setRadioEnd] = useState(3),
    [busy, setBusy] = useState(false);
  const ws = useRef<WebSocket | null>(null),
    ctx = useRef<AudioContext | null>(null),
    node = useRef<AudioBufferSourceNode | null>(null),
    timer = useRef<ReturnType<typeof setInterval> | null>(null),
    sent = useRef(0),
    base = useRef(0),
    active = useRef(false),
    pcm = useRef<Float32Array>(new Float32Array()),
    sending = useRef(false),
    lastSent = useRef(0),
    statusRef = useRef("idle"),
    hasFinal = useRef(false),
    sessionId = useRef("");
  const audioOffset = useRef(0);
  useEffect(() => {
    setRadioStart(0);
    setRadioEnd(Math.min(3, selected?.duration || 3));
  }, [selected?.id]);
  async function read<T>(path: string): Promise<T> {
    const r = await fetch(API + path);
    if (!r.ok) throw Error("读取失败，请检查后端连接");
    return r.json();
  }
  async function loadSession(id: string) {
    sessionId.current = id;
    try {
      const [items, analysis, audio] = await Promise.all([
        read<Segment[]>(`/sessions/${id}/transcripts`),
        read<EventInfo[]>(`/events?session_id=${encodeURIComponent(id)}`),
        read<AudioFile[]>("/audio"),
      ]);
      if (sessionId.current !== id) return;
      setSegments(items);
      setEvents(analysis.filter((event) => event.session_id === id));
      setFiles(audio);
      setSelected(audio.find((f) => f.id === items[0]?.source_id));
      setPartial("");
    } catch (e) {
      setError(String(e));
    }
  }
  const load = async () => {
    setFiles(await fetch(API + "/audio").then((r) => r.json()));
  };
  const refreshASR = async () => {
    try {
      const response = await fetch(API + "/health");
      if (!response.ok) throw Error("health");
      const value = await response.json();
      setMode(value.mode);
      setAsrInfo(
        value.asr
          ? { provider: value.asr_provider, ...value.asr }
          : {
              provider: value.asr_provider,
              ready: value.asr_provider === "mock",
              status: "legacy",
            },
      );
    } catch {
      setMode("离线");
      setAsrInfo(undefined);
    }
  };
  useEffect(() => {
    load().catch(() => setError("后端连接失败"));
    refreshASR();
    const id = new URLSearchParams(window.location.search).get("session");
    if (id) loadSession(id);
    const onFocus = () => {
      if (
        sessionId.current &&
        !["connecting", "running", "paused", "stopping"].includes(
          statusRef.current,
        )
      )
        loadSession(sessionId.current);
    };
    window.addEventListener("focus", onFocus);
    fetch(API + "/hotwords")
      .then((r) => r.json())
      .then((x) => setWords(x.words.join("\n")))
      .catch(() => {});
    return () => {
      window.removeEventListener("focus", onFocus);
      ws.current?.close();
      ctx.current?.close();
      if (timer.current) clearInterval(timer.current);
    };
  }, []);
  const updateStatus = (s: string) => {
    statusRef.current = s;
    setStatus(s);
  };
  function cleanup() {
    active.current = false;
    if (timer.current) clearInterval(timer.current);
    node.current?.stop();
    node.current = null;
    ctx.current?.close();
    ctx.current = null;
    setLevel(0);
  }
  async function start() {
    if (!selected) return;
    const offset = recognitionMode === "radio_digits" ? radioStart : 0;
    if (
      recognitionMode === "radio_digits" &&
      (!Number.isFinite(offset) ||
        !Number.isFinite(radioEnd) ||
        offset < 0 ||
        radioEnd <= offset ||
        radioEnd > selected.duration ||
        radioEnd - offset > 30)
    ) {
      setError("请选择录音内 0–30 秒长度的数字短句范围。");
      return;
    }
    audioOffset.current = offset;
    cleanup();
    const previousSocket = ws.current;
    ws.current = null;
    previousSocket?.close();
    setError("");
    setSegments([]);
    setPartial("");
    setEvents([]);
    sessionId.current = "";
    setProgress(offset);
    updateStatus("connecting");
    sent.current = 0;
    sending.current = false;
    hasFinal.current = false;
    try {
      const context = new AudioContext({ sampleRate: 16000 });
      ctx.current = context;
      await context.resume();
      const response = await fetch(API + "/audio/" + selected.id + "/content");
      if (!response.ok) throw Error("音频读取失败");
      const fullBuffer = await context.decodeAudioData(
        await response.arrayBuffer(),
      );
      let buffer = fullBuffer;
      if (recognitionMode === "radio_digits") {
        const from = Math.round(offset * 16000),
          to = Math.min(fullBuffer.length, Math.round(radioEnd * 16000));
        buffer = context.createBuffer(1, to - from, 16000);
        buffer.copyToChannel(fullBuffer.getChannelData(0).slice(from, to), 0);
      }
      pcm.current = buffer.getChannelData(0);
      const socket = new WebSocket(
        API.replace(/^http/, "ws") + "/ws/recognize",
      );
      ws.current = socket;
      socket.onopen = () =>
        socket.send(
          JSON.stringify({
            type: "start",
            source_id: selected.id,
            recognition_mode: recognitionMode,
            audio_offset: offset,
          }),
        );
      socket.onmessage = async (e) => {
        if (ws.current !== socket) return;
        const m = JSON.parse(e.data);
        if (m.type === "model_status") setMode("模型加载中 · " + m.asr_engine);
        if (m.type === "ready") {
          if (
            recognitionMode === "radio_digits" &&
            m.recognition_mode !== "radio_digits"
          ) {
            setError("后端版本尚未支持数字专项，请先更新后端。");
            cleanup();
            updateStatus("error");
            socket.close();
            return;
          }
          sessionId.current = m.session_id;
          setMode(
            m.asr_engine === "mock"
              ? "模拟识别"
              : "真实流式识别 · " + m.asr_engine,
          );
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(context.destination);
          node.current = source;
          base.current = context.currentTime;
          active.current = true;
          updateStatus("running");
          source.start();
          timer.current = setInterval(() => pump(socket, context), 30);
        }
        if (m.type === "partial") setPartial(m.text);
        if (m.type === "progress") {
          sending.current = false;
          setLatency(performance.now() - lastSent.current);
          setRtf(m.rtf);
        }
        if (m.type === "final") {
          hasFinal.current = true;
          setPartial("");
          setSegments((s) => [
            ...s.filter((x) => x.segment_id !== m.segment_id),
            m,
          ]);
        }
        if (m.type === "event")
          setEvents((old) => [
            ...old.filter((x) => x.segment_id !== m.segment_id),
            m,
          ]);
        if (m.type === "state") {
          updateStatus(m.status);
          if (m.status === "running") {
            await context.resume();
            active.current = true;
          }
        }
        if (m.type === "ended") {
          if (!hasFinal.current)
            setError("本次未识别到可确认语音，请检查音量、语言和录音清晰度。");
          cleanup();
          updateStatus(m.status);
        }
        if (m.type === "error") {
          const messages: Record<string, string> = {
            ASR_BUSY: "真实识别会话已占用，请稍后重试。",
            ASR_MODE_UNSUPPORTED: "数字专项模式需要新版 Vosk 后端。",
            RADIO_DIGIT_VOCABULARY_UNSUPPORTED:
              "当前模型缺少数字声学词条，请使用受支持的中文模型。",
            INVALID_AUDIO_OFFSET: "数字片段时间范围无效，请重新选择。",
            ASR_MODEL_MISSING: "中文模型文件未安装，请检查 ASR_MODEL 配置。",
            ASR_MODEL_LOAD_FAILED:
              "模型加载失败，请检查 Render 日志及实例内存。",
            ASR_DEPENDENCY_MISSING: "识别引擎依赖未安装，请部署新版后端镜像。",
            SESSION_FAILED: "识别会话失败，请检查后端日志。",
          };
          setError(messages[m.code] || m.code);
          cleanup();
          updateStatus("error");
          socket.close();
          refreshASR();
        }
      };
      socket.onerror = () => {
        if (ws.current !== socket) return;
        setError("WebSocket 连接失败");
        cleanup();
        updateStatus("error");
      };
      socket.onclose = () => {
        if (ws.current !== socket) return;
        if (["running", "paused", "connecting"].includes(statusRef.current)) {
          cleanup();
          updateStatus("disconnected");
          setError("连接已断开，请重新识别（当前不支持断点恢复）");
        }
      };
    } catch (e) {
      cleanup();
      updateStatus("error");
      setError(String(e));
    }
  }
  function pump(socket: WebSocket, context: AudioContext) {
    if (!active.current || sending.current || socket.readyState !== 1) return;
    const available = Math.min(
      pcm.current.length,
      Math.floor((context.currentTime - base.current) * 16000),
    );
    if (
      available - sent.current < Math.round(chunkMs * 16) &&
      available < pcm.current.length
    )
      return;
    const end = Math.min(available, sent.current + Math.round(chunkMs * 16));
    if (end <= sent.current) {
      if (sent.current >= pcm.current.length) {
        active.current = false;
        socket.send(JSON.stringify({ type: "finish" }));
        if (timer.current) clearInterval(timer.current);
      }
      return;
    }
    const part = pcm.current.subarray(sent.current, end);
    const bytes = new ArrayBuffer(part.length * 2);
    const view = new DataView(bytes);
    let sum = 0;
    part.forEach((v, i) => {
      const sample = Math.max(-1, Math.min(1, v));
      view.setInt16(i * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
      sum += v * v;
    });
    socket.send(bytes);
    lastSent.current = performance.now();
    sending.current = true;
    sent.current = end;
    setProgress(audioOffset.current + end / 16000);
    setLevel(Math.sqrt(sum / part.length));
  }
  async function pause() {
    active.current = false;
    await ctx.current?.suspend();
    ws.current?.send(JSON.stringify({ type: "pause" }));
    updateStatus("paused");
  }
  function resume() {
    ws.current?.send(JSON.stringify({ type: "resume" }));
  }
  function stop() {
    active.current = false;
    ws.current?.send(JSON.stringify({ type: "stop" }));
    cleanup();
    updateStatus("stopping");
  }
  async function upload(file: File) {
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(API + "/audio", { method: "POST", body: form });
      if (!r.ok) throw Error((await r.json()).detail);
      const item = await r.json();
      await load();
      setSelected(item);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function revise(segment: Segment, text: string) {
    const r = await fetch(API + "/transcripts/" + segment.segment_id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (r.ok) {
      const value = await r.json();
      setSegments((s) =>
        s.map((x) => (x.segment_id === segment.segment_id ? value : x)),
      );
      const analysis = await read<EventInfo[]>(
        `/events?session_id=${encodeURIComponent(segment.session_id)}`,
      );
      if (sessionId.current === segment.session_id)
        setEvents(
          analysis.filter((event) => event.session_id === segment.session_id),
        );
      setError("修订已保存，事件分析已更新；原始转写保留。");
    } else setError("修订保存失败，请刷新后重试");
  }
  async function saveWords() {
    const r = await fetch(API + "/hotwords", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        words: words
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
      }),
    });
    setError(
      r.ok ? "词典已保存；当前引擎不支持原生热词或自动纠错" : "词典保存失败",
    );
  }
  const locked = ["connecting", "running", "paused", "stopping"].includes(
    status,
  );
  return (
    <main>
      <header>
        <div className="brand">
          <div className="logo">
            <Radio />
          </div>
          <div>
            <h1>
              llmErV <span>机场应急救援</span>
            </h1>
            <p>AIRPORT EMERGENCY RESCUE · VOICE INTELLIGENCE</p>
          </div>
        </div>
        <div className="top-status">
          <Link href="/review" className="button outline">
            对话修订工作台
          </Link>
          <span className="dot" />
          {mode}
          <span className="separator" />
          辅助分析 · 人工核实
        </div>
      </header>
      <section className="metrics">
        <div>
          <small>音频输入状态</small>
          <strong>
            {(
              {
                idle: "待命",
                running: "实时输入",
                paused: "已暂停",
                finished: "已完成",
                stopped: "已停止",
              } as Record<string, string>
            )[status] || status}
          </strong>
        </div>
        <div>
          <small>ASR 运行模式</small>
          <strong>{mode}</strong>
        </div>
        <div>
          <small>分片往返延迟</small>
          <strong>
            {latency.toFixed(0)} <em>ms</em>
          </strong>
        </div>
        <div>
          <small>实时率 RTF</small>
          <strong>{rtf.toFixed(3)}</strong>
        </div>
        <div>
          <small>音频时间</small>
          <strong>
            {progress.toFixed(1)} <em>s</em>
          </strong>
        </div>
        <div>
          <small>连接状态</small>
          <strong>{locked ? "会话连接中" : "待连接"}</strong>
        </div>
      </section>
      {asrInfo && !asrInfo.ready && (
        <div className="alert">
          ASR 尚未就绪：{asrInfo.error_code || asrInfo.status}。
          <Button variant="outline" onClick={refreshASR}>
            刷新模型状态
          </Button>
        </div>
      )}
      {asrInfo?.provider === "vosk" && (
        <div className="asr-banner">
          真实中文流式识别 · Vosk · CPU · 16kHz ·
          默认单会话。机场术语和关键信息请回听核实；当前词典不具备模型原生热词加权。
        </div>
      )}
      {error && (
        <div role="alert" className="alert">
          {error}
        </div>
      )}
      <div className="workspace">
        <aside className="panel">
          <div className="panel-title">
            <Headphones size={18} />
            <h2>音频接入</h2>
            <span>01</span>
          </div>
          <label className="upload">
            <Upload />
            <b>{busy ? "音频解码中…" : "上传通信录音"}</b>
            <small>WAV / MP3 / FLAC / M4A / OGG / MP4</small>
            <small>最大 50 MB · 最长 30 分钟</small>
            <input
              aria-label="上传音频"
              type="file"
              accept=".wav,.mp3,.flac,.m4a,.ogg,.mp4"
              disabled={busy || locked}
              onChange={(e) => {
                if (e.target.files?.[0]) upload(e.target.files[0]);
                e.target.value = "";
              }}
            />
          </label>
          <div className="section-label">
            录音资料库 <span>{files.length}</span>
          </div>
          <input
            aria-label="搜索录音"
            placeholder="搜索录音名称…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="file-list">
            {files
              .filter((f) => f.name.toLowerCase().includes(query.toLowerCase()))
              .map((f) => (
                <div
                  className={
                    "file " + (selected?.id === f.id ? "selected" : "")
                  }
                  key={f.id}
                >
                  <button disabled={locked} onClick={() => setSelected(f)}>
                    <Radio size={16} />
                    <b>{f.name}</b>
                    <small>
                      {f.duration.toFixed(1)} s · {f.codec} · {f.sample_rate} Hz
                    </small>
                  </button>
                  <button
                    aria-label={"删除 " + f.name}
                    disabled={locked}
                    onClick={async () => {
                      if (!confirm("删除录音？历史转写保留。")) return;
                      const r = await fetch(API + "/audio/" + f.id, {
                        method: "DELETE",
                      });
                      if (r.ok) {
                        if (selected?.id === f.id) setSelected(undefined);
                        load();
                      } else setError("删除失败");
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            {!files.length && (
              <p className="empty">尚无录音，请上传音频开始。</p>
            )}
          </div>
          <div className="source">
            <span className="dot" /> 文件回放通道{" "}
            <small>CH-01 · 标准 PCM 16kHz / MONO</small>
          </div>
          <details>
            <summary>历史识别会话</summary>
            <Button
              variant="outline"
              onClick={async () =>
                setHistory(await fetch(API + "/sessions").then((r) => r.json()))
              }
            >
              刷新历史
            </Button>
            {history.map((s) => (
              <button
                className="history"
                key={s.id}
                onClick={async () => {
                  if (locked) return;
                  await loadSession(s.id);
                }}
              >
                {s.id.slice(0, 8)} · {s.status} ·{" "}
                {(s.audio_time || 0).toFixed(1)}s
              </button>
            ))}
          </details>
        </aside>
        <section className="panel center">
          <div className="panel-title">
            <Activity size={18} />
            <h2>实时语音识别</h2>
            <span>LIVE TRANSCRIPTION</span>
          </div>
          <div className="player">
            <div className="section-label">
              当前音频 <span>1.0× 实时回放</span>
            </div>
            <h3>{selected?.name || "等待选择音频"}</h3>
            <div className="wave" aria-label="输入音量">
              {Array.from({ length: 72 }, (_, i) => (
                <i
                  key={i}
                  style={{
                    height: `${8 + Math.abs(Math.sin(i * 1.73)) * Math.min(80, level * 700)}px`,
                    opacity:
                      i / 72 < progress / (selected?.duration || 1) ? 1 : 0.35,
                  }}
                />
              ))}
            </div>
            <progress value={progress} max={selected?.duration || 1} />
            <div className="time">
              <span>{progress.toFixed(1)} s</span>
              <span>
                {selected?.duration.toFixed(1) || "0.0"} s · RMS{" "}
                {level.toFixed(3)}
              </span>
            </div>
            <div className="controls">
              <Button
                disabled={!selected || locked || !asrInfo?.ready}
                onClick={start}
              >
                <Play size={16} />
                开始识别
              </Button>
              <Button
                variant="outline"
                disabled={status !== "running" && status !== "paused"}
                onClick={status === "paused" ? resume : pause}
              >
                {status === "paused" ? <Play size={16} /> : <Pause size={16} />}
                {status === "paused" ? "继续" : "暂停"}
              </Button>
              <Button
                variant="outline"
                disabled={!["running", "paused"].includes(status)}
                onClick={stop}
              >
                <Square size={15} />
                停止
              </Button>
              <Button
                variant="outline"
                disabled={!selected || locked || !asrInfo?.ready}
                onClick={start}
              >
                <RotateCcw size={15} />
                重新识别
              </Button>
            </div>
            <label className="chunk-label">
              识别策略{" "}
              <select
                aria-label="识别策略"
                disabled={locked}
                value={recognitionMode}
                onChange={(e) => setRecognitionMode(e.target.value)}
              >
                <option value="general">常规通话</option>
                <option
                  value="radio_digits"
                  disabled={asrInfo?.provider !== "vosk"}
                >
                  数字报读专项（仅数字短句）
                </option>
              </select>
            </label>
            {recognitionMode === "radio_digits" && (
              <p className="review-note">
                数字受限解码：幺 / 两 / 拐 /
                洞。请仅输入逐位数字短句；完整通话使用常规策略。候选须回听确认，不是模型训练或通用热词加权。
              </p>
            )}
            {recognitionMode === "radio_digits" && (
              <div className="time-range">
                <label>
                  数字片段开始秒
                  <input
                    aria-label="数字片段开始秒"
                    type="number"
                    min={0}
                    step={0.1}
                    disabled={locked}
                    value={radioStart}
                    onChange={(e) => setRadioStart(Number(e.target.value))}
                  />
                </label>
                <label>
                  数字片段结束秒
                  <input
                    aria-label="数字片段结束秒"
                    type="number"
                    min={0}
                    step={0.1}
                    disabled={locked}
                    value={radioEnd}
                    onChange={(e) => setRadioEnd(Number(e.target.value))}
                  />
                </label>
              </div>
            )}
            <label className="chunk-label">
              分片大小{" "}
              <select
                aria-label="分片大小"
                value={chunkMs}
                onChange={(e) => setChunkMs(Number(e.target.value))}
              >
                {[100, 200, 400, 600].map((n) => (
                  <option key={n} value={n}>
                    {n} ms
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="section-label">
            实时字幕 <span className="cyan">PARTIAL → FINAL</span>
          </div>
          <div className="live">
            <span className="live-tag">增量结果</span>
            <p>{partial || "等待音频分片输入…"}</p>
          </div>
          <div className="section-label">
            通话记录 <span>{segments.length} 条确认片段</span>
          </div>
          <div className="transcripts">
            {segments.map((s) => (
              <article key={s.segment_id}>
                <div>
                  <span className="cyan">
                    {(s.start_time || 0).toFixed(1)}s — {s.end_time.toFixed(1)}s
                  </span>
                  <span className="final-tag">FINAL · {s.asr_engine}</span>
                </div>
                <p>{s.corrected_text ?? s.text}</p>
                {s.recognition_mode === "radio_digits" && (
                  <small>数字专项 · 受限词表 · 原始模型输出保留</small>
                )}
                {s.radio_digits && (s.corrected_text ?? s.text) === s.text && (
                  <p className="review-note">
                    数字候选：{s.radio_digits.digits}（{s.radio_digits.readings}
                    ）· 请进入修订工作台逐位回听确认
                  </p>
                )}
                {s.confidence != null && (
                  <small>
                    词级置信度均值 {(s.confidence * 100).toFixed(0)}
                    %（非准确率）
                  </small>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const text = String(
                      new FormData(e.currentTarget).get("text") ?? "",
                    );
                    revise(s, text).catch(() =>
                      setError("修订或分析更新失败，请刷新历史记录核对。"),
                    );
                  }}
                >
                  <label>
                    人工修订
                    <textarea
                      aria-label="人工修订"
                      name="text"
                      key={s.segment_id + (s.corrected_text ?? s.text)}
                      defaultValue={s.corrected_text ?? s.text}
                    />
                  </label>
                  <Button type="submit">保存修订并更新分析</Button>
                </form>
                <small>原始文本：{s.original_text || s.text}</small>
                <Link href={"/review?segment=" + s.segment_id} className="cyan">
                  参考规范与单卡修订 →
                </Link>
              </article>
            ))}
            {!segments.length && (
              <div className="empty">
                <Radio size={32} />
                <p>已确认的识别结果将显示在这里</p>
                <small>Partial 持续更新，Final 固定保存</small>
              </div>
            )}
          </div>
          <footer>
            {asrInfo?.provider === "mock"
              ? "模拟模式仅验证数据链路，不代表音频内容或识别准确率。"
              : "真实模型增量识别；置信度不是准确率，关键事实须回听核实。"}
          </footer>
        </section>
        <aside className="panel">
          <div className="panel-title">
            <ShieldCheck size={18} />
            <h2>应急事件分析</h2>
            <span>AI ASSIST</span>
          </div>
          <div className="advisory">辅助信息 · 不自动发出调度或运行指令</div>
          <EventAnalysis events={events} finalCount={segments.length} />
          <Button
            variant="outline"
            disabled={!sessionId.current || locked}
            onClick={() => loadSession(sessionId.current)}
          >
            刷新当前分析
          </Button>
          <details className="dictionary">
            <summary>专业术语与热词词典</summary>
            <p>
              词典仅存储；当前未启用模型原生热词和自动纠错。人工修订保留原文。
            </p>
            <textarea
              aria-label="热词词典"
              value={words}
              onChange={(e) => setWords(e.target.value)}
              rows={8}
            />
            <Button onClick={saveWords}>保存词典</Button>
            <Button
              variant="outline"
              onClick={() => {
                const a = document.createElement("a");
                a.href = URL.createObjectURL(
                  new Blob([JSON.stringify({ words: words.split("\n") })], {
                    type: "application/json",
                  }),
                );
                a.download = "hotwords.json";
                a.click();
                URL.revokeObjectURL(a.href);
              }}
            >
              <Download size={14} />
              导出
            </Button>
            <label>
              导入 JSON
              <input
                aria-label="导入热词"
                type="file"
                accept=".json"
                onChange={async (e) => {
                  try {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const x = JSON.parse(await f.text());
                    if (
                      !Array.isArray(x.words) ||
                      x.words.some((w: unknown) => typeof w !== "string")
                    )
                      throw Error();
                    setWords(x.words.join("\n"));
                  } catch {
                    setError("热词 JSON 格式错误");
                  }
                }}
              />
            </label>
          </details>
          <div className="source">
            证据优先 · 信息不足返回未知
            <small>模型置信度不可用时不生成数值</small>
          </div>
        </aside>
      </div>
      <div className="bottom-bar">
        llmErV / PHASE 01{" "}
        <span>机场应急通信 · 音频时间轴关联 · 人工核实闭环</span>
      </div>
    </main>
  );
}
