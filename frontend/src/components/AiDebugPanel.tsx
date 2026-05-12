interface AiDebugPanelProps {
  title?: string;
  data: Record<string, unknown>;
}

function shouldShowDebug() {
  if (import.meta.env.DEV) return true;
  return new URLSearchParams(window.location.search).get("debug") === "1";
}

export default function AiDebugPanel({ title = "AI Debug", data }: AiDebugPanelProps) {
  if (!shouldShowDebug()) return null;

  const json = JSON.stringify(data, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
    } catch {
      console.warn("AI Debug JSON copy failed");
    }
  };

  return (
    <details className="mt-4 rounded-lg border border-stone-300 bg-stone-950 text-stone-100">
      <summary className="cursor-pointer px-4 py-3 text-sm font-bold">{title}</summary>
      <div className="border-t border-stone-700 p-4">
        <button
          type="button"
          onClick={copy}
          className="mb-3 rounded-md border border-stone-500 px-3 py-1 text-xs font-semibold text-stone-100"
        >
          복사
        </button>
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words text-xs leading-5">
          {json}
        </pre>
      </div>
    </details>
  );
}
