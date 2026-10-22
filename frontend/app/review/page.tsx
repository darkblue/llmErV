"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, ClipboardCheck, FileText } from "lucide-react";
import { Button } from "../../components/ui/button";
import { EventAnalysis, type EventInfo } from "../../components/event-analysis";
import { RadioDigitReview } from "../../components/radio-digit-review";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
type Excerpt = {
  id: string;
  page: number;
  text: string;
  verified: boolean;
  source_method: string;
};
type Reference = {
  source_url?: string | null;
  detected_standard_id?: string | null;
  id: string;
  title: string;
  kind: string;
  sha256: string;
  pages: number;
  extraction_status: string;
  excerpts: Excerpt[];
};
type Citation = {
  reference_id: string;
  title: string;
  page: number;
  quote: string;
  verified: boolean;
};
type Suggestion = {
  id: string;
  before: string;
  after: string;
  start: number;
  end: number;
  reason: string;
  can_apply: boolean;
  references: Citation[];
};
type Proposal = {
  status: string;
  base_hash: string;
  suggestions: Suggestion[];
  warnings: string[];
  reference_notes?: {
    clause: string;
    title: string;
    note: string;
    reference: Citation;
    currency: string;
  }[];
};
type Segment = {
  segment_id: string;
  source_id: string;
  session_id: string;
  text: string;
  original_text: string;
  corrected_text: string;
  start_time: number;
  end_time: number;
  asr_engine: string;
};
type Revision = {
  id: string;
  before: string;
  after: string;
  method: string;
  created_at: string;
  version: number;
  evidence: Suggestion[];
};
type Audio = { id: string; name: string; duration: number };
const errors: Record<string, string> = {
  SOURCE_REVIEW_ACK_REQUIRED: "请先对照 PDF 核实摘录。",
  AUDIO_REVIEW_ACK_REQUIRED: "请先回听并勾选确认。",
  REFERENCE_REVIEW_REQUIRED: "请先核实对应资料摘录。",
  STALE_TRANSCRIPT_REVIEW_AGAIN: "转写已有新修订，请刷新记录后重新生成建议。",
  UNSAFE_RULE_USE_MANUAL_REVIEW:
    "此规则涉及关键事实或不在安全术语范围内，请回听后人工修订。",
  RULE_NOT_SUPPORTED_BY_EXCERPT: "目标术语不在所选摘录中。",
  TRANSCRIPT_OUTSIDE_AUDIO: "时间范围超出音频。",
  INVALID_PDF_OR_EXTRACTION_FAILED: "PDF 无法提取或已超出页数/文本限制。",
};
async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + url, init);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "请求失败" }));
    throw Error(
      errors[e.detail] ||
        String(typeof e.detail === "string" ? e.detail : "输入格式不正确"),
    );
  }
  return r.json();
}
const json = (value: unknown) => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(value),
});
export default function ReviewPage() {
  const [references, setReferences] = useState<Reference[]>([]),
    [activeRef, setActiveRef] = useState(""),
    [chosenRefs, setChosenRefs] = useState<string[]>([]),
    [kind, setKind] = useState("exercise_card"),
    [page, setPage] = useState(1),
    [excerptText, setExcerptText] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [segments, setSegments] = useState<Segment[]>([]),
    [selectedId, setSelectedId] = useState(""),
    [proposal, setProposal] = useState<Proposal>(),
    [chosen, setChosen] = useState<string[]>([]),
    [audioAck, setAudioAck] = useState(false),
    [revisions, setRevisions] = useState<Revision[]>([]),
    [audioFiles, setAudioFiles] = useState<Audio[]>([]),
    [manualText, setManualText] = useState(""),
    [sourceId, setSourceId] = useState(""),
    [start, setStart] = useState(0),
    [end, setEnd] = useState(1),
    [edited, setEdited] = useState(""),
    [terms, setTerms] = useState<string[]>([]),
    [ruleBefore, setRuleBefore] = useState(""),
    [ruleAfter, setRuleAfter] = useState("指挥中心"),
    [ruleExcerpt, setRuleExcerpt] = useState(""),
    [context, setContext] = useState("aoc_rescue");
  const [events, setEvents] = useState<EventInfo[]>([]);
  const player = useRef<HTMLAudioElement | null>(null);
  const ref = references.find((r) => r.id === activeRef),
    segment = segments.find((s) => s.segment_id === selectedId);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setNotice("");
    try {
      await action();
    } catch (e) {
      setNotice(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const [refs, sessions, audio, capabilities] = await Promise.all([
      call<Reference[]>("/references"),
      call<{ id: string }[]>("/sessions"),
      call<Audio[]>("/audio"),
      call<{ allowed_terms: string[] }>("/review/capabilities"),
    ]);
    setReferences(refs);
    setAudioFiles(audio);
    setTerms(capabilities.allowed_terms);
    const lists = await Promise.all(
      sessions.map((s) =>
        call<Segment[]>("/sessions/" + s.id + "/transcripts"),
      ),
    );
    setSegments(lists.flat());
  }
  useEffect(() => {
    run(refresh);
    const id = new URLSearchParams(window.location.search).get("segment");
    if (id) setSelectedId(id);
  }, []);
  useEffect(() => {
    setProposal(undefined);
    setChosen([]);
    setAudioAck(false);
    setEdited(segment?.corrected_text ?? segment?.text ?? "");
    setEvents([]);
    if (segment) {
      const id = segment.session_id;
      let cancelled = false;
      call<EventInfo[]>("/events?session_id=" + encodeURIComponent(id))
        .then((items) => {
          if (!cancelled)
            setEvents(items.filter((event) => event.session_id === id));
        })
        .catch((e) => {
          if (!cancelled) setNotice(e.message);
        });
      return () => {
        cancelled = true;
      };
    }
  }, [selectedId, segment?.corrected_text]);
  useEffect(() => {
    setRevisions([]);
    if (selectedId)
      call<Revision[]>("/transcripts/" + selectedId + "/revisions")
        .then(setRevisions)
        .catch((e) => setNotice(e.message));
  }, [selectedId, segment?.corrected_text]);
  const updateReference = (value: Reference) => {
    setReferences((old) => old.map((r) => (r.id === value.id ? value : r)));
    setProposal(undefined);
    setChosen([]);
    setAudioAck(false);
  };
  async function upload(file: File) {
    const form = new FormData();
    form.append("file", file);
    const value = await call<Reference>("/references?kind=" + kind, {
      method: "POST",
      body: form,
    });
    setReferences((old) => [...old, value]);
    setActiveRef(value.id);
    setChosenRefs((old) => [...old, value.id]);
    setNotice(
      value.extraction_status === "scan_needs_manual_transcription"
        ? "这是扫描 PDF，请按页录入摘录并对照原件核实；系统不会猜读手写内容。"
        : "PDF 文字已提取，仍需逐页核实。",
    );
  }
  async function loadProposal() {
    const value = await call<Proposal>(
      "/transcripts/" + selectedId + "/review",
      {
        method: "POST",
        ...json({ reference_ids: chosenRefs, communication_context: context }),
      },
    );
    setProposal(value);
    setChosen([]);
    setAudioAck(false);
  }
  async function apply() {
    if (!proposal) return;
    const value = await call<Segment>(
      "/transcripts/" + selectedId + "/review/apply",
      {
        method: "POST",
        ...json({
          reference_ids: chosenRefs,
          communication_context: context,
          base_hash: proposal.base_hash,
          suggestion_ids: chosen,
          acknowledge_audio_review: audioAck,
        }),
      },
    );
    setSegments((old) =>
      old.map((s) => (s.segment_id === value.segment_id ? value : s)),
    );
    setRevisions(
      await call<Revision[]>("/transcripts/" + selectedId + "/revisions"),
    );
    setProposal(undefined);
    setNotice("修订已保存，事件分析已更新；原始转写保留。");
  }
  function listen() {
    if (!segment || !player.current) return;
    player.current.currentTime = segment.start_time;
    player.current
      .play()
      .catch(() => setNotice("无法播放音频，请检查原文件是否仍存在。"));
  }
  return (
    <main className="review-page">
      <header>
        <div className="brand">
          <div className="logo">
            <ClipboardCheck />
          </div>
          <div>
            <h1>对话修订工作台</h1>
            <p>REFERENCE EVIDENCE · AUDIO REVIEW · REVISION HISTORY</p>
          </div>
        </div>
        <Link
          className="button outline"
          href={
            segment
              ? "/?session=" + encodeURIComponent(segment.session_id)
              : "/"
          }
        >
          <ArrowLeft size={16} />
          返回识别台
        </Link>
      </header>
      <div className="advisory review-warning">
        单卡只证明参考用词，不证明录音实际内容。系统仅建议有限术语错字；航班号、位置、时间、人数、否定词及指令均须人工回听，不自动补写。资料归类不等于已核验官方规范或完成合规审查。
      </div>
      {notice && (
        <div className="alert" role="status">
          {notice}
        </div>
      )}
      <div className="advisory review-warning">
        本次参考版本：MH/T
        4014—2003《空中交通无线电通话用语》，尚未核验其现行有效性。
        <a
          className="cyan"
          href="https://www.caac.gov.cn/XXGK/XXGK/BZGF/HYBZ/201511/P020170804579259214829.pdf"
          target="_blank"
          rel="noopener noreferrer"
        >
          查看用户提供的民航局原文
        </a>
      </div>
      <div className="review-grid">
        <aside className="panel">
          <div className="panel-title">
            <BookOpen size={18} />
            <h2>参考资料</h2>
          </div>
          <label>
            资料类型
            <select
              aria-label="资料类型"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="exercise_card">演练单卡 / 本地流程</option>
              <option value="caac_standard">空管规范 / 标准</option>
            </select>
          </label>
          <label className="upload">
            <FileText />
            <b>导入参考 PDF</b>
            <small>最大 15 MiB · 200 页 · 不执行文档内指令</small>
            <input
              aria-label="导入参考PDF"
              type="file"
              accept=".pdf"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) run(() => upload(f));
                e.target.value = "";
              }}
            />
          </label>
          {!references.length && <p className="empty">尚未导入规范或单卡。</p>}
          {references.map((r) => (
            <div className="reference-item" key={r.id}>
              <label>
                <input
                  type="checkbox"
                  aria-label={"用于修订 " + r.title}
                  checked={chosenRefs.includes(r.id)}
                  onChange={(e) => {
                    setChosenRefs((ids) =>
                      e.target.checked
                        ? [...ids, r.id]
                        : ids.filter((id) => id !== r.id),
                    );
                    setProposal(undefined);
                  }}
                />
                用于修订
              </label>
              <button
                className="text-button"
                onClick={() => {
                  setActiveRef(r.id);
                  setRuleExcerpt("");
                }}
              >
                {r.title}
              </button>
              <small>
                {r.kind === "caac_standard" ? "规范资料" : "演练单卡"} ·{" "}
                {r.pages} 页 · {r.excerpts.filter((e) => e.verified).length}{" "}
                个已核实摘录
              </small>
            </div>
          ))}
          {ref && (
            <section className="reference-detail">
              <h3>{ref.title}</h3>
              {ref.detected_standard_id && (
                <p className="review-note">
                  识别版本：{ref.detected_standard_id} · 现行有效性未核验
                </p>
              )}
              <a
                href={API + "/references/" + ref.id + "/content"}
                target="_blank"
                rel="noopener noreferrer"
                className="cyan"
              >
                打开 PDF 原件核对
              </a>
              <p className="hash">SHA256 {ref.sha256}</p>
              {ref.extraction_status === "scan_needs_manual_transcription" && (
                <p className="advisory">
                  扫描件无可提取文字，需要人工录入。手写信息不得猜读。
                </p>
              )}
              <label>
                摘录页码
                <input
                  aria-label="摘录页码"
                  type="number"
                  min={1}
                  max={ref.pages}
                  value={page}
                  onChange={(e) => setPage(Number(e.target.value))}
                />
              </label>
              <label>
                按原件录入摘录
                <textarea
                  aria-label="资料摘录"
                  rows={5}
                  value={excerptText}
                  onChange={(e) => setExcerptText(e.target.value)}
                  placeholder="只录入需要比对的原文，不必导入联系人和电话号码。"
                />
              </label>
              <Button
                disabled={busy || !excerptText.trim()}
                onClick={() =>
                  run(async () => {
                    updateReference(
                      await call<Reference>(
                        "/references/" + ref.id + "/excerpts",
                        {
                          method: "POST",
                          ...json({ page, text: excerptText }),
                        },
                      ),
                    );
                    setExcerptText("");
                  })
                }
              >
                添加待核实摘录
              </Button>
              {ref.excerpts.map((x) => (
                <article className="excerpt" key={x.id}>
                  <strong>
                    第 {x.page} 页 ·{" "}
                    {x.source_method === "manual_transcription"
                      ? "人工录入"
                      : "文字提取"}
                  </strong>
                  <p>{x.text}</p>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={"核实摘录 " + x.id}
                      checked={x.verified}
                      disabled={busy}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        const previous = ref;
                        updateReference({
                          ...ref,
                          excerpts: ref.excerpts.map((item) =>
                            item.id === x.id
                              ? { ...item, verified: checked }
                              : item,
                          ),
                        });
                        run(async () => {
                          try {
                            updateReference(
                              await call<Reference>(
                                `/references/${ref.id}/excerpts/${x.id}/verification`,
                                {
                                  method: "PUT",
                                  ...json({
                                    verified: checked,
                                    acknowledge_source_review: checked,
                                  }),
                                },
                              ),
                            );
                          } catch (error) {
                            updateReference(previous);
                            throw error;
                          }
                        });
                      }}
                    />
                    已逐字对照原 PDF 核实
                  </label>
                </article>
              ))}
              <details>
                <summary>添加术语错字映射</summary>
                <p>
                  仅允许一个编辑距离的通用术语映射，禁止关键事实和指令。目标术语须出现在摘录内。
                </p>
                <select
                  aria-label="规则来源摘录"
                  value={ruleExcerpt}
                  onChange={(e) => setRuleExcerpt(e.target.value)}
                >
                  <option value="">选择来源摘录</option>
                  {ref.excerpts.map((x) => (
                    <option key={x.id} value={x.id}>
                      第 {x.page} 页 · {x.text.slice(0, 35)}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="规则原词"
                  placeholder="疑似错字，如：指回中心"
                  value={ruleBefore}
                  onChange={(e) => setRuleBefore(e.target.value)}
                />
                <select
                  aria-label="规则目标术语"
                  value={ruleAfter}
                  onChange={(e) => setRuleAfter(e.target.value)}
                >
                  {terms.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
                <Button
                  disabled={busy || !ruleExcerpt || !ruleBefore}
                  onClick={() =>
                    run(async () => {
                      await call("/review/rules", {
                        method: "POST",
                        ...json({
                          reference_id: ref.id,
                          excerpt_id: ruleExcerpt,
                          before: ruleBefore,
                          after: ruleAfter,
                        }),
                      });
                      setProposal(undefined);
                      setNotice("映射已保存；仍需逐句回听确认后应用。");
                    })
                  }
                >
                  保存映射
                </Button>
              </details>
            </section>
          )}
        </aside>
        <section className="panel">
          <div className="panel-title">
            <ClipboardCheck size={18} />
            <h2>对话与录音核对</h2>
          </div>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => run(refresh)}
          >
            刷新历史记录
          </Button>
          <label>
            通话场景
            <select
              aria-label="通话场景"
              value={context}
              onChange={(e) => {
                setContext(e.target.value);
                setProposal(undefined);
                setChosen([]);
                setAudioAck(false);
              }}
            >
              <option value="aoc_rescue">机场 AOC / 救援协同</option>
              <option value="atc_air_ground">空地管制通话</option>
              <option value="unknown">场景待核实</option>
            </select>
          </label>
          <label>
            选择 Final 片段
            <select
              aria-label="选择转写片段"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              <option value="">请选择历史转写</option>
              {segments.map((s) => (
                <option key={s.segment_id} value={s.segment_id}>
                  {s.asr_engine} · {s.start_time.toFixed(1)}–
                  {s.end_time.toFixed(1)}s ·{" "}
                  {(s.corrected_text ?? s.text).slice(0, 32)}
                </option>
              ))}
            </select>
          </label>
          {segment ? (
            <>
              <div className="segment-meta">
                来源：
                {audioFiles.find((a) => a.id === segment.source_id)?.name ||
                  "原录音已删除"}{" "}
                ·{" "}
                {segment.asr_engine === "manual_input"
                  ? "人工录入（不是 ASR 输出）"
                  : segment.asr_engine}{" "}
                · {segment.start_time.toFixed(2)}–{segment.end_time.toFixed(2)}s
              </div>
              <audio
                ref={player}
                controls
                src={API + "/audio/" + segment.source_id + "/content"}
                onError={() => setNotice("原录音不可用，无法完成回听验证。")}
                onTimeUpdate={() => {
                  if (
                    player.current &&
                    player.current.currentTime >= segment.end_time &&
                    !player.current.paused
                  )
                    player.current.pause();
                }}
              />
              <Button variant="outline" onClick={listen}>
                回听本段
              </Button>
              <h3>原始转写（保留）</h3>
              <pre className="original-text">
                {segment.original_text || segment.text}
              </pre>
              <h3>当前修订稿</h3>
              <RadioDigitReview
                segmentId={segment.segment_id}
                text={segment.corrected_text ?? segment.text}
                onApplied={refresh}
              />
              <textarea
                aria-label="修订稿"
                rows={5}
                value={edited}
                onChange={(e) => setEdited(e.target.value)}
              />
              <div className="review-actions">
                <Button
                  variant="outline"
                  disabled={busy || edited === segment.corrected_text}
                  onClick={() =>
                    run(async () => {
                      const value = await call<Segment>(
                        "/transcripts/" + selectedId,
                        { method: "PATCH", ...json({ text: edited }) },
                      );
                      setSegments((old) =>
                        old.map((s) =>
                          s.segment_id === selectedId ? value : s,
                        ),
                      );
                      setNotice(
                        "人工修订已保存并记录历史，事件分析已更新。不会训练或修改 ASR 模型。",
                      );
                    })
                  }
                >
                  保存人工修订
                </Button>
                <Button
                  disabled={busy || !chosenRefs.length}
                  onClick={() => run(loadProposal)}
                >
                  生成参考修订建议
                </Button>
              </div>
              {proposal && (
                <div className="proposal">
                  <h3>
                    {proposal.status === "mock_not_reviewable"
                      ? "模拟识别不能修订为真实对话"
                      : "待人工确认的建议"}
                  </h3>
                  {proposal.reference_notes?.map((n) => (
                    <article className="excerpt" key={n.clause}>
                      <strong>
                        人工检查参考 · {n.title} · 第 {n.clause} 条
                      </strong>
                      <p>{n.note}</p>
                      <small>
                        {n.reference.title} · PDF 第 {n.reference.page} 页 ·{" "}
                        {n.reference.verified ? "摘录已核实" : "摘录待核实"}
                      </small>
                      <details>
                        <summary>查看条款摘录</summary>
                        <p>{n.reference.quote}</p>
                      </details>
                    </article>
                  ))}
                  {proposal.warnings.map((w) => (
                    <p className="review-note" key={w}>
                      {w}
                    </p>
                  ))}
                  {!proposal.suggestions.length && (
                    <p>
                      未生成可支持的术语建议。这不表示对话已正确或符合规范。
                    </p>
                  )}
                  {proposal.suggestions.map((s) => (
                    <article className="suggestion" key={s.id}>
                      <label>
                        <input
                          type="checkbox"
                          aria-label={"选择修订 " + s.before}
                          checked={chosen.includes(s.id)}
                          disabled={!s.can_apply}
                          onChange={(e) =>
                            setChosen((ids) =>
                              e.target.checked
                                ? [...ids, s.id]
                                : ids.filter((id) => id !== s.id),
                            )
                          }
                        />
                        <del>{s.before}</del> → <strong>{s.after}</strong>
                      </label>
                      <p>{s.reason}</p>
                      {s.references.map((r, i) => (
                        <blockquote key={i}>
                          {r.title} · 第 {r.page} 页 ·{" "}
                          {r.verified ? "摘录已核实" : "摘录未核实"}
                          <p>{r.quote}</p>
                        </blockquote>
                      ))}
                      {!s.can_apply && (
                        <small>请先在左侧对照原件核实摘录。</small>
                      )}
                    </article>
                  ))}
                  {proposal.suggestions.length > 0 && (
                    <>
                      <label className="audio-ack">
                        <input
                          aria-label="已回听确认"
                          type="checkbox"
                          checked={audioAck}
                          onChange={(e) => setAudioAck(e.target.checked)}
                        />
                        我已回听所选术语，确认修订与实际发音一致；未按单卡补写事实或指令。
                      </label>
                      <Button
                        disabled={busy || !chosen.length || !audioAck}
                        onClick={() => run(apply)}
                      >
                        应用选中修订
                      </Button>
                    </>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="empty">选择已有 Final 或导入带时间范围的人工转写。</p>
          )}
          <details className="manual-import">
            <summary>导入人工转写（不冒充 ASR）</summary>
            <p>
              录音暂不能真实识别时，可自行回听后粘贴原文。请先在识别台上传对应音频或带音轨
              MP4。
            </p>
            <label>
              关联录音
              <select
                aria-label="人工转写关联录音"
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
              >
                <option value="">选择录音</option>
                {audioFiles.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.duration.toFixed(1)}s
                  </option>
                ))}
              </select>
            </label>
            <div className="time-range">
              <label>
                开始秒
                <input
                  aria-label="转写开始秒"
                  type="number"
                  min={0}
                  step={0.1}
                  value={start}
                  onChange={(e) => setStart(Number(e.target.value))}
                />
              </label>
              <label>
                结束秒
                <input
                  aria-label="转写结束秒"
                  type="number"
                  min={0}
                  step={0.1}
                  value={end}
                  onChange={(e) => setEnd(Number(e.target.value))}
                />
              </label>
            </div>
            <textarea
              aria-label="人工转写原文"
              rows={4}
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              placeholder="粘贴实际听到的原文；听不清请标记，不按单卡补齐。"
            />
            <Button
              disabled={busy || !sourceId || !manualText.trim()}
              onClick={() =>
                run(async () => {
                  const value = await call<Segment>("/transcripts/import", {
                    method: "POST",
                    ...json({
                      source_id: sourceId,
                      text: manualText,
                      start_time: start,
                      end_time: end,
                    }),
                  });
                  setSegments((old) => [...old, value]);
                  setSelectedId(value.segment_id);
                  setManualText("");
                  setNotice("人工转写已关联录音，不计为 ASR 识别结果。");
                })
              }
            >
              导入人工转写
            </Button>
          </details>
        </section>
        <aside className="panel">
          <div className="panel-title">
            <FileText size={18} />
            <h2>修订后事件分析与记录</h2>
          </div>
          <EventAnalysis events={events} finalCount={segment ? 1 : 0} />
          <p className="review-note">
            所有修订保留修改前后文本、录音时间范围和参考摘录快照。当前为本地演示操作记录，未接入登录认证，不能用于确认操作人员身份。
          </p>
          {!revisions.length && <p className="empty">尚无修订记录。</p>}
          {revisions.map((r) => (
            <article className="revision" key={r.id}>
              <strong>
                版本 {r.version} ·{" "}
                {r.method === "reference_term_review"
                  ? "参考术语修订"
                  : r.method === "radio_digit_review"
                    ? "数字报读确认"
                    : "人工修改"}
              </strong>
              <small>{new Date(r.created_at).toLocaleString("zh-CN")}</small>
              <p>
                <del>{r.before}</del>
              </p>
              <p>{r.after}</p>
              {r.evidence.map((s) => (
                <div key={s.id}>
                  {s.before} → {s.after}
                  {s.references.map((c, i) => (
                    <small key={i}>
                      {c.title} · 第 {c.page} 页
                    </small>
                  ))}
                </div>
              ))}
            </article>
          ))}
          <div className="advisory">
            空管规范与机场 AOC
            单卡适用场景不同，不能把演练话术直接声明为民航局标准。当前不自动检查复诵完整性、漏报或调度正确性。
          </div>
          <p className="review-note">
            保存修订后自动重算事件分析，原文与修改历史保留。修订只影响当前片段，不训练识别模型；参考资料和术语映射仅用于生成人工确认的建议，不会自动替换其他录音。
          </p>
        </aside>
      </div>
    </main>
  );
}
