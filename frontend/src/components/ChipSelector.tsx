interface ChipSelectorProps {
  options: string[];
  aiRecommended?: string[];
  aiReason?: string;
  multi?: boolean;
  value: string[];
  onChange: (val: string[]) => void;
  error?: boolean;
  errorMsg?: string;
  otherWarning?: string;
}

export default function ChipSelector({
  options,
  aiRecommended = [],
  aiReason,
  multi = false,
  value,
  onChange,
  error = false,
  errorMsg,
  otherWarning,
}: ChipSelectorProps) {
  const toggle = (option: string) => {
    if (multi) {
      onChange(value.includes(option) ? value.filter((item) => item !== option) : [...value, option]);
      return;
    }
    onChange(value.includes(option) ? [] : [option]);
  };

  return (
    <div
      className={`rounded-lg border bg-white p-3 transition ${
        error ? "border-red-400" : "border-stone-200"
      }`}
    >
      {aiReason && (
        <div className="mb-3 rounded-md border border-indigo-100 bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
          {aiReason}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = value.includes(option);
          const recommended = aiRecommended.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              className={`min-h-10 rounded-md border px-3 py-2 text-sm font-medium transition ${
                selected
                  ? "border-field-700 bg-field-700 text-white"
                  : "border-stone-300 bg-white text-stone-800 hover:border-field-700"
              } ${recommended && !selected ? "border-indigo-400 bg-indigo-50 text-indigo-900" : ""}`}
            >
              <span>{option}</span>
              {recommended && (
                <span
                  className={`ml-2 rounded px-1.5 py-0.5 text-xs ${
                    selected ? "bg-white/20 text-white" : "bg-indigo-100 text-indigo-800"
                  }`}
                >
                  AI
                </span>
              )}
            </button>
          );
        })}
      </div>
      {error && errorMsg && <p className="mt-2 text-sm text-red-600">{errorMsg}</p>}
      {!error && otherWarning && <p className="mt-2 text-sm text-amber-700">{otherWarning}</p>}
    </div>
  );
}
