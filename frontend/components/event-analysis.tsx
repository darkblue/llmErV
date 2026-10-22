export type EventInfo = {
  segment_id: string;
  mock_excluded?: boolean;
  fields: Record<
    string,
    {
      value: string | null;
      verification: string;
      evidence?: {
        text: string;
        start_time: number;
        end_time: number;
        review_version?: number;
      } | null;
    }
  >;
};
const labels: Record<string, string> = {
  event_type: "事件类型",
  flight: "关联航班",
  location: "事件位置",
  occurred_at: "发生时间",
  units: "涉及单位",
  emergency_level: "应急等级",
  casualties: "伤亡信息",
  resources: "资源需求",
  instructions: "处置指令",
  status: "事件状态",
};
export function EventAnalysis({
  events,
  finalCount,
}: {
  events: EventInfo[];
  finalCount: number;
}) {
  // Keep each segment's analysis. A later empty segment cannot erase earlier
  // evidence; replacing a revised segment can still retract its old findings.
  const fields: EventInfo["fields"] = {};
  for (const event of events)
    for (const [key, field] of Object.entries(event.fields)) {
      if (field.value) fields[key] = field;
    }
  const matched = Object.keys(fields).length;
  return (
    <>
      <div className="event-header" role="status">
        <span className="dot" />{" "}
        {finalCount
          ? `规则已分析 ${events.length} 个片段 · 提取 ${matched} 类信息`
          : "等待最终转写（Partial 不作事件判断）"}
      </div>
      {finalCount > 0 && !matched && (
        <p className="review-note">
          {events.length && events.every((e) => e.mock_excluded)
            ? "模拟字幕不作为事件证据。请使用真实识别或人工转写。"
            : "当前文本未命中明确事件信息；规则分析已运行，信息不足保持未知。"}
        </p>
      )}
      <p className="review-note">
        基于当前修订稿 · 同一字段显示时间轴上最近的明确提及 · 规则提取，尚未启用
        LLM
      </p>
      <div className="event-fields">
        {Object.entries(labels).map(([key, label]) => {
          const field = fields[key];
          return (
            <div key={key} data-testid={`event-${key}`}>
              <small>{label}</small>
              <strong>{field?.value || "未知"}</strong>
              <span>{field?.value ? "待核实" : "无原文证据"}</span>
              {field?.evidence && (
                <details>
                  <summary>查看原文依据</summary>
                  <small>
                    {field.evidence.start_time.toFixed(1)}–
                    {field.evidence.end_time.toFixed(1)}s · 修订版本{" "}
                    {field.evidence.review_version || 0}
                  </small>
                  <p>{field.evidence.text}</p>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
