import { test, expect } from "@playwright/test";
import path from "node:path";

test("真实中文模型在浏览器播放中输出字幕、暂停续传并保存 Final", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("真实流式识别 · vosk", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("上传音频", { exact: true })
    .setInputFiles(path.resolve("../tests/fixtures/mandarin-example.wav"));
  await page.getByRole("button", { name: "开始识别", exact: true }).click();
  await expect(page.locator(".live p")).toContainText(/欢迎|体验|语音/, {
    timeout: 15000,
  });
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await page.waitForTimeout(500);
  const paused = await page.locator(".live p").textContent();
  await page.waitForTimeout(600);
  expect(await page.locator(".live p").textContent()).toBe(paused);
  await page.getByRole("button", { name: "继续", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "重新识别", exact: true }),
  ).toBeEnabled({ timeout: 15000 });
  await expect(page.locator(".transcripts")).toContainText("欢迎");
  await expect(page.locator(".transcripts")).toContainText("语音识别");
  await expect(page.locator(".transcripts")).toContainText("vosk");
  await expect(page.locator(".transcripts")).not.toContainText("模拟识别");
});
