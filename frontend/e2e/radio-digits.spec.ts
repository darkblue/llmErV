import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

test("数字候选须逐位回听确认，保留前导零、原文及审计", async ({
  page,
  request,
}) => {
  // Authored transcript + synthetic tone validate review, not ASR accuracy.
  const audio = await (
    await request.post(API + "/audio", {
      multipart: {
        file: {
          name: "self-authored-digit-review.wav",
          mimeType: "audio/wav",
          buffer: fs.readFileSync(path.resolve("../tests/fixtures/tone.wav")),
        },
      },
    })
  ).json();
  const original = "洞 幺 两 拐 洞";
  const r = await request.post(API + "/transcripts/import", {
    data: { source_id: audio.id, text: original, start_time: 0, end_time: 2 },
  });
  expect(r.ok()).toBeTruthy();
  const item = await r.json();
  await page.goto("/review?segment=" + item.segment_id);
  await page.getByRole("button", { name: "生成数字候选", exact: true }).click();
  await expect(page.getByText("01270", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "采用已核实数字", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("数字已逐位回听确认", { exact: true }).check();
  await page
    .getByRole("button", { name: "采用已核实数字", exact: true })
    .click();
  await expect(page.getByLabel("修订稿", { exact: true })).toHaveValue("01270");
  await expect(page.locator(".original-text")).toHaveText(original);
  await expect(page.locator(".revision")).toContainText("数字报读确认");
  await page.getByRole("link", { name: "返回识别台", exact: true }).click();
  await expect(page.locator(".transcripts article > p").first()).toHaveText(
    "01270",
  );
});
