"use client";
import { useEffect, useState } from "react";
import { Button } from "./ui/button";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
type Result = {
  base_hash: string;
  candidate: {
    digits: string;
    readings: string;
    recognized_text: string;
    mechanism: string;
  } | null;
};
export function RadioDigitReview({
  segmentId,
  text,
  onApplied,
}: {
  segmentId: string;
  text: string;
  onApplied: () => Promise<void>;
}) {
  const [result, setResult] = useState<Result>();
  const [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    setResult(undefined);
    setAck(false);
    setNotice("");
  }, [segmentId, text]);
  async function run(apply: boolean) {
    setBusy(true);
    setNotice("");
    try {
      const r = await fetch(
        API +
          `/transcripts/${segmentId}/radio-digits` +
          (apply ? "/apply" : ""),
        apply
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                base_hash: result?.base_hash,
                acknowledge_audio_review: ack,
              }),
            }
          : undefined,
      );
      if (!r.ok) {
        const e = await r.json();
        throw Error(
          e.detail === "STALE_TRANSCRIPT_REVIEW_AGAIN"
            ? "转写已变化，请刷新并重新生成候选。"
            : "数字复核失败，请重新生成候选并回听确认。",
        );
      }
      if (apply) {
        await onApplied();
        setNotice("数字修订已保存，原文及回听确认记录保留。");
      } else {
        setResult(await r.json());
        setAck(false);
      }
    } catch (e) {
      setNotice(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="excerpt">
      <h3>民航数字报读复核</h3>
      <p>
        1 幺 · 2 两 · 7 拐 · 0
        洞。仅复核完整数字短句，普通话中的“两架、拐弯、洞口”不自动替换；不补全呼号、位置或指令。
      </p>
      <Button variant="outline" disabled={busy} onClick={() => run(false)}>
        生成数字候选
      </Button>
      {result &&
        (result.candidate ? (
          <>
            <p>
              数字候选：<strong>{result.candidate.digits}</strong> ·{" "}
              {result.candidate.readings} · 待核实
            </p>
            <small>模型/转写原文：{result.candidate.recognized_text}</small>
            <label>
              <input
                type="checkbox"
                aria-label="数字已逐位回听确认"
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
              />
              我已回听并逐位核实数字，包括前导零，没有补写未听到的数字。
            </label>
            <Button disabled={busy || !ack} onClick={() => run(true)}>
              采用已核实数字
            </Button>
          </>
        ) : (
          <p>
            没有可安全生成的完整数字候选。混合通话、听不清或含未知词时，请回听后人工修订。
          </p>
        ))}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
