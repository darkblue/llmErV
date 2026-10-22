import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

test("参考摘录核实、回听确认、修订审计与原文保留", async ({
  page,
  request,
}) => {
  // Entire fixture is authored for this UI test, not the user's exercise.
  await page.setContent(
    '<meta charset="utf-8"><h1>自制测试资料</h1><p>指挥中心、五方通话、应急救援频道。</p>',
  );
  const pdf = await page.pdf();
  const audioResponse = await request.post(API + "/audio", {
    multipart: {
      file: {
        name: "review-test-tone.wav",
        mimeType: "audio/wav",
        buffer: fs.readFileSync(path.resolve("../tests/fixtures/tone.wav")),
      },
    },
  });
  expect(audioResponse.ok()).toBeTruthy();
  const audio = await audioResponse.json();
  await page.goto("/review");
  const uploaded = page.waitForResponse(
    (r) => r.url().includes("/references?") && r.request().method() === "POST",
  );
  await page
    .getByLabel("导入参考PDF", { exact: true })
    .setInputFiles({
      name: `self-authored-review-${Date.now()}.pdf`,
      mimeType: "application/pdf",
      buffer: pdf,
    });
  const ref = await (await uploaded).json();
  expect(ref.excerpts[0].text).toContain("指挥中心");
  await page
    .getByLabel("核实摘录 " + ref.excerpts[0].id, { exact: true })
    .check();
  await expect(
    page.getByLabel("核实摘录 " + ref.excerpts[0].id, { exact: true }),
  ).toBeChecked();
  await page.getByText("导入人工转写（不冒充 ASR）", { exact: true }).click();
  await page
    .getByLabel("人工转写关联录音", { exact: true })
    .selectOption(audio.id);
  await page.getByLabel("转写开始秒", { exact: true }).fill("0.5");
  await page.getByLabel("转写结束秒", { exact: true }).fill("3");
  const original = "指回中心，CA1234，27跑道，不要进入。五方通化收到。";
  await page.getByLabel("人工转写原文", { exact: true }).fill(original);
  await page.getByRole("button", { name: "导入人工转写", exact: true }).click();
  await expect(page.locator(".original-text")).toHaveText(original);
  await page.getByRole("button", { name: "回听本段", exact: true }).click();
  await expect
    .poll(() =>
      page.locator("audio").evaluate((a: HTMLAudioElement) => a.currentTime),
    )
    .toBeGreaterThanOrEqual(0.5);
  await page
    .getByRole("button", { name: "生成参考修订建议", exact: true })
    .click();
  await expect(page.locator(".suggestion")).toHaveCount(2);
  await expect(
    page.getByRole("button", { name: "应用选中修订" }),
  ).toBeDisabled();
  await page.getByLabel("选择修订 指回中心", { exact: true }).check();
  await page.getByLabel("选择修订 五方通化", { exact: true }).check();
  await expect(
    page.getByRole("button", { name: "应用选中修订" }),
  ).toBeDisabled();
  await page.getByLabel("已回听确认", { exact: true }).check();
  await page.getByRole("button", { name: "应用选中修订", exact: true }).click();
  await expect(page.getByLabel("修订稿", { exact: true })).toHaveValue(
    "指挥中心，CA1234，27跑道，不要进入。五方通话收到。",
  );
  await expect(page.locator(".original-text")).toHaveText(original);
  await expect(page.locator(".revision")).toHaveCount(1);
  await expect(page.locator(".revision")).toContainText("参考术语修订");
  await expect(page.locator(".revision")).toContainText("第 1 页");
});
