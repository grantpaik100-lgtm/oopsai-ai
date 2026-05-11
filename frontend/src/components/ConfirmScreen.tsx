import type { FormState } from "../pages/InputFlow";

interface ConfirmScreenProps {
  form: FormState;
  missingFields: string[];
  onEdit: (step: number) => void;
  onSubmit: () => void;
  submitting: boolean;
}

const rows: Array<{ label: string; key: keyof FormState; step: number }> = [
  { label: "상황 설명", key: "situationText", step: 0 },
  { label: "발생 일시", key: "occurredAt", step: 1 },
  { label: "발생 장소", key: "occurredLocation", step: 1 },
  { label: "사고유형", key: "accidentType", step: 2 },
  { label: "작업유형", key: "workType", step: 3 },
  { label: "위험요인", key: "hazards", step: 4 },
  { label: "환경요인", key: "environmentFactors", step: 5 },
  { label: "인적요인", key: "humanFactors", step: 6 },
  { label: "사용장비", key: "equipment", step: 7 },
];

function displayValue(value: string | string[]) {
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "미입력";
  return value || "미입력";
}

export default function ConfirmScreen({
  form,
  missingFields,
  onEdit,
  onSubmit,
  submitting,
}: ConfirmScreenProps) {
  const canSubmit = missingFields.length === 0 && !submitting;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-field-900">입력 내용 확인</h2>
        <p className="mt-1 text-sm text-stone-600">제출 전 필수 항목과 AI 분석 결과를 확인합니다.</p>
      </div>

      <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {rows.map((row) => {
          const missing = missingFields.includes(row.key);
          return (
            <div
              key={row.key}
              className={`grid gap-2 px-4 py-3 sm:grid-cols-[120px_1fr_auto] ${
                missing ? "bg-amber-50" : ""
              }`}
            >
              <div className="text-sm font-semibold text-stone-700">{row.label}</div>
              <div className="text-sm leading-6 text-stone-900">{displayValue(form[row.key])}</div>
              <button
                type="button"
                onClick={() => onEdit(row.step)}
                className="text-left text-sm font-semibold text-field-700 sm:text-right"
              >
                {missing ? "탭해서 입력하기" : "수정"}
              </button>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        disabled={!canSubmit}
        onClick={onSubmit}
        className="w-full rounded-md bg-field-700 px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-stone-300"
      >
        {submitting ? "제출 중" : "분석 결과 생성"}
      </button>
    </div>
  );
}
