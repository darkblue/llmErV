import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

test("人工修订同步右栏，工作台返回及历史会话保留分析", async ({
  page,
  request,
}) => {
  // Authored text associated with a synthetic tone; not an ASR accuracy test.
  const upload = await request.post(API + "/audio", {
    multipart: {
      file: {
        name: "self-authored-events.wav",
        mimeType: "audio/wav",
        buffer: fs.readFileSync(path.resolve("../tests/fixtures/tone.wav")),
      },
    },
  });
  expect(upload.ok()).toBeTruthy();
  const audio = await upload.json();
  const original = "CA1234，27号跑道起火，请消防前往集结。";
  const imported = await request.post(API + "/transcripts/import", {
    data: {
      source_id: audio.id,
      text: original,
      start_time: 0,
      end_time: 2,
    },
  });
  expect(imported.ok()).toBeTruthy();
  const item = await imported.json();
  await page.goto("/?session=" + item.session_id);
  await expect(page.getByTestId("event-location")).toContainText("27号跑道");
  await expect(page.getByTestId("event-event_type")).toContainText("起火");
  const revised = "CA1234，28号跑道未发现起火，请医疗前往集结。";
  await page.getByLabel("人工修订", { exact: true }).fill(revised);
  await page
    .getByRole("button", { name: "保存修订并更新分析", exact: true })
    .click();
  await expect(page.getByTestId("event-location")).toContainText("28号跑道");
  await expect(
    page.getByTestId("event-event_type").locator("strong"),
  ).toHaveText("未知");
  await expect(page.getByTestId("event-units")).toContainText("医疗");
  await expect(page.locator(".transcripts article > p")).toHaveText(revised);
  await expect(page.locator(".transcripts")).toContainText(
    "原始文本：" + original,
  );
  await page
    .getByRole("link", { name: "参考规范与单卡修订 →", exact: true })
    .click();
  await expect(page.getByLabel("修订稿", { exact: true })).toHaveValue(revised);
  await expect(page.getByTestId("event-location")).toContainText("28号跑道");
  await page
    .getByLabel("修订稿", { exact: true })
    .fill("未发现烟雾，人员平安。");
  await page.getByRole("button", { name: "保存人工修订", exact: true }).click();
  await expect(page.getByTestId("event-location").locator("strong")).toHaveText(
    "未知",
  );
  await expect(
    page.getByTestId("event-event_type").locator("strong"),
  ).toHaveText("未知");
  await page.getByRole("link", { name: "返回识别台", exact: true }).click();
  await expect(page.locator(".transcripts article > p")).toHaveText(
    "未发现烟雾，人员平安。",
  );
  await expect(page.getByTestId("event-location").locator("strong")).toHaveText(
    "未知",
  );
  await page.goto("/");
  await page.getByText("历史识别会话", { exact: true }).click();
  await page.getByRole("button", { name: "刷新历史", exact: true }).click();
  await page
    .locator(".history")
    .filter({ hasText: item.session_id.slice(0, 8) })
    .click();
  await expect(page.locator(".transcripts article > p")).toHaveText(
    "未发现烟雾，人员平安。",
  );
  await expect(page.locator(".event-header")).toContainText(
    "规则已分析 1 个片段",
  );
});

test("后续空片段不清空已有事件，展示可展开的时间依据", async ({ page }) => {
  // Response fixtures isolate sidebar aggregation, not real audio inference.
  const first = {
    segment_id: "first",
    session_id: "fixture",
    source_id: "tone",
    text: "27号跑道起火",
    corrected_text: "27号跑道起火",
    start_time: 0,
    end_time: 2,
    asr_engine: "manual_input",
  };
  const second = {
    ...first,
    segment_id: "second",
    text: "收到",
    corrected_text: "收到",
    start_time: 2,
    end_time: 3,
  };
  await page.route(API + "/sessions/fixture/transcripts", (r) =>
    r.fulfill({ json: [first, second] }),
  );
  await page.route(API + "/events?session_id=fixture", (r) =>
    r.fulfill({
      json: [
        {
          segment_id: "first",
          fields: {
            location: {
              value: "27号跑道",
              verification: "unverified",
              evidence: { text: first.text, start_time: 0, end_time: 2 },
            },
          },
        },
        {
          segment_id: "second",
          fields: { location: { value: null, verification: "unknown" } },
        },
      ],
    }),
  );
  await page.goto("/?session=fixture");
  await expect(page.getByTestId("event-location")).toContainText("27号跑道");
  await expect(page.locator(".event-header")).toContainText("2 个片段");
  await page.getByTestId("event-location").getByText("查看原文依据").click();
  await expect(page.getByTestId("event-location")).toContainText("0.0–2.0s");
  await expect(page.getByTestId("event-location")).toContainText(first.text);
});
