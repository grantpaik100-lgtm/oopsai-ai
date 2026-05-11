import type { ReactNode } from "react";

interface AiBubbleProps {
  title?: string;
  children: ReactNode;
}

export default function AiBubble({ title = "AI 추천", children }: AiBubbleProps) {
  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm text-indigo-950">
      <p className="mb-1 font-semibold">{title}</p>
      <div className="leading-6">{children}</div>
    </div>
  );
}
