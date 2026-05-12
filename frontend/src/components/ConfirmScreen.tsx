import type { FormState, OtherInputs } from "../pages/InputFlow";

interface ConfirmScreenProps {
  form: FormState;
  otherInputs: OtherInputs;
  missingQuestionAnswers: Record<string, string>;
  missingQuestionPrompts: Record<string, string>;
  missingFields: string[];
  onEdit: (step: number) => void;
  onSubmit: () => void;
  submitting: boolean;
}

const rows: Array<{ label: string; key: keyof FormState; step: number }> = [
  { label: "발생일시", key: "occurred_at", step: 0 },
  { label: "발생장소", key: "occurred_location", step: 0 },
  { label: "상황 설명", key: "situationText", step: 1 },
  { label: "사고유형", key: "accidentType", step: 3 },
  { label: "작업유형", key: "workType", step: 4 },
  { label: "위험요인", key: "hazards", step: 5 },
  { label: "환경요인", key: "environmentFactors", step: 6 },
  { label: "인적요인", key: "humanFactors", step: 7 },
  { label: "사용장비", key: "equipment", step: 8 },
];

const otherLabels: Record<keyof OtherInputs, string> = {
  accidentType: "사고유형 기타",
  workType: "작업유형 기타",
  hazards: "위험요인 기타",
  environmentFactors: "환경요인 기타",
  humanFactors: "인적요인 기타",
  equipment: "사용장비 기타",
};

function displayValue(value: string | string[]) {
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "미입력";
  return value || "미입력";
}

export default function ConfirmScreen({
  form,
  otherInputs,
  missingQuestionAnswers,
  missingQuestionPrompts,
  missingFields,
  onEdit,
  onSubmit,
  submitting,
}: ConfirmScreenProps) {
  const canSubmit = missingFields.length === 0 && !submitting;
  const otherRows = Object.entries(otherInputs).filter(([, value]) => value.trim());
  const questionRows = Object.entries(missingQuestionAnswers).filter(([, value]) => value.trim());

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-field-900">입력 내용 확인</h2>
        <p className="mt-1 text-sm text-stone-600">제출 전 발생 정보와 요인 분류를 확인합니다.</p>
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

      {otherRows.length > 0 && (
        <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {otherRows.map(([key, value]) => (
            <div key={key} className="grid gap-2 px-4 py-3 sm:grid-cols-[120px_1fr]">
              <div className="text-sm font-semibold text-stone-700">{otherLabels[key as keyof OtherInputs]}</div>
              <div className="text-sm leading-6 text-stone-900">{value}</div>
            </div>
          ))}
        </div>
      )}

      {questionRows.length > 0 && (
        <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {questionRows.map(([key, value], index) => (
            <div key={key} className="grid gap-2 px-4 py-3 sm:grid-cols-[120px_1fr]">
              <div className="text-sm font-semibold text-stone-700">추가 답변 {index + 1}</div>
              <div className="space-y-1 text-sm leading-6 text-stone-900">
                {missingQuestionPrompts[key] && (
                  <p>
                    <span className="font-semibold text-stone-700">질문: </span>
                    {missingQuestionPrompts[key]}
                  </p>
                )}
                <p>
                  <span className="font-semibold text-stone-700">답변: </span>
                  {value}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        disabled={!canSubmit}
        onClick={onSubmit}
        className="w-full rounded-md bg-field-700 px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-stone-300"
      >
        {submitting ? "제출 중" : "예방조치 분석"}
      </button>
    </div>
  );
}
