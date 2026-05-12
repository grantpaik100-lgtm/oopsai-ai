import type { MissingInfoQuestion, NormalizedInput } from "../types/api";

type StatusKind = "done" | "needsCheck" | "none" | "review";

interface FactorRow {
  label: string;
  value?: string;
  status: StatusKind;
}

interface AiFactorStatusPanelProps {
  normalized: NormalizedInput | null;
  missingInfoQuestions: MissingInfoQuestion[];
}

const statusLabels: Record<StatusKind, string> = {
  done: "완료",
  needsCheck: "확인 필요",
  none: "추천 없음",
  review: "기타/검토 필요",
};

const statusClasses: Record<StatusKind, string> = {
  done: "border-emerald-200 bg-emerald-50 text-emerald-800",
  needsCheck: "border-amber-200 bg-amber-50 text-amber-800",
  none: "border-stone-200 bg-stone-50 text-stone-600",
  review: "border-sky-200 bg-sky-50 text-sky-800",
};

const fieldGroups: Record<string, string[]> = {
  accident: ["accident_type"],
  work: ["work_type"],
  hazard: ["hazard"],
  environment: ["environment_factor"],
  human: ["human_factor"],
  equipment: ["equipment"],
};

function hasQuestion(fields: string[], questions: MissingInfoQuestion[]) {
  return questions.some((item) => fields.includes(item.field));
}

function isNone(value?: string | null) {
  return !value || value === "해당 없음";
}

function isReview(value?: string | null) {
  return value === "기타";
}

function statusForValue(value: string | undefined, needsCheck: boolean): StatusKind {
  if (needsCheck) return "needsCheck";
  if (isNone(value)) return "none";
  if (isReview(value)) return "review";
  return "done";
}

function statusForArray(values: string[], needsCheck: boolean): StatusKind {
  if (needsCheck) return "needsCheck";
  const filtered = values.filter((value) => value && value !== "해당 없음");
  if (filtered.length === 0) return "none";
  if (filtered.every((value) => value === "기타")) return "review";
  return "done";
}

function displayArray(values: string[]) {
  const filtered = values.filter((value) => value && value !== "해당 없음");
  return filtered.length > 0 ? filtered.join(", ") : undefined;
}

function buildRows(normalized: NormalizedInput, questions: MissingInfoQuestion[]): FactorRow[] {
  const secondary = normalized.secondary_hazards ?? [];
  return [
    {
      label: "사고유형",
      value: normalized.accident_type,
      status: statusForValue(normalized.accident_type, hasQuestion(fieldGroups.accident, questions)),
    },
    {
      label: "작업유형",
      value: normalized.work_type,
      status: statusForValue(normalized.work_type, hasQuestion(fieldGroups.work, questions)),
    },
    {
      label: "주요 위험요인",
      value: normalized.hazard_middle_category,
      status: statusForValue(normalized.hazard_middle_category, hasQuestion(fieldGroups.hazard, questions)),
    },
    {
      label: "부가 위험요인",
      value: secondary.map((item) => `${item.major} / ${item.middle}`).join(", "),
      status: secondary.length > 0 ? "done" : "none",
    },
    {
      label: "환경요인",
      value: displayArray(normalized.environment_factors),
      status: statusForArray(normalized.environment_factors, hasQuestion(fieldGroups.environment, questions)),
    },
    {
      label: "인적요인",
      value: displayArray(normalized.human_factors),
      status: statusForArray(normalized.human_factors, hasQuestion(fieldGroups.human, questions)),
    },
    {
      label: "사용장비",
      value: normalized.equipment ?? undefined,
      status: statusForValue(normalized.equipment ?? undefined, hasQuestion(fieldGroups.equipment, questions)),
    },
  ];
}

export default function AiFactorStatusPanel({ normalized, missingInfoQuestions }: AiFactorStatusPanelProps) {
  if (!normalized) return null;

  const rows = buildRows(normalized, missingInfoQuestions);

  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-field-900">AI가 현재 파악한 정보</h3>
          <p className="text-sm text-stone-600">정규화 결과와 부족정보 질문 기준으로 표시합니다.</p>
        </div>
        <div className="text-sm text-stone-600">
          신뢰도 {Math.round(normalized.confidence * 100)}% · 부족정보 질문 {missingInfoQuestions.length}개
        </div>
      </div>
      <div className="grid gap-2">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-2 rounded-md border border-stone-100 px-3 py-2 sm:grid-cols-[110px_1fr]">
            <div className="flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${statusClasses[row.status]}`}>
                {statusLabels[row.status]}
              </span>
              <span className="text-sm font-semibold text-stone-700">{row.label}</span>
            </div>
            <div className="text-sm leading-6 text-stone-900">{row.value || "판단 단서 부족"}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
