import { useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import { analyzeIncident, generateActionImage, normalizeIncident, pingBackend, startCase } from "../api/client";
import type {
  AnalyzeResponse,
  GenerateActionImageResponse,
  MissingInfoQuestion,
  NormalizedInput,
  PreventionItem,
  SourceImage,
} from "../types/api";

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

type Step = "photo" | "questions" | "type" | "prevention" | "action" | "completionPhoto" | "preview" | "done";
type PickMode = "camera" | "gallery";
type ActionImageStatus = "idle" | "loading" | "success" | "error";

type BrowserSpeechRecognitionEvent = Event & {
  results: ArrayLike<{
    isFinal: boolean;
    0: {
      transcript: string;
    };
  }>;
};

type BrowserSpeechRecognitionErrorEvent = Event & {
  error?: string;
};

interface BrowserSpeechRecognition extends EventTarget {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => BrowserSpeechRecognition;
    webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
  }
}

const steps: Array<[Step, string]> = [
  ["photo", "위험"],
  ["questions", "질문"],
  ["type", "유형"],
  ["prevention", "예방"],
  ["action", "조치"],
  ["completionPhoto", "사진"],
  ["preview", "확인"],
  ["done", "완료"],
];

const accidentTypes = ["화재", "폭발", "떨어짐(추락)", "끼임(협착)", "부딪힘(충격)", "붕괴", "감전", "중독(질식)", "온열질환", "기타"];
const demoText = "전기 배선함 인근 전선 피복이 벗겨져 있어 감전 위험이 있었습니다. 전원을 차단하지 않은 상태에서 점검하려 했고, 검전도 하지 않았습니다.";

function nowInputValue() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function stripDataUrl(dataUrl: string) {
  return dataUrl.includes(",") ? dataUrl.split(",", 2)[1] : dataUrl;
}

function fileToSourceImage(file: File): Promise<SourceImage> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("사진을 읽지 못했습니다."));
    reader.onload = () => {
      const previewUrl = String(reader.result ?? "");
      resolve({
        image_id: `local-${Date.now()}`,
        filename: file.name,
        mime_type: file.type || "image/jpeg",
        base64_data: stripDataUrl(previewUrl),
        preview_url: previewUrl,
        metadata: {
          size: file.size,
          source: "frontend_file_input",
        },
      });
    };
    reader.readAsDataURL(file);
  });
}

function closestAccidentType(value?: string) {
  const text = value ?? "";
  if (text.includes("화재")) return "화재";
  if (text.includes("폭발") || text.includes("파열")) return "폭발";
  if (text.includes("추락") || text.includes("떨어")) return "떨어짐(추락)";
  if (text.includes("끼임") || text.includes("협착")) return "끼임(협착)";
  if (text.includes("충격") || text.includes("부딪")) return "부딪힘(충격)";
  if (text.includes("붕괴")) return "붕괴";
  if (text.includes("감전")) return "감전";
  if (text.includes("질식") || text.includes("중독")) return "중독(질식)";
  if (text.includes("온열")) return "온열질환";
  return text ? "기타" : "";
}

function toCompletedForm(text: string): string {
  return text
    .replace(/한다\./g, "하였다.")
    .replace(/합니다\./g, "하였습니다.")
    .replace(/한다$/g, "하였다.")
    .replace(/합니다$/g, "하였습니다.")
    .replace(/설치한다/g, "설치하였다")
    .replace(/조치한다/g, "조치하였다")
    .replace(/차단한다/g, "차단하였다")
    .replace(/통제한다/g, "통제하였다")
    .replace(/보고한다/g, "보고하였다")
    .replace(/점검한다/g, "점검하였다")
    .replace(/진행한다/g, "진행하였다")
    .replace(/확인한다/g, "확인하였다")
    .replace(/실시한다/g, "실시하였다");
}

function fallbackNormalized(text: string, caseId: string | null): NormalizedInput {
  return {
    case_id: caseId,
    accident_type: text.includes("감전") ? "감전" : "기타",
    work_type: "점검",
    hazard_major_category: "전기 위험",
    hazard_middle_category: text || "현장 위험요인",
    environment_factors: [],
    human_factors: ["전원 차단 전 점검", "검전 미실시"],
    equipment: "전기 배선함",
    confidence: 0.55,
    ai_recommendations: {
      accident_type: [text.includes("감전") ? "감전" : "기타"],
      work_type: ["점검"],
      hazard: ["전기 위험"],
      environment_factors: [],
      human_factors: ["검전 미실시"],
      equipment: ["전기 배선함"],
      hazard_raw_matched: "",
      reason: "AI 분석이 지연되어 시연용 기본값을 사용했습니다.",
    },
    secondary_hazards: [],
    missing_info_questions: [],
    is_ready_for_recommendation: true,
    recommendation_context: {
      accident_type: text.includes("감전") ? "감전" : "기타",
      work_type: "점검",
      primary_hazard: "전기 위험",
      hazard_major_category: "전기 위험",
      hazard_middle_category: text,
      secondary_hazards: [],
      environment_factors: [],
      human_factors: ["전원 차단 전 점검", "검전 미실시"],
      equipment: "전기 배선함",
      confidence: 0.55,
    },
    image_edit_targets: [],
  };
}

function fallbackAnalyze(normalized: NormalizedInput, caseId: string | null): AnalyzeResponse {
  const item: PreventionItem = {
    prevention_id: "DEMO_PRV_001",
    major_category: "전기 위험",
    middle_category: "감전",
    content: "전기 담당자에게 즉시 보고하고, 전원 차단 및 검전 후 손상된 전선 피복을 절연 조치한다. 조치 전까지 해당 구역 접근을 통제한다.",
    expected_action_result: { effect_summary: "감전 위험이 줄고 무단 접근을 방지한다." },
    priority: 1,
    recommended_reason: "감전 위험은 전원 차단, 검전, 절연조치, 접근통제가 우선입니다.",
  };
  return {
    meta: { case_id: caseId ?? "DEMO_LOCAL", timestamp: new Date().toISOString(), status: "pending_review" },
    input_summary: { accident_type: normalized.accident_type, work_type: normalized.work_type, hazard: normalized.hazard_middle_category },
    prevention_list: [item],
    similar_cases: [],
    risk_score: { level: "medium", score: 68, reasons: ["전원 차단 전 점검과 검전 미실시가 확인되었습니다."] },
    predicted_severity: null,
    action_guide: {
      summary: "전기 담당자 보고, 전원 차단, 검전, 절연조치, 접근통제를 순서대로 진행하였다.",
      immediate_actions: ["손상된 전선 피복을 절연 조치하였다.", "접근 통제 표지를 설치하였다."],
      follow_up_actions: ["조치 완료 후 실제 현장 사진으로 확인하였다."],
      expected_result_example: "노출된 전선이 절연되고 접근통제 표지가 설치됩니다.",
    },
    analysis_reason: "AI 분석이 지연되어 시연용 기본 제안을 표시했습니다.",
  };
}

function fallbackImage(caseId: string | null): GenerateActionImageResponse {
  return {
    case_id: caseId,
    image_purpose: "action_after_example",
    is_actual_evidence: false,
    images: [],
    safety_notice: "이 이미지는 조치 후 예시이며 실제 현장 증빙이 아닙니다.",
    limitations: ["현재 시연버전에서는 실제 이미지 생성을 수행하지 않았거나 생성에 실패했습니다.", "실제 조치 완료 여부는 현장 확인 또는 실제 사진으로 검증해야 합니다."],
  };
}

export default function InputFlow() {
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const completionCameraRef = useRef<HTMLInputElement>(null);
  const completionGalleryRef = useRef<HTMLInputElement>(null);
  const speechRecognitionRef = useRef<BrowserSpeechRecognition | null>(null);

  const [step, setStep] = useState<Step>("photo");
  const [caseId, setCaseId] = useState<string | null>(null);
  const [sourceImage, setSourceImage] = useState<SourceImage | null>(null);
  const [completionSourceImage, setCompletionSourceImage] = useState<SourceImage | null>(null);
  const [occurredAt, setOccurredAt] = useState(nowInputValue());
  const [occurredLocation, setOccurredLocation] = useState("본부동 전기실");
  const [situationText, setSituationText] = useState("");
  const [normalized, setNormalized] = useState<NormalizedInput | null>(null);
  const [questions, setQuestions] = useState<MissingInfoQuestion[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [missingInfoAnswers, setMissingInfoAnswers] = useState<string[]>([]);
  const [questionDraft, setQuestionDraft] = useState("");
  const [selectedAccidentType, setSelectedAccidentType] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [preventionText, setPreventionText] = useState("");
  const [preventionCardVisible, setPreventionCardVisible] = useState(true);
  const [actionText, setActionText] = useState("");
  const [actionCardVisible, setActionCardVisible] = useState(true);
  const [imageResult, setImageResult] = useState<GenerateActionImageResponse | null>(null);
  const [actionImageStatus, setActionImageStatus] = useState<ActionImageStatus>("idle");
  const [loading, setLoading] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fileMode, setFileMode] = useState<PickMode>("gallery");
  const [completionFileMode, setCompletionFileMode] = useState<PickMode>("gallery");
  const [isListening, setIsListening] = useState(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const createdAt = useMemo(() => new Date().toLocaleString("ko-KR"), [step === "preview"]);

  const aiType = closestAccidentType(normalized?.accident_type);
  const preventionSuggestion = analyzeResult?.prevention_list.map((item) => item.content).join("\n") ?? "";
  const preventionReason = analyzeResult?.prevention_list[0]?.recommended_reason || analyzeResult?.analysis_reason || "AI 추천 이유가 제공되지 않았습니다.";

  const rawActionSuggestion = analyzeResult?.action_guide
    ? [analyzeResult.action_guide.summary, ...analyzeResult.action_guide.immediate_actions, ...analyzeResult.action_guide.follow_up_actions].join("\n")
    : analyzeResult?.prevention_list[0]?.content ?? preventionSuggestion;
  const actionSuggestion = toCompletedForm(rawActionSuggestion);

  const actionImageSrc = imageResult?.images?.[0]?.base64_data
    ? `data:${imageResult.images[0].mime_type};base64,${imageResult.images[0].base64_data}`
    : (imageResult?.images?.[0]?.url ?? null);

  const appendSpeechText = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSituationText((current) => {
      const existing = current.trim();
      return existing ? `${existing}\n${trimmed}` : trimmed;
    });
  };

  const startSpeechInput = () => {
    const SpeechRecognitionConstructor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionConstructor) {
      setNotice("이 브라우저에서는 음성 입력을 지원하지 않습니다. 텍스트로 입력해주세요.");
      return;
    }

    try {
      speechRecognitionRef.current?.stop();
      const recognition = new SpeechRecognitionConstructor();
      speechRecognitionRef.current = recognition;
      recognition.lang = "ko-KR";
      recognition.interimResults = true;
      recognition.continuous = false;

      let finalTranscript = "";
      recognition.onresult = (event) => {
        let interimTranscript = "";
        for (let index = 0; index < event.results.length; index += 1) {
          const result = event.results[index];
          const transcript = result[0]?.transcript ?? "";
          if (result.isFinal) finalTranscript += transcript;
          else interimTranscript += transcript;
        }
        if (interimTranscript.trim()) {
          setNotice(`듣는 중: ${interimTranscript.trim()}`);
        }
      };
      recognition.onerror = () => {
        setIsListening(false);
        setNotice("음성 인식에 실패했습니다. 텍스트로 입력해주세요.");
      };
      recognition.onend = () => {
        setIsListening(false);
        appendSpeechText(finalTranscript);
        speechRecognitionRef.current = null;
      };
      setNotice(null);
      setIsListening(true);
      recognition.start();
    } catch {
      setIsListening(false);
      setNotice("음성 인식에 실패했습니다. 텍스트로 입력해주세요.");
    }
  };

  const pickSourceFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      setSourceImage(await fileToSourceImage(file));
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "사진을 읽지 못했습니다.");
    }
  };

  const pickCompletionFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      setCompletionSourceImage(await fileToSourceImage(file));
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "사진을 읽지 못했습니다.");
    }
  };

  const startPhotoPick = (mode: PickMode) => {
    setFileMode(mode);
    if (mode === "camera") cameraInputRef.current?.click();
    else galleryInputRef.current?.click();
  };

  const startCompletionPhotoPick = (mode: PickMode) => {
    setCompletionFileMode(mode);
    if (mode === "camera") completionCameraRef.current?.click();
    else completionGalleryRef.current?.click();
  };

  const fillDemo = () => {
    setOccurredLocation("본부동 전기실");
    setSituationText(demoText);
    setSelectedAccidentType("감전");
  };

  const runStartAndNormalize = async () => {
    if (!situationText.trim()) {
      setNotice("식별된 위험 요인을 입력해주세요.");
      return;
    }
    setLoading("서버에 연결 중입니다... (첫 접속 시 최대 1분 소요)");
    setNotice(null);
    try {
      await pingBackend();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "서버에 연결할 수 없습니다.");
      setLoading(null);
      return;
    }
    setLoading("AI가 사진과 설명을 정리하고 있어요.");
    let nextCaseId = caseId;
    try {
      if (!nextCaseId) {
        const started = await startCase({
          submitted_by: "demo_user",
          occurred_at: occurredAt,
          occurred_location: occurredLocation,
          selected_accident_type: selectedAccidentType || null,
          situation_text: situationText,
          photo_metadata: sourceImage ? [{ ...sourceImage, base64_data: undefined, preview_url: undefined }] : [],
        });
        nextCaseId = started.case_id;
        setCaseId(nextCaseId);
      }
      const result = await normalizeIncident({
        case_id: nextCaseId,
        situation_text: situationText,
        occurred_at: occurredAt,
        occurred_location: occurredLocation,
        selected_accident_type: selectedAccidentType || null,
        images: sourceImage ? [{ ...sourceImage, preview_url: undefined }] : [],
        missing_info_answers: [],
        fields: {
          accident_type_raw: selectedAccidentType || null,
          work_type_raw: null,
          hazard_raw: [],
          environment_factor_raw: [],
          human_factor_raw: [],
          equipment_raw: null,
        },
      });
      setNormalized(result);
      setQuestions(result.missing_info_questions ?? []);
      setMissingInfoAnswers(new Array(result.missing_info_questions?.length ?? 0).fill(""));
      setSelectedAccidentType(closestAccidentType(result.accident_type) || selectedAccidentType);
      setStep((result.missing_info_questions?.length ?? 0) > 0 ? "questions" : "type");
    } catch (error) {
      const fallback = fallbackNormalized(situationText, nextCaseId);
      setNormalized(fallback);
      setQuestions([]);
      setSelectedAccidentType(closestAccidentType(fallback.accident_type));
      setNotice(error instanceof Error ? `AI 분석이 지연되고 있어 수동 입력으로 계속 진행할 수 있습니다. (${error.message})` : "AI 분석이 지연되고 있어 수동 입력으로 계속 진행할 수 있습니다.");
      setStep("type");
    } finally {
      setLoading(null);
    }
  };

  const saveQuestionAnswer = async (answer: string) => {
    const next = [...missingInfoAnswers];
    next[questionIndex] = answer;
    setMissingInfoAnswers(next);
    setQuestionDraft("");
    if (questionIndex + 1 < questions.length) {
      setQuestionIndex((current) => current + 1);
      return;
    }
    await rerunNormalize(next);
    setStep("type");
  };

  const rerunNormalize = async (answers: string[]) => {
    if (!caseId || !normalized) return;
    try {
      setLoading("답변을 반영해 다시 정리하고 있어요.");
      const result = await normalizeIncident({
        case_id: caseId,
        situation_text: `${situationText}\n\n[추가 답변]\n${questions.map((q, i) => `${q.question}: ${answers[i] || "건너뜀"}`).join("\n")}`,
        occurred_at: occurredAt,
        occurred_location: occurredLocation,
        images: sourceImage ? [{ ...sourceImage, preview_url: undefined }] : [],
        missing_info_answers: answers,
        fields: {
          accident_type_raw: selectedAccidentType || null,
          work_type_raw: null,
          hazard_raw: [],
          environment_factor_raw: [],
          human_factor_raw: [],
          equipment_raw: null,
        },
      });
      setNormalized(result);
      setSelectedAccidentType(closestAccidentType(result.accident_type) || selectedAccidentType);
    } catch {
      setNotice("재분석에 실패했지만 기존 AI 결과로 계속 진행할 수 있습니다.");
    } finally {
      setLoading(null);
    }
  };

  const runAnalyze = async () => {
    const base = normalized ?? fallbackNormalized(situationText, caseId);
    const nextNormalized = { ...base, case_id: caseId, accident_type: selectedAccidentType || base.accident_type };
    setNormalized(nextNormalized);
    setLoading("AI 분석 중...");
    setNotice(null);

    let resultLocal: AnalyzeResponse = fallbackAnalyze(nextNormalized, caseId);

    try {
      resultLocal = await analyzeIncident({
        case_id: caseId,
        raw_input: situationText,
        normalized: nextNormalized,
        recommendation_context: nextNormalized.recommendation_context ?? {},
        meta: {
          submitted_by: "demo_user",
          occurred_at: occurredAt,
          occurred_location: occurredLocation,
        },
      });
      setAnalyzeResult(resultLocal);
    } catch (error) {
      setAnalyzeResult(resultLocal);
      setNotice(error instanceof Error ? `AI 분석이 지연되고 있어 수동 입력으로 계속 진행할 수 있습니다. (${error.message})` : "AI 분석이 지연되고 있어 수동 입력으로 계속 진행할 수 있습니다.");
    } finally {
      setLoading(null);
    }

    // 백그라운드 이미지 생성 (analyze 완료 직후 즉시 실행, 결과를 기다리지 않음)
    setActionImageStatus("loading");
    const actionContent = resultLocal.prevention_list[0]?.content ?? preventionText ?? "확정한 안전 조치를 적용한다.";
    generateActionImage({
      case_id: caseId,
      source_image: sourceImage ? { ...sourceImage, preview_url: undefined } : null,
      selected_action: { content: actionContent },
      recommendation_context: nextNormalized.recommendation_context ?? {},
      image_edit_target: nextNormalized.image_edit_targets?.[0] ?? {
        description: "사용자가 입력한 위험 요인을 예방 조치한 후의 상태",
        action_after_text: actionContent,
        metadata: { source: "frontend_prevention_image_fallback" },
      },
    }).then((result) => {
      setImageResult(result);
      setActionImageStatus("success");
    }).catch(() => {
      setActionImageStatus("error");
    });

    setStep("prevention");
  };

  const applyText = (kind: "prevention" | "action", mode: "accept" | "append" | "replace" | "reject") => {
    const suggestion = kind === "prevention" ? preventionSuggestion : actionSuggestion;
    const setter = kind === "prevention" ? setPreventionText : setActionText;
    if (mode === "reject") {
      if (kind === "prevention") setPreventionCardVisible(false);
      else setActionCardVisible(false);
      return;
    }
    if (mode === "accept" || mode === "replace") setter(suggestion);
    if (mode === "append") setter((current) => [current, suggestion].filter(Boolean).join("\n"));
  };

  return (
    <main className="min-h-screen bg-[#F3F4F8] px-3 py-4 text-[#1D1D24]">
      <input ref={cameraInputRef} className="hidden" type="file" accept="image/*" capture="environment" onChange={pickSourceFile} />
      <input ref={galleryInputRef} className="hidden" type="file" accept="image/*" onChange={pickSourceFile} />
      <input ref={completionCameraRef} className="hidden" type="file" accept="image/*" capture="environment" onChange={pickCompletionFile} />
      <input ref={completionGalleryRef} className="hidden" type="file" accept="image/*" onChange={pickCompletionFile} />

      <div className="mx-auto max-w-[360px] rounded-[28px] border border-[#D9DAE3] bg-white shadow-sm">
        <TopBar title="사고 등록" onBack={() => setStep(previousStep(step))} />
        <StepDots step={step} />
        <section className="px-4 pb-4">
          {notice && <Notice>{notice}</Notice>}
          {loading && <div className="mb-3 rounded-xl border border-[#AFA9EC] bg-[#EEEDFE] px-3 py-2 text-[13px] font-semibold text-[#3C3489]">{loading}</div>}

          {step === "photo" && (
            <Screen title="사진을 첨부하고 상황을 설명해주세요">
              <button className="mb-3 text-[12px] font-bold text-[#534AB7]" onClick={fillDemo}>데모 입력 채우기</button>
              <div className="mb-3 grid grid-cols-3 gap-2">
                <MiniButton onClick={() => startPhotoPick("camera")}>카메라</MiniButton>
                <MiniButton onClick={() => startPhotoPick("gallery")}>갤러리</MiniButton>
                <MiniButton onClick={() => setSourceImage(null)}>건너뛰기</MiniButton>
              </div>
              <div className="mb-3 rounded-2xl border border-dashed border-[#C8C8D3] bg-[#F9F9FC] p-3">
                {sourceImage?.preview_url ? (
                  <div>
                    <img src={sourceImage.preview_url} alt="선택한 현장 사진" className="h-40 w-full rounded-xl object-cover" />
                    <div className="mt-2 flex gap-2">
                      <MiniButton onClick={() => startPhotoPick(fileMode)}>재촬영</MiniButton>
                      <MiniButton onClick={() => startPhotoPick("gallery")}>추가</MiniButton>
                    </div>
                    <p className="mt-2 text-[11px] text-[#777783]">원본 사진은 조치 가이드 생성 참고용으로만 사용됩니다.</p>
                  </div>
                ) : (
                  <p className="py-8 text-center text-[13px] text-[#777783]">사진은 선택 사항입니다.</p>
                )}
              </div>
              <Input label="식별 일시" value={occurredAt} onChange={setOccurredAt} type="datetime-local" />
              <Input label="식별 장소" value={occurredLocation} onChange={setOccurredLocation} />
              <div className="mb-3 grid grid-cols-2 gap-2">
                <MiniButton onClick={startSpeechInput}>{isListening ? "듣는 중..." : "음성으로 입력"}</MiniButton>
                <MiniButton onClick={() => setSituationText("")}>입력 지우기</MiniButton>
              </div>
              <Textarea label="식별된 위험 요인" value={situationText} onChange={setSituationText} placeholder="전기 배선함 인근 전선 피복이 벗겨져 있어 감전 위험이 있었습니다." />
              <BottomButton onClick={runStartAndNormalize}>다음</BottomButton>
            </Screen>
          )}

          {step === "questions" && (
            <Screen title="몇 가지 더 여쭤볼게요">
              <Progress current={questionIndex + 1} total={Math.max(questions.length, 1)} />
              <div className="mb-3 rounded-2xl border border-[#AFA9EC] bg-[#EEEDFE] p-3">
                <p className="mb-1 text-[12px] font-bold text-[#3C3489]">AI 질문 {questionIndex + 1} / {questions.length}</p>
                <p className="text-[14px] font-semibold leading-6">{questions[questionIndex]?.question}</p>
                <p className="mt-1 text-[12px] leading-5 text-[#5B587A]">{questions[questionIndex]?.reason}</p>
              </div>
              <div className="mb-3 grid gap-2">
                {["예", "아니요", "잘 모르겠습니다"].map((answer) => (
                  <button key={answer} className="rounded-xl border border-[#D7D7E1] px-3 py-3 text-left text-[13px] font-semibold" onClick={() => saveQuestionAnswer(answer)}>{answer}</button>
                ))}
              </div>
              <input className="mb-2 w-full rounded-xl border border-[#D7D7E1] px-3 py-3 text-[13px]" value={questionDraft} onChange={(event) => setQuestionDraft(event.target.value)} placeholder="직접 입력" />
              <MiniButton onClick={() => saveQuestionAnswer(questionDraft || "건너뜀")}>다음 질문</MiniButton>
              <button className="mt-3 w-full text-[12px] font-bold text-[#777783]" onClick={() => setStep("type")}>나머지 질문 건너뛰기</button>
            </Screen>
          )}

          {step === "type" && (
            <Screen title="이 사고의 유형을 선택해주세요">
              <div className="grid gap-2">
                {accidentTypes.map((type) => (
                  <button key={type} className={`rounded-xl border px-3 py-3 text-left text-[13px] font-bold ${selectedAccidentType === type ? "border-[#534AB7] bg-[#EEEDFE] text-[#3C3489]" : "border-[#D7D7E1]"}`} onClick={() => setSelectedAccidentType(type)}>
                    {type}
                    {aiType === type && <span className="ml-2 rounded-full bg-[#CECBF6] px-2 py-1 text-[10px] text-[#3C3489]">AI 추천</span>}
                  </button>
                ))}
              </div>
              <BottomButton onClick={runAnalyze}>다음</BottomButton>
            </Screen>
          )}

          {step === "prevention" && (
            <EditorScreen
              title="예방 대책을 작성해주세요"
              value={preventionText}
              onChange={setPreventionText}
              suggestion={preventionSuggestion}
              reason={preventionReason}
              visible={preventionCardVisible}
              onApply={(mode) => applyText("prevention", mode)}
              onNext={() => setStep("action")}
              extra={
                <ActionImageCard
                  status={actionImageStatus}
                  imageSrc={actionImageSrc}
                  notice={imageResult?.safety_notice}
                  limitations={imageResult?.limitations}
                />
              }
            />
          )}

          {step === "action" && (
            <EditorScreen
              title="조치 결과를 작성해주세요"
              value={actionText}
              onChange={setActionText}
              suggestion={actionSuggestion}
              reason={analyzeResult?.action_guide?.expected_result_example ?? "조치 완료 후 실제 현장 확인이 필요합니다."}
              visible={actionCardVisible}
              onApply={(mode) => applyText("action", mode)}
              onNext={() => setStep("completionPhoto")}
            />
          )}

          {step === "completionPhoto" && (
            <Screen title="조치 완료 사진을 첨부해주세요">
              <div className="mb-3 grid grid-cols-3 gap-2">
                <MiniButton onClick={() => startCompletionPhotoPick("camera")}>카메라</MiniButton>
                <MiniButton onClick={() => startCompletionPhotoPick("gallery")}>갤러리</MiniButton>
                <MiniButton onClick={() => { setCompletionSourceImage(null); setStep("preview"); }}>나중에 첨부할게요</MiniButton>
              </div>
              <div className="mb-3 rounded-2xl border border-dashed border-[#C8C8D3] bg-[#F9F9FC] p-3">
                {completionSourceImage?.preview_url ? (
                  <div>
                    <img src={completionSourceImage.preview_url} alt="조치 완료 사진" className="h-40 w-full rounded-xl object-cover" />
                    <div className="mt-2 flex gap-2">
                      <MiniButton onClick={() => startCompletionPhotoPick(completionFileMode)}>재촬영</MiniButton>
                      <MiniButton onClick={() => startCompletionPhotoPick("gallery")}>다시 선택</MiniButton>
                    </div>
                  </div>
                ) : (
                  <p className="py-8 text-center text-[13px] text-[#777783]">조치 완료 사진을 첨부해주세요.</p>
                )}
              </div>
              {completionSourceImage && (
                <BottomButton onClick={() => setStep("preview")}>다음</BottomButton>
              )}
            </Screen>
          )}

          {step === "preview" && (
            <Screen title="보고서 미리보기">
              <Report label="소속 / 계급 / 성명" value="1중대 병장 홍길동" />
              <Report label="식별 일시" value={occurredAt.replace("T", " ")} />
              <Report label="식별 장소" value={occurredLocation} />
              <Report label="글 등록 시간" value={createdAt} />
              <Report label="사고 유형" value={selectedAccidentType || "미선택"} />
              <Report label="식별된 위험 요인" value={situationText} />
              <Report label="예방 대책" value={preventionText || "미입력"} />
              <Report label="조치 결과" value={actionText || "미입력"} />
              <div className="mb-2 rounded-xl border border-[#E4E4EA] bg-white p-3">
                <p className="text-[11px] font-bold text-[#777783]">관련 사진</p>
                {sourceImage?.preview_url && (
                  <div className="mt-2">
                    <p className="mb-1 text-[11px] text-[#777783]">식별 사진</p>
                    <img className="h-28 w-full rounded-xl object-cover" src={sourceImage.preview_url} alt="식별 사진" />
                  </div>
                )}
                {completionSourceImage?.preview_url ? (
                  <div className="mt-2">
                    <p className="mb-1 text-[11px] text-[#777783]">조치 완료 사진</p>
                    <img className="h-28 w-full rounded-xl object-cover" src={completionSourceImage.preview_url} alt="조치 완료 사진" />
                  </div>
                ) : (
                  <p className="mt-1 text-[13px] text-[#777783]">조치 완료 사진: 없음</p>
                )}
              </div>
              <div className="mb-2 rounded-xl border border-[#E4E4EA] bg-white p-3">
                <p className="text-[11px] font-bold text-[#777783]">처리 상태</p>
                {completionSourceImage ? (
                  <p className="mt-1 text-[13px] font-bold text-[#1D9E75]">조치 완료</p>
                ) : (
                  <p className="mt-1 text-[13px] font-bold text-[#D97706]">사진 미첨부 (조치 대기)</p>
                )}
              </div>
              <BottomButton onClick={() => setStep("done")}>등록하기</BottomButton>
            </Screen>
          )}

          {step === "done" && (
            <Screen title="등록이 완료됐어요">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#E1F5EE] text-3xl font-bold text-[#1D9E75]">✓</div>
              <p className="text-center text-[14px] font-semibold">사고 보고서가 등록됐습니다.</p>
              {completionSourceImage ? (
                <p className="mt-3 rounded-xl bg-[#E1F5EE] px-3 py-3 text-center text-[13px] font-bold text-[#1D9E75]">처리 상태: 조치 완료</p>
              ) : (
                <p className="mt-3 rounded-xl bg-[#FEF3C7] px-3 py-3 text-center text-[13px] font-bold text-[#D97706]">처리 상태: 사진 미첨부 (조치 대기)</p>
              )}
              <BottomButton onClick={() => undefined}>내 사고 관리로 이동</BottomButton>
            </Screen>
          )}
        </section>
      </div>
    </main>
  );
}

function previousStep(step: Step): Step {
  const index = steps.findIndex(([key]) => key === step);
  return steps[Math.max(index - 1, 0)]?.[0] ?? "photo";
}

function TopBar({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <div className="grid grid-cols-[32px_1fr_32px] items-center px-4 py-3">
      <button className="text-xl font-bold text-[#534AB7]" onClick={onBack}>‹</button>
      <h1 className="text-center text-[15px] font-bold">{title}</h1>
      <button className="text-lg font-bold text-[#777783]">×</button>
    </div>
  );
}

function StepDots({ step }: { step: Step }) {
  const current = steps.findIndex(([key]) => key === step);
  return (
    <div className="flex items-center justify-center gap-1 px-4 pb-3">
      {steps.map(([key], index) => (
        <span key={key} className={`h-2 rounded-full ${index < current ? "w-2 bg-[#1D9E75]" : index === current ? "w-7 bg-[#534AB7]" : "w-2 bg-[#D7D7E1]"}`} />
      ))}
    </div>
  );
}

function Screen({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-[560px]">
      <h2 className="mb-3 text-[18px] font-extrabold tracking-normal">{title}</h2>
      {children}
    </div>
  );
}

function Input({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-[12px] font-bold text-[#555560]">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-[#D7D7E1] px-3 py-3 text-[13px] outline-none focus:border-[#534AB7]" />
    </label>
  );
}

function Textarea({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-[12px] font-bold text-[#555560]">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} rows={7} className="w-full resize-none rounded-xl border border-[#D7D7E1] px-3 py-3 text-[13px] leading-6 outline-none focus:border-[#534AB7]" />
    </label>
  );
}

function MiniButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button className="rounded-xl border border-[#D7D7E1] bg-white px-3 py-3 text-[12px] font-bold text-[#3D3D46]" onClick={onClick}>{children}</button>;
}

function BottomButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button className="mt-4 w-full rounded-2xl bg-[#534AB7] px-4 py-4 text-[14px] font-extrabold text-white shadow-sm" onClick={onClick}>{children}</button>;
}

function Notice({ children }: { children: ReactNode }) {
  return <div className="mb-3 rounded-xl border border-[#EF9F27] bg-[#FAEEDA] px-3 py-2 text-[12px] font-semibold text-[#855B18]">{children}</div>;
}

function Progress({ current, total }: { current: number; total: number }) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex justify-between text-[11px] font-bold text-[#777783]"><span>진행률</span><span>{current} / {total}</span></div>
      <div className="h-2 rounded-full bg-[#E8E8EF]"><div className="h-2 rounded-full bg-[#534AB7]" style={{ width: `${Math.min(100, (current / total) * 100)}%` }} /></div>
    </div>
  );
}

function ActionImageCard({
  status,
  imageSrc,
  notice,
  limitations,
}: {
  status: ActionImageStatus;
  imageSrc: string | null;
  notice?: string | null;
  limitations?: string[];
}) {
  const showImage = status === "success" && imageSrc !== null;
  const showFallback = status === "error" || status === "idle" || (status === "success" && !imageSrc);

  return (
    <div className="mt-3 rounded-2xl border border-[#AFA9EC] bg-[#EEEDFE] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded-full bg-[#CECBF6] px-2 py-1 text-[11px] font-bold text-[#3C3489]">AI 예방 조치 가이드 이미지</span>
        <span className="text-[11px] font-bold text-[#EF9F27]">증빙 아님</span>
      </div>
      {status === "loading" && (
        <div className="flex items-center justify-center py-6 text-[13px] font-semibold text-[#534AB7]">
          <span className="mr-2 inline-block animate-spin">⟳</span>AI 이미지 생성 중...
        </div>
      )}
      {showImage && (
        <>
          <img className="h-44 w-full rounded-xl object-cover" src={imageSrc} alt="AI 생성 조치 가이드 예시" />
          <p className="mt-2 text-[12px] leading-5 text-[#3C3489]">이 이미지는 예방 조치 가이드용 예시이며 실제 현장 증빙이 아닙니다.</p>
          {notice && <p className="mt-1 text-[12px] leading-5 text-[#5B587A]">{notice}</p>}
          {limitations && limitations.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-[12px] leading-5 text-[#5B587A]">
              {limitations.map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
        </>
      )}
      {showFallback && (
        <div className="rounded-xl bg-white px-3 py-4 text-center text-[13px] font-semibold text-[#777783]">
          현재 시연버전에서는 이미지 안내로 대체됩니다.
        </div>
      )}
    </div>
  );
}

function EditorScreen({
  title,
  value,
  onChange,
  suggestion,
  reason,
  visible,
  onApply,
  onNext,
  extra,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  suggestion: string;
  reason: string;
  visible: boolean;
  onApply: (mode: "accept" | "append" | "replace" | "reject") => void;
  onNext: () => void;
  extra?: ReactNode;
}) {
  const hasText = value.trim().length > 0;
  return (
    <Screen title={title}>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={8} className="w-full resize-none rounded-xl border border-[#D7D7E1] px-3 py-3 text-[13px] leading-6 outline-none focus:border-[#534AB7]" />
      {visible && suggestion && (
        <div className="mt-3 rounded-2xl border border-[#AFA9EC] bg-[#EEEDFE] p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] font-extrabold text-[#3C3489]">AI 제안</span>
            <span className="rounded-full bg-[#CECBF6] px-2 py-1 text-[10px] font-bold text-[#3C3489]">추천</span>
          </div>
          <p className="whitespace-pre-wrap text-[13px] leading-6">{suggestion}</p>
          <p className="mt-2 rounded-xl bg-white px-3 py-2 text-[12px] leading-5 text-[#555560]">추천 이유: {reason}</p>
          <div className="mt-3 grid gap-2">
            {!hasText ? (
              <>
                <MiniButton onClick={() => onApply("accept")}>전체 수락</MiniButton>
                <MiniButton onClick={() => onApply("reject")}>거부</MiniButton>
              </>
            ) : (
              <>
                <MiniButton onClick={() => onApply("append")}>기존 내용에 추가</MiniButton>
                <MiniButton onClick={() => onApply("replace")}>전체 교체</MiniButton>
                <MiniButton onClick={() => onApply("reject")}>거부</MiniButton>
              </>
            )}
          </div>
        </div>
      )}
      {extra}
      <BottomButton onClick={onNext}>다음</BottomButton>
    </Screen>
  );
}

function Report({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2 rounded-xl border border-[#E4E4EA] bg-white p-3">
      <p className="text-[11px] font-bold text-[#777783]">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-[13px] leading-5">{value || "미입력"}</p>
    </div>
  );
}
