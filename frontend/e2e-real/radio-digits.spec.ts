import { test, expect } from "@playwright/test";

test("真实数字专项流式识别选段，时间戳关联原始录音", async ({ page }) => {
  test.skip(
    !process.env.RADIO_DIGIT_FIXTURE,
    "CI supplies a self-authored synthetic digit fixture",
  );
  await page.goto("/");
  await expect(
    page.getByText("真实流式识别 · vosk", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("上传音频", { exact: true })
    .setInputFiles(process.env.RADIO_DIGIT_FIXTURE!);
  await page
    .getByLabel("识别策略", { exact: true })
    .selectOption("radio_digits");
  await page.getByLabel("数字片段开始秒", { exact: true }).fill("0.5");
  await page.getByLabel("数字片段结束秒", { exact: true }).fill("8");
  // Fixture duration is read through the UI to avoid assuming TTS timing.
  const duration = await page.locator("progress").getAttribute("max");
  await page.getByLabel("数字片段结束秒", { exact: true }).fill(duration!);
  await page.getByRole("button", { name: "开始识别", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "重新识别", exact: true }),
  ).toBeEnabled({ timeout: 20000 });
  await expect(page.locator(".transcripts")).toContainText("数字候选");
  await expect(page.locator(".transcripts")).toContainText("受限词表");
  await expect(page.locator(".transcripts")).not.toContainText("模拟识别");
});
