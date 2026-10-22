import "./globals.css";
export const metadata = {
  title: "llmErV · 机场应急语音平台",
  description: "机场应急救援语音辅助分析",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
