import { test, expect } from "@playwright/test";
import path from "node:path";
test("上传、真实时钟分片、暂停、继续、Final、修订与历史", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByText("模拟识别", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("上传音频", { exact: true })
    .setInputFiles(path.resolve("../tests/fixtures/tone.wav"));
  await expect(
    page.getByRole("button", { name: "开始识别", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "开始识别", exact: true }).click();
  await expect(page.locator(".live p")).toContainText("已接收音频");
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await page.waitForTimeout(350);
  const before = await page.locator(".live p").textContent();
  await page.waitForTimeout(600);
  expect(await page.locator(".live p").textContent()).toBe(before);
  await page.getByRole("button", { name: "继续", exact: true }).click();
  await expect(page.locator(".transcripts article")).toHaveCount(1, {
    timeout: 12000,
  });
  await expect(page.locator(".transcripts article")).toContainText(
    "非真实转写",
  );
  await page.getByLabel("人工修订", { exact: true }).fill("人工核实测试");
  await page
    .getByRole("button", { name: "保存修订并更新分析", exact: true })
    .click();
  await expect(page.locator(".transcripts article > p")).toHaveText(
    "人工核实测试",
  );
  await expect(page.locator(".transcripts textarea")).toHaveValue(
    "人工核实测试",
  );
  await page.getByText("历史识别会话", { exact: true }).click();
  await page.getByRole("button", { name: "刷新历史" }).click();
  await expect(page.locator(".history").first()).toBeVisible();
});
test("停止和重新识别不叠加 Partial", async ({ page }) => {
  await page.goto("/");
  await page
    .getByLabel("上传音频", { exact: true })
    .setInputFiles(path.resolve("../tests/fixtures/tone.wav"));
  await page.getByRole("button", { name: "开始识别", exact: true }).click();
  await expect(page.locator(".live p")).toContainText("已接收音频");
  await page.getByRole("button", { name: "停止", exact: true }).click();
  await expect(page.locator(".transcripts article")).toHaveCount(1);
  await page.getByRole("button", { name: "重新识别", exact: true }).click();
  await expect(page.locator(".transcripts article")).toHaveCount(0);
  await expect(page.locator(".transcripts article")).toHaveCount(1, {
    timeout: 12000,
  });
});
