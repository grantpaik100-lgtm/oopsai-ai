import { useMemo, useState } from "react";
import { analyzeIncident, normalizeIncident } from "../api/client";
import AiBubble from "../components/AiBubble";
import AiDebugPanel from "../components/AiDebugPanel";
import AiFactorStatusPanel from "../components/AiFactorStatusPanel";
import ChipSelector from "../components/ChipSelector";
import ConfirmScreen from "../components/ConfirmScreen";
import ProgressBar from "../components/ProgressBar";
import STTButton from "../components/STTButton";
import { CHIPS, CHIP_TAXONOMY_MAP, HAZARD_MAJOR_MAP } from "../constants/chips";
import type { AnalyzeRequest, AnalyzeResponse, MissingInfoQuestion, NormalizedInput, NormalizeFields } from "../types/api";
import ResultDetail from "./ResultDetail";

export interface FormState {
  occurred_at: string;
  occurred_location: string;
  situationText: string;
  accidentType: string;
  workType: string;
  hazards: string[];
  environmentFactors: string[];
  humanFactors: string[];
  equipment: string;
}

export interface OtherInputs {
  accidentType: string;
  workType: string;
  hazards: string;
  environmentFactors: string;
  humanFactors: string;
  equipment: string;
}

const initialForm: FormState = {
  occurred_at: "",
  occurred_location: "",
  situationText: "",
  accidentType: "",
  workType: "",
  hazards: [],
  environmentFactors: [],
  humanFactors: [],
  equipment: "",
};

const initialOtherInputs: OtherInputs = {
  accidentType: "",
  workType: "",
  hazards: "",
  environmentFactors: "",
  humanFactors: "",
  equipment: "",
};

const stepTitles = [
  "발생 정보",
  "상황 입력",
  "AI 정보부족질문",
  "사고유형 확인",
  "작업유형 확인",
  "위험요인 확인",
  "환경요인 확인",
  "인적요인 확인",
  "사용장비 확인",
  "입력 내용 확인",
  "분석 결과",
];

const requiredStepMessages: Record<number, { key: keyof FormState; message: string }> = {
  3: { key: "accidentType", message: "사고유형을 선택해주세요" },
  4: { key: "workType", message: "작업유형을 선택해주세요" },
  5: { key: "hazards", message: "위험요인을 하나 이상 선택해주세요" },
  6: { key: "environmentFactors", message: "환경요인을 선택해주세요 (해당 없음 선택 가능)" },
  7: { key: "humanFactors", message: "인적요인을 선택해주세요 (해당 없음 선택 가능)" },
  8: { key: "equipment", message: "사용장비를 선택해주세요 (해당 없음 선택 가능)" },
};

const requiredConfirmKeys: Array<keyof FormState> = [
  "occurred_at",
  "occurred_location",
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

function withOtherEvidence(values: string[], otherValue: string) {
  const trimmed = otherValue.trim();
  if (!values.includes("기타") || !trimmed) return values;
  return [...values, `기타: ${trimmed}`];
}

function singleWithOtherEvidence(value: string, otherValue: string) {
  const trimmed = otherValue.trim();
  if (value !== "기타" || !trimmed) return value || null;
  return `기타: ${trimmed}`;
}

function otherWarning(selected: string | string[], otherValue: string) {
  const hasOther = Array.isArray(selected) ? selected.includes("기타") : selected === "기타";
  if (!hasOther || otherValue.trim()) return undefined;
  return "기타를 선택한 경우 내용을 적으면 AI 분석 정확도가 올라갑니다.";
}

function missingQuestionKey(item: MissingInfoQuestion, index: number) {
  return `${item.field}-${index}`;
}

function buildNormalizeFields(form: FormState, otherInputs: OtherInputs): NormalizeFields {
  return {
    accident_type_raw: singleWithOtherEvidence(form.accidentType, otherInputs.accidentType),
    work_type_raw: singleWithOtherEvidence(form.workType, otherInputs.workType),
    hazard_raw: withOtherEvidence(form.hazards, otherInputs.hazards),
    environment_factor_raw: withOtherEvidence(form.environmentFactors, otherInputs.environmentFactors),
    human_factor_raw: withOtherEvidence(form.humanFactors, otherInputs.humanFactors),
    equipment_raw: singleWithOtherEvidence(form.equipment, otherInputs.equipment),
  };
}

function buildQuestionPromptMap(questions: MissingInfoQuestion[]) {
  return Object.fromEntries(questions.map((item, index) => [missingQuestionKey(item, index), item.question]));
}

function actionableMissingInfoQuestions(questions: MissingInfoQuestion[], form: FormState) {
  return questions.filter((item) => {
    if (item.field === "occurred_at" && form.occurred_at) return false;
    if (item.field === "occurred_location" && form.occurred_location.trim()) return false;
    return true;
  });
}

function buildSituationWithMissingAnswers(
  situationText: string,
  questions: MissingInfoQuestion[],
  answers: Record<string, string>,
) {
  const answerLines = questions
    .map((item, index) => {
      const answer = answers[missingQuestionKey(item, index)]?.trim();
      return answer ? `- ${item.question}: ${answer}` : null;
    })
    .filter((line): line is string => Boolean(line));

  if (answerLines.length === 0) return situationText;
  return `${situationText.trim()}\n\n[추가 답변]\n${answerLines.join("\n")}`;
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
    secondary_hazards: aiNormalized?.secondary_hazards ?? [],
    missing_info_questions: aiNormalized?.missing_info_questions ?? [],
  };
}

function hasFilledValue(value: string | null | undefined) {
  return Boolean(value && value !== "기타" && value !== "해당 없음");
}

function hasFilledArray(values: string[] | undefined) {
  return Boolean(values?.some((value) => value && value !== "기타" && value !== "해당 없음"));
}

function buildReanalysisMessage(
  before: NormalizedInput | null,
  after: NormalizedInput,
  visibleQuestionCount: number,
) {
  const improved: string[] = [];
  if (!hasFilledValue(before?.accident_type) && hasFilledValue(after.accident_type)) improved.push("사고유형");
  if (!hasFilledValue(before?.work_type) && hasFilledValue(after.work_type)) improved.push("작업유형");
  if (!hasFilledValue(before?.hazard_middle_category) && hasFilledValue(after.hazard_middle_category)) {
    improved.push("위험요인");
  }
  if (!hasFilledValue(before?.equipment) && hasFilledValue(after.equipment)) improved.push("사용장비");
  if ((before?.secondary_hazards?.length ?? 0) < (after.secondary_hazards?.length ?? 0)) {
    improved.push("부가 위험요인");
  }
  if (!hasFilledArray(before?.environment_factors) && hasFilledArray(after.environment_factors)) {
    improved.push("환경요인");
  }
  if (!hasFilledArray(before?.human_factors) && hasFilledArray(after.human_factors)) improved.push("인적요인");

  if (visibleQuestionCount === 0) {
    return improved.length > 0
      ? `답변이 반영되었습니다. ${improved.join(", ")} 정보가 보강되어 요인 확인 단계로 이동합니다.`
      : "추가 질문이 없어 요인 확인 단계로 이동합니다.";
  }
  if (improved.length > 0) {
    return `답변이 반영되었습니다. ${improved.join(", ")} 정보가 보강되었습니다.`;
  }
  return "답변을 반영했지만 아직 확인이 필요한 정보가 있습니다.";
}

export default function InputFlow() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [otherInputs, setOtherInputs] = useState<OtherInputs>(initialOtherInputs);
  const [missingQuestionAnswers, setMissingQuestionAnswers] = useState<Record<string, string>>({});
  const [missingQuestionPrompts, setMissingQuestionPrompts] = useState<Record<string, string>>({});
  const [aiNormalized, setAiNormalized] = useState<NormalizedInput | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [reanalyzeLoading, setReanalyzeLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  const [reanalyzeMessage, setReanalyzeMessage] = useState<string | null>(null);

  const missingInfoQuestions = useMemo(
    () => actionableMissingInfoQuestions(aiNormalized?.missing_info_questions ?? [], form),
    [aiNormalized?.missing_info_questions, form],
  );

  const missingFields = useMemo(
    () => requiredConfirmKeys.filter((key) => isEmpty(form[key])),
    [form],
  );

  const aiRecommendations = useMemo(
    () => ({
      accidentType: recommendationsOrFallback(
        "사고유형",
        CHIPS.사고유형,
        aiNormalized?.ai_recommendations?.accident_type,
        [aiNormalized?.accident_type],
      ),
      workType: recommendationsOrFallback(
        "작업유형",
        CHIPS.작업유형,
        aiNormalized?.ai_recommendations?.work_type,
        [aiNormalized?.work_type],
      ),
      hazards: recommendationsOrFallback(
        "위험요인",
        CHIPS.위험요인,
        aiNormalized?.ai_recommendations?.hazard,
        [aiNormalized?.hazard_middle_category],
      ),
      environmentFactors: recommendationsOrFallback(
        "환경요인",
        CHIPS.환경요인,
        aiNormalized?.ai_recommendations?.environment_factors,
        aiNormalized?.environment_factors ?? [],
      ),
      humanFactors: recommendationsOrFallback(
        "인적요인",
        CHIPS.인적요인,
        aiNormalized?.ai_recommendations?.human_factors,
        aiNormalized?.human_factors ?? [],
      ),
      equipment: recommendationsOrFallback(
        "사용장비",
        CHIPS.사용장비,
        aiNormalized?.ai_recommendations?.equipment,
        [aiNormalized?.equipment],
      ),
    }),
    [aiNormalized],
  );

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setStepError(null);
  };

  const updateOtherInput = (key: keyof OtherInputs, value: string) => {
    setOtherInputs((current) => ({ ...current, [key]: value }));
  };

  const runNormalize = async () => {
    if (!form.situationText.trim()) {
      setStepError("상황 내용을 입력해주세요");
      return;
    }

    setLoading(true);
    setError(null);
    setStepError(null);
    try {
      const normalized = await normalizeIncident({
        situation_text: form.situationText,
        fields: buildNormalizeFields(form, otherInputs),
      });
      const nextQuestions = actionableMissingInfoQuestions(normalized.missing_info_questions ?? [], form);
      setAiNormalized(normalized);
      setMissingQuestionAnswers({});
      setMissingQuestionPrompts(buildQuestionPromptMap(nextQuestions));
      setReanalyzeMessage(null);
      setStep(nextQuestions.length > 0 ? 2 : 3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 분석에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const rerunNormalizeWithMissingAnswers = async () => {
    if (!form.situationText.trim()) {
      setStepError("상황 내용을 입력해주세요");
      return;
    }

    setReanalyzeLoading(true);
    setError(null);
    setStepError(null);
    try {
      const normalized = await normalizeIncident({
        situation_text: buildSituationWithMissingAnswers(form.situationText, missingInfoQuestions, missingQuestionAnswers),
        fields: buildNormalizeFields(form, otherInputs),
      });
      const nextQuestions = actionableMissingInfoQuestions(normalized.missing_info_questions ?? [], form);
      const message = buildReanalysisMessage(aiNormalized, normalized, nextQuestions.length);
      setAiNormalized(normalized);
      setMissingQuestionPrompts((current) => ({
        ...current,
        ...buildQuestionPromptMap(nextQuestions),
      }));
      setReanalyzeMessage(message);
      setStep(nextQuestions.length > 0 ? 2 : 3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "재분석에 실패했습니다.");
    } finally {
      setReanalyzeLoading(false);
    }
  };

  const goNext = () => {
    if (step === 0) {
      if (!form.occurred_at) {
        setStepError("발생일시를 입력해주세요");
        return;
      }
      if (!form.occurred_location.trim()) {
        setStepError("발생장소를 입력해주세요");
        return;
      }
      setStep(1);
      return;
    }

    if (step === 1) {
      if (!form.situationText.trim()) {
        setStepError("상황 내용을 입력해주세요");
        return;
      }
      setStep(aiNormalized ? ((missingInfoQuestions.length > 0 ? 2 : 3)) : 1);
      return;
    }

    // TODO: 1-B 이후 질문별 필수 여부가 내려오면 여기서 필수 답변 검증을 적용한다.
    if (step === 2) {
      setStep(3);
      return;
    }

    const required = requiredStepMessages[step];
    if (required && isEmpty(form[required.key])) {
      setStepError(required.message);
      return;
    }
    setStep((current) => Math.min(current + 1, 9));
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
          submitted_by: "user_001",
          occurred_at: form.occurred_at,
          occurred_location: form.occurred_location,
        },
      };
      const analyzeResult = await analyzeIncident(request);
      setResult(analyzeResult);
      setStep(10);
    } catch (err) {
      setError(err instanceof Error ? err.message : "결과 생성에 실패했습니다.");
    } finally {
      setSubmitLoading(false);
    }
  };

  const reset = () => {
    setForm(initialForm);
    setOtherInputs(initialOtherInputs);
    setMissingQuestionAnswers({});
    setMissingQuestionPrompts({});
    setAiNormalized(null);
    setResult(null);
    setError(null);
    setStepError(null);
    setReanalyzeMessage(null);
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
          {step < 10 && (
            <div className="mb-5">
              <ProgressBar current={Math.min(step + 1, 10)} total={10} />
              <h2 className="mt-4 text-xl font-bold text-field-900">{stepTitles[step]}</h2>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {reanalyzeMessage && (
            <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {reanalyzeMessage}
            </div>
          )}

          {aiNormalized && step >= 3 && step <= 8 && (
            <div className="mb-4 space-y-4">
              <AiBubble>
                AI 정규화 결과를 기준으로 추천 칩을 표시했습니다. 실제 상황과 다르면 직접 수정할 수 있습니다.
              </AiBubble>
              <AiFactorStatusPanel normalized={aiNormalized} missingInfoQuestions={missingInfoQuestions} />
            </div>
          )}

          {step === 0 && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-semibold text-stone-700">발생일시</span>
                <input
                  type="datetime-local"
                  value={form.occurred_at}
                  onChange={(event) => updateForm("occurred_at", event.target.value)}
                  className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
                />
              </label>
              <label className="block">
                <span className="text-sm font-semibold text-stone-700">발생장소</span>
                <input
                  value={form.occurred_location}
                  onChange={(event) => updateForm("occurred_location", event.target.value)}
                  placeholder="예: 사격장"
                  className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
                />
              </label>
              {stepError && <p className="text-sm text-red-600">{stepError}</p>}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <p className="text-sm leading-6 text-stone-600">
                무슨 작업 중이었는지, 어떤 위험이 있었는지, 장비·보호구·장소 상황을 설명해주세요.
              </p>
              <textarea
                value={form.situationText}
                onChange={(event) => updateForm("situationText", event.target.value)}
                rows={7}
                placeholder="예: 사격훈련 중 총기 부품이 튕겨 눈을 다칠 뻔했습니다. 보호안경을 착용하지 않았고 주변 통제가 부족했습니다."
                className="w-full resize-none rounded-lg border border-stone-300 bg-white p-3 text-sm leading-6 outline-none focus:border-field-700"
              />
              {stepError && <p className="text-sm text-red-600">{stepError}</p>}
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

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-field-900">AI가 추가로 확인하고 싶은 정보</h3>
                <p className="mt-1 text-sm leading-6 text-stone-600">
                  입력만으로 판단하기 어려운 항목이 있으면 아래 질문에 답해주세요. 답변을 반영하면 사고유형과 위험요인 추천이 더 정확해집니다.
                </p>
              </div>
              <AiFactorStatusPanel normalized={aiNormalized} missingInfoQuestions={missingInfoQuestions} />
              {missingInfoQuestions.length > 0 ? (
                missingInfoQuestions.map((item, index) => {
                  const key = missingQuestionKey(item, index);
                  return (
                    <div key={key} className="rounded-lg border border-stone-200 bg-white p-3">
                      <p className="text-sm font-semibold text-stone-900">{item.question}</p>
                      <p className="mt-1 text-xs leading-5 text-stone-500">{item.reason}</p>
                      <textarea
                        value={missingQuestionAnswers[key] ?? ""}
                        onChange={(event) => {
                          setMissingQuestionAnswers((current) => ({ ...current, [key]: event.target.value }));
                          setMissingQuestionPrompts((current) => ({ ...current, [key]: item.question }));
                        }}
                        onFocus={() =>
                          setMissingQuestionPrompts((current) => ({ ...current, [key]: item.question }))
                        }
                        rows={3}
                        placeholder="답변 입력"
                        className="mt-3 w-full resize-none rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
                      />
                    </div>
                  );
                })
              ) : (
                <div className="rounded-lg border border-stone-200 bg-white px-3 py-4 text-sm text-stone-600">
                  추가 질문 없음
                </div>
              )}
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={rerunNormalizeWithMissingAnswers}
                  disabled={reanalyzeLoading}
                  className="flex-1 rounded-md bg-field-700 px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-stone-300"
                >
                  {reanalyzeLoading ? "재분석 중" : "답변 반영 후 다시 분석"}
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  disabled={reanalyzeLoading}
                  className="flex-1 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-700 disabled:cursor-not-allowed disabled:bg-stone-100 disabled:text-stone-400"
                >
                  그대로 진행
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <FactorStep
              options={[...CHIPS.사고유형]}
              value={form.accidentType ? [form.accidentType] : []}
              onChange={(value) => updateForm("accidentType", value[0] ?? "")}
              aiRecommended={aiRecommendations.accidentType}
              recommendationMissing={aiRecommendations.accidentType.length === 0}
              aiReason={aiNormalized ? `신뢰도 ${Math.round(aiNormalized.confidence * 100)}% 기준 추천입니다.` : undefined}
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.accidentType}
              onOtherChange={(value) => updateOtherInput("accidentType", value)}
              otherWarning={otherWarning(form.accidentType, otherInputs.accidentType)}
            />
          )}

          {step === 4 && (
            <FactorStep
              options={[...CHIPS.작업유형]}
              value={form.workType ? [form.workType] : []}
              onChange={(value) => updateForm("workType", value[0] ?? "")}
              aiRecommended={aiRecommendations.workType}
              recommendationMissing={aiRecommendations.workType.length === 0}
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.workType}
              onOtherChange={(value) => updateOtherInput("workType", value)}
              otherWarning={otherWarning(form.workType, otherInputs.workType)}
            />
          )}

          {step === 5 && (
            <FactorStep
              options={[...CHIPS.위험요인]}
              value={form.hazards}
              onChange={(value) => updateForm("hazards", value)}
              aiRecommended={aiRecommendations.hazards}
              recommendationMissing={aiRecommendations.hazards.length === 0}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.hazards}
              onOtherChange={(value) => updateOtherInput("hazards", value)}
              otherWarning={otherWarning(form.hazards, otherInputs.hazards)}
            />
          )}

          {step === 6 && (
            <FactorStep
              options={[...CHIPS.환경요인]}
              value={form.environmentFactors}
              onChange={(value) => updateForm("environmentFactors", value)}
              aiRecommended={aiRecommendations.environmentFactors}
              recommendationMissing={aiRecommendations.environmentFactors.length === 0}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.environmentFactors}
              onOtherChange={(value) => updateOtherInput("environmentFactors", value)}
              otherWarning={otherWarning(form.environmentFactors, otherInputs.environmentFactors)}
            />
          )}

          {step === 7 && (
            <FactorStep
              options={[...CHIPS.인적요인]}
              value={form.humanFactors}
              onChange={(value) => updateForm("humanFactors", value)}
              aiRecommended={aiRecommendations.humanFactors}
              recommendationMissing={aiRecommendations.humanFactors.length === 0}
              multi
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.humanFactors}
              onOtherChange={(value) => updateOtherInput("humanFactors", value)}
              otherWarning={otherWarning(form.humanFactors, otherInputs.humanFactors)}
            />
          )}

          {step === 8 && (
            <FactorStep
              options={[...CHIPS.사용장비]}
              value={form.equipment ? [form.equipment] : []}
              onChange={(value) => updateForm("equipment", value[0] ?? "")}
              aiRecommended={aiRecommendations.equipment}
              recommendationMissing={aiRecommendations.equipment.length === 0}
              error={Boolean(stepError)}
              errorMsg={stepError ?? undefined}
              otherValue={otherInputs.equipment}
              onOtherChange={(value) => updateOtherInput("equipment", value)}
              otherWarning={otherWarning(form.equipment, otherInputs.equipment)}
            />
          )}

          {step === 9 && (
            <ConfirmScreen
              form={form}
              otherInputs={otherInputs}
              missingQuestionAnswers={missingQuestionAnswers}
              missingQuestionPrompts={missingQuestionPrompts}
              missingFields={missingFields}
              onEdit={setStep}
              onSubmit={submitAnalyze}
              submitting={submitLoading}
            />
          )}

          {step === 10 && result && <ResultDetail result={result} onReset={reset} />}

          <AiDebugPanel
            data={{
              step,
              form,
              normalizeFields: buildNormalizeFields(form, otherInputs),
              otherInputs,
              missingQuestionAnswers,
              missingQuestionPrompts,
              aiNormalized,
              analyzeResult: result,
              normalizeConfidence: aiNormalized?.confidence,
              analysisReason: result?.analysis_reason,
              riskScoreReasons: result?.risk_score?.reasons,
              preventionRanking: result?.prevention_list?.map((item) => ({
                prevention_id: item.prevention_id,
                priority: item.priority,
                recommended_reason: item.recommended_reason,
              })),
              actionGuideSummary: result?.action_guide?.summary,
            }}
          />

          {step < 9 && step !== 1 && step !== 2 && (
            <div className="mt-6 flex gap-2">
              {step > 0 && (
                <button
                  type="button"
                  onClick={() => setStep((current) => Math.max(current - 1, 0))}
                  className="flex-1 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-700"
                >
                  이전
                </button>
              )}
              <button
                type="button"
                onClick={goNext}
                className="flex-1 rounded-md bg-field-700 px-4 py-2 text-sm font-bold text-white"
              >
                다음
              </button>
            </div>
          )}

          {step === 1 && (
            <button
              type="button"
              onClick={() => setStep(0)}
              className="mt-6 w-full rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-700"
            >
              이전
            </button>
          )}

          {step === 9 && (
            <button
              type="button"
              onClick={() => setStep(8)}
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

interface FactorStepProps {
  options: string[];
  aiRecommended?: string[];
  aiReason?: string;
  recommendationMissing?: boolean;
  multi?: boolean;
  value: string[];
  onChange: (value: string[]) => void;
  error?: boolean;
  errorMsg?: string;
  otherValue: string;
  onOtherChange: (value: string) => void;
  otherWarning?: string;
}

function FactorStep({
  options,
  aiRecommended,
  aiReason,
  recommendationMissing,
  multi,
  value,
  onChange,
  error,
  errorMsg,
  otherValue,
  onOtherChange,
  otherWarning,
}: FactorStepProps) {
  const showOtherInput = value.includes("기타");

  return (
    <div className="space-y-3">
      <ChipSelector
        options={options}
        value={value}
        onChange={onChange}
        aiRecommended={aiRecommended}
        aiReason={aiReason}
        multi={multi}
        error={error}
        errorMsg={errorMsg}
        otherWarning={otherWarning}
      />
      {recommendationMissing && (
        <p className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-600">
          AI 추천 없음: 입력에서 이 항목을 판단할 단서가 부족합니다.
        </p>
      )}
      {showOtherInput && (
        <label className="block">
          <span className="text-sm font-semibold text-stone-700">기타 내용</span>
          <textarea
            value={otherValue}
            onChange={(event) => onOtherChange(event.target.value)}
            rows={3}
            placeholder="표준 분류로 판단할 수 있도록 구체적인 내용을 입력해주세요."
            className="mt-1 w-full resize-none rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-field-700"
          />
        </label>
      )}
    </div>
  );
}
