import { useMemo, useState } from "react";
import { analyzeIncident, normalizeIncident } from "../api/client";
import AiBubble from "../components/AiBubble";
import ChipSelector from "../components/ChipSelector";
import ConfirmScreen from "../components/ConfirmScreen";
import ProgressBar from "../components/ProgressBar";
import STTButton from "../components/STTButton";
import { CHIPS, CHIP_TAXONOMY_MAP, HAZARD_MAJOR_MAP } from "../constants/chips";
import type { AnalyzeRequest, AnalyzeResponse, NormalizedInput } from "../types/api";
import ResultDetail from "./ResultDetail";

export interface FormState {
  situationText: string;
  occurredAt: string;
  occurredLocation: string;
  accidentType: string;
  workType: string;
  hazards: string[];
  environmentFactors: string[];
  humanFactors: string[];
  equipment: string;
}

const initialForm: FormState = {
  situationText: "",
  occurredAt: "",
  occurredLocation: "",
  accidentType: "",
  workType: "",
  hazards: [],
  environmentFactors: [],
  humanFactors: [],
  equipment: "",
};

const stepTitles = [
  "상황 서술",
  "식별 정보",
  "사고유형",
  "작업유형",
  "위험요인",
  "환경요인",
  "인적요인",
  "사용장비",
  "확인",
  "결과",
];

const requiredStepMessages: Record<number, { key: keyof FormState; message: string }> = {
  2: { key: "accidentType", message: "사고유형을 선택해주세요" },
  3: { key: "workType", message: "작업유형을 선택해주세요" },
  4: { key: "hazards", message: "위험요인을 하나 이상 선택해주세요" },
  5: { key: "environmentFactors", message: "환경요인을 선택해주세요 (해당 없음 선택 가능)" },
  6: { key: "humanFactors", message: "인적요인을 선택해주세요 (해당 없음 선택 가능)" },
  7: { key: "equipment", message: "사용장비를 선택해주세요 (해당 없음 선택 가능)" },
};

const requiredConfirmKeys: Array<keyof FormState> = [
  "situationText",
  "accidentType",
  "workType",
  "hazards",
  "environmentFactors",
  "humanFactors",
  "equipment",
];

function isEmpty(value: string | string[]) {
  return !value || (Array.isArray(value) && value.length === 0);
}

function taxonomyValue(label: string) {
  return CHIP_TAXONOMY_MAP[label] ?? label;
}

function firstOrOther(values: string[], fallback = "기타") {
  return values[0] ? taxonomyValue(values[0]) : fallback;
}

function emptyAiRecommendations() {
  return {
    accident_type: [],
    work_type: [],
    hazard: [],
    environment_factors: [],
    human_factors: [],
    equipment: [],
    hazard_raw_matched: "",
    reason: "",
  };
}

function normalizeRecommendationValues(values: Array<string | null | undefined>) {
  return values.filter((value): value is string => Boolean(value)).map(taxonomyValue);
}

function validRecommendations(groupName: string, options: readonly string[], values: string[]) {
  const optionSet = new Set(options);
  return values.filter((value) => {
    const valid = optionSet.has(value);
    if (!valid) {
      console.warn(`[ai_recommendations] ${groupName} option not found: ${value}`);
    }
    return valid;
  });
}

function recommendationsOrFallback(
  groupName: string,
  options: readonly string[],
  recommended: string[] | undefined,
  fallback: Array<string | null | undefined>,
) {
  const values = recommended && recommended.length > 0 ? recommended : normalizeRecommendationValues(fallback);
  return validRecommendations(groupName, options, values);
}

function buildNormalizedFromForm(form: FormState, aiNormalized: NormalizedInput | null): NormalizedInput {
  const hazard = form.hazards[0] ?? "기타";

  return {
    accident_type: taxonomyValue(form.accidentType),
    work_type: form.workType,
    hazard_major_category: HAZARD_MAJOR_MAP[hazard] ?? aiNormalized?.hazard_major_category ?? "기타",
    hazard_middle_category: firstOrOther(form.hazards),
    environment_factors: form.environmentFactors.map(taxonomyValue),
    human_factors: form.humanFactors.map(taxonomyValue),
    equipment: form.equipment === "해당 없음" ? null : form.equipment,
    confidence: aiNormalized?.confidence ?? 0.8,
    ai_recommendations: aiNormalized?.ai_recommendations ?? emptyAiRecommendations(),
  };
}

export default function InputFlow() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [aiNormalized, setAiNormalized] = useState<NormalizedInput | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);

  const missingFields = useMemo(
    () => requiredConfirmKeys.filter((key) => isEmpty(form[key])),
    [form],
  );

  const aiRecommendations = useMemo(
    () => ({
      accidentType: recommendationsOrFallback(
        "사고유형",
        CHIPS.사고유형,
        aiNormalized?.ai_recommendations.accident_type,
        [aiNormalized?.accident_type],
      ),
      workType: recommendationsOrFallback(
        "작업유형",
        CHIPS.작업유형,
        aiNormalized?.ai_recommendations.work_type,
        [aiNormalized?.work_type],
      ),
      hazards: recommendationsOrFallback(
        "위험요인",
        CHIPS.위험요인,
        aiNormalized?.ai_recommendations.hazard,
        [aiNormalized?.hazard_middle_category],
      ),
      environmentFactors: recommendationsOrFallback(
        "환경요인",
        CHIPS.환경요인,
        aiNormalized?.ai_recommendations.environment_factors,
        aiNormalized?.environment_factors ?? [],
      ),
      humanFactors: recommendationsOrFallback(
        "인적요인",
        CHIPS.인적요인,
        aiNormalized?.ai_recommendations.human_factors,
        aiNormalized?.human_factors ?? [],
      ),
      equipment: recommendationsOrFallback(
        "사용장비",
        CHIPS.사용장비,
        aiNormalized?.ai_recommendations.equipment,
        [aiNormalized?.equipment],
      ),
    }),
    [aiNormalized],
  );

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setStepError(null);
  };

  const runNormalize = async () => {
    if (!form.situationText.trim()) {
      setError("상황을 먼저 입력해주세요.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const normalized = await normalizeIncident({
        situation_text: form.situationText,
        fields: {
          accident_type_raw: form.accidentType || null,
          work_type_raw: form.workType || null,
          hazard_raw: form.hazards,
          environment_factor_raw: form.environmentFactors,
          human_factor_raw: form.humanFactors,
          equipment_raw: form.equipment || null,
        },
      });
      setAiNormalized(normalized);
      setStep(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 분석에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const goNext = () => {
    const required = requiredStepMessages[step];
    if (required && isEmpty(form[required.key])) {
      setStepError(required.message);
      return;
    }
    setStep((current) => Math.min(current + 1, 8));
  };

  const submitAnalyze = async () => {
    if (missingFields.length > 0) return;

    setSubmitLoading(true);
    setError(null);
    try {
      const request: AnalyzeRequest = {
        raw_input: form.situationText,
        normalized: buildNormalizedFromForm(form, aiNormalized),
        meta: {
          submitted_by: "user",
          occurred_at: form.occurredAt || null,
          occurred_location: form.occurredLocation || null,
        },
      };
      const analyzeResult = await analyzeIncident(request);
      setResult(analyzeResult);
      setStep(9);
    } catch (err) {
      setError(err instanceof Error ? err.message : "결과 생성에 실패했습니다.");
    } finally {
      setSubmitLoading(false);
    }
  };

  const reset = () => {
    setForm(initialForm);
    setAiNormalized(null);
    setResult(null);
    setError(null);
    setStepError(null);
    setStep(0);
  };

  return (
    <main className="min-h-screen px-4 py-6 sm:py-10">
      <div className="mx-auto max-w-2xl">
        <header className="mb-5">
          <p className="text-sm font-semibold text-field-700">군 안전관리 아차사고 신고</p>
          <h1 className="mt-1 text-2xl font-bold tracking-normal text-field-900">AI 예방대책 입력</h1>
        </header>

        <section className="rounded-lg border border-stone-200 bg-field-50 p-4 shadow-sm sm:p-6">
          {step < 9 && (
            <div className="mb-5">
              <ProgressBar current={Math.min(step + 1, 9)} total={9} />
              <h2 className="mt-4 text-xl font-bold text-field-900">{stepTitles[step]}</h2>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {aiNormalized && step > 1 && step < 8 && (
            <div className="mb-4">
              <AiBubble>
                mock normalize 결과를 추천 칩으로 표시했습니다. 추천과 다르게 직접 선택해도 됩니다.
              </AiBubble>
            </div>
          )}

          {step === 0 && (
            <div className="space-y-4">
              <textarea
                value={form.situationText}
                onChange={(event) => updateForm("situationText", event.target.value)}
                rows={7}
                placeholder="예: 사격훈련 중 총기 부품이 튕겨 눈을 다칠 뻔했습니다."
                className="w-full resize-none rounded-lg border border-stone-300 bg-white p-3 text-sm leading-6 outline-none focus:border-field-700"
              />
              <div className="flex flex-col gap-2 sm:flex-row">
                <STTButton />
                <button
                  type="button"
                  onClick={runNormalize}
                  disabled={loading}
                  className="rounded-md bg-field-700 px-4 py-2 text-sm font-bold text-white disabled:bg-stone-300"
                >
                  {loading ? "분석 중" : "AI 분석"}
                </button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-semibold text-stone-700">발생 일시</span>
                <input
                  type="datetime-local"
                  value={form.occurredAt}
                  onChange={(event) => updateForm("occurredAt", event.target.value)}
                  className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
                />
              </label>
              <label className="block">
                <span className="text-sm font-semibold text-stone-700">발생 장소</span>
                <input
                  value={form.occurredLocation}
                  onChange={(event) => updateForm("occurredLocation", event.target.value)}
                  placeholder="예: 사격장, 정비고, 취사장"
                  className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
                />
              </label>
            </div>
          )}

          {step === 2 && (
            <ChipSelector
              options={[...CHIPS.사고유형]}
              value={form.accidentType ? [form.accidentType] : []}
              onChange={(value) => updateForm("accidentType", value[0] ?? "")}
              aiRecommended={aiRecommendations.accidentType}
              aiReason={aiNormalized ? `신뢰도 ${Math.round(aiNormalized.confidence * 100)}% 기준 추천입니다.` : undefined}
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
            />
          )}

          {step === 3 && (
            <ChipSelector
              options={[...CHIPS.작업유형]}
              value={form.workType ? [form.workType] : []}
              onChange={(value) => updateForm("workType", value[0] ?? "")}
              aiRecommended={aiRecommendations.workType}
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
            />
          )}

          {step === 4 && (
            <ChipSelector
              options={[...CHIPS.위험요인]}
              value={form.hazards}
              onChange={(value) => updateForm("hazards", value)}
              aiRecommended={aiRecommendations.hazards}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
            />
          )}

          {step === 5 && (
            <ChipSelector
              options={[...CHIPS.환경요인]}
              value={form.environmentFactors}
              onChange={(value) => updateForm("environmentFactors", value)}
              aiRecommended={aiRecommendations.environmentFactors}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
            />
          )}

          {step === 6 && (
            <ChipSelector
              options={[...CHIPS.인적요인]}
              value={form.humanFactors}
              onChange={(value) => updateForm("humanFactors", value)}
              aiRecommended={aiRecommendations.humanFactors}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
            />
          )}

          {step === 7 && (
            <div className="space-y-3">
              <ChipSelector
                options={[...CHIPS.사용장비]}
                value={form.equipment ? [form.equipment] : []}
                onChange={(value) => updateForm("equipment", value[0] ?? "")}
                aiRecommended={aiRecommendations.equipment}
                error={Boolean(stepError)}
                errorMsg={stepError ?? undefined}
              />
              <input
                value={CHIPS.사용장비.includes(form.equipment as (typeof CHIPS.사용장비)[number]) ? "" : form.equipment}
                onChange={(event) => updateForm("equipment", event.target.value)}
                placeholder="기타 장비 직접 입력"
                className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
              />
            </div>
          )}

          {step === 8 && (
            <ConfirmScreen
              form={form}
              missingFields={missingFields}
              onEdit={setStep}
              onSubmit={submitAnalyze}
              submitting={submitLoading}
            />
          )}

          {step === 9 && result && <ResultDetail result={result} onReset={reset} />}

          {step > 0 && step < 8 && (
            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => setStep((current) => Math.max(current - 1, 0))}
                className="flex-1 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-700"
              >
                이전
              </button>
              <button
                type="button"
                onClick={goNext}
                className="flex-1 rounded-md bg-field-700 px-4 py-2 text-sm font-bold text-white"
              >
                다음
              </button>
            </div>
          )}

          {step === 8 && (
            <button
              type="button"
              onClick={() => setStep(7)}
              className="mt-4 w-full rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-700"
            >
              이전
            </button>
          )}
        </section>
      </div>
    </main>
  );
}
