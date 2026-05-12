import { useState } from "react";
import { analyzeIncident, normalizeIncident } from "../api/client";
import AiFactorStatusPanel from "../components/AiFactorStatusPanel";
import { INCIDENT_SCENARIOS, type IncidentScenario, type ScenarioExpected } from "../dev/incidentScenarios";
import type { AnalyzeResponse, AnalyzeRequest, NormalizeRequest, NormalizedInput } from "../types/api";

type Verdict = "PASS" | "FAIL" | "SKIP";

interface CompareRow {
  field: string;
  expected: string;
  actual: string;
  verdict: Verdict;
}

interface RunAllEntry {
  id: string;
  name: string;
  rows: CompareRow[];
  passCount: number;
  failCount: number;
  skipCount: number;
  error: string | null;
}

const TAG_COLORS: Record<string, string> = {
  정보충분: "bg-emerald-100 text-emerald-800",
  정보부족: "bg-amber-100 text-amber-800",
  고위험: "bg-red-100 text-red-800",
  경미: "bg-sky-100 text-sky-800",
  차량: "bg-blue-100 text-blue-800",
  감전: "bg-purple-100 text-purple-800",
  추락: "bg-orange-100 text-orange-800",
  낙상: "bg-yellow-100 text-yellow-800",
  화재: "bg-rose-100 text-rose-800",
  폭발: "bg-red-200 text-red-900",
  질식: "bg-indigo-100 text-indigo-800",
  과부하: "bg-teal-100 text-teal-800",
};

const FILTER_TAGS = ["정보부족", "고위험", "경미", "차량", "감전", "추락", "낙상", "화재", "폭발", "질식", "과부하"];

const VERDICT_COLORS: Record<Verdict, string> = {
  PASS: "text-emerald-700 font-bold",
  FAIL: "text-red-700 font-bold",
  SKIP: "text-stone-400",
};

function buildNormalizeRequest(scenario: IncidentScenario): NormalizeRequest {
  return {
    situation_text: scenario.situation_text,
    fields: {
      accident_type_raw: scenario.fields?.accident_type_raw ?? null,
      work_type_raw: scenario.fields?.work_type_raw ?? null,
      hazard_raw: scenario.fields?.hazard_raw ?? [],
      environment_factor_raw: scenario.fields?.environment_factor_raw ?? [],
      human_factor_raw: scenario.fields?.human_factor_raw ?? [],
      equipment_raw: scenario.fields?.equipment_raw ?? null,
    },
  };
}

function buildAnalyzeRequest(scenario: IncidentScenario, normalized: NormalizedInput): AnalyzeRequest {
  return {
    raw_input: scenario.situation_text,
    normalized,
    meta: {
      submitted_by: "dev_test",
      occurred_at: scenario.occurred_at ?? null,
      occurred_location: scenario.occurred_location,
    },
  };
}

function friendlyError(err: unknown): string {
  if (err instanceof TypeError) return "백엔드 서버가 실행 중인지 확인하세요";
  if (err instanceof Error) {
    if (err.message.includes("fetch")) return "백엔드 서버가 실행 중인지 확인하세요";
    return err.message;
  }
  return "알 수 없는 오류";
}

function matchValue(expected: string | string[], actual: string): boolean {
  return Array.isArray(expected) ? expected.includes(actual) : actual === expected;
}

function displayExpected(expected: string | string[]): string {
  return Array.isArray(expected) ? expected.join(" / ") : expected;
}

function buildComparison(
  expected: ScenarioExpected | undefined,
  normalize: NormalizedInput | null,
  analyze: AnalyzeResponse | null,
): CompareRow[] {
  if (!expected) return [];

  const rows: CompareRow[] = [];

  function push(field: string, expectedStr: string, actualStr: string, pass: boolean): void {
    rows.push({ field, expected: expectedStr, actual: actualStr, verdict: pass ? "PASS" : "FAIL" });
  }

  function skip(field: string, expectedStr: string): void {
    rows.push({ field, expected: expectedStr, actual: "—", verdict: "SKIP" });
  }

  if (expected.accident_type !== undefined) {
    const actual = normalize?.accident_type ?? "";
    const expStr = displayExpected(expected.accident_type);
    actual ? push("accident_type", expStr, actual, matchValue(expected.accident_type, actual)) : skip("accident_type", expStr);
  }

  if (expected.work_type !== undefined) {
    const actual = normalize?.work_type ?? "";
    const expStr = displayExpected(expected.work_type);
    actual ? push("work_type", expStr, actual, matchValue(expected.work_type, actual)) : skip("work_type", expStr);
  }

  if (expected.hazard_middle_category !== undefined) {
    const actual = normalize?.hazard_middle_category ?? "";
    const expStr = displayExpected(expected.hazard_middle_category);
    actual ? push("hazard_middle_category", expStr, actual, matchValue(expected.hazard_middle_category, actual)) : skip("hazard_middle_category", expStr);
  }

  if ("equipment" in expected) {
    const expEq = expected.equipment === null ? "(없음)" : (expected.equipment ?? "(없음)");
    const actEq = normalize == null ? null : (normalize.equipment === null || normalize.equipment === undefined ? "(없음)" : normalize.equipment);
    actEq != null ? push("equipment", expEq, actEq, expEq === actEq) : skip("equipment", expEq);
  }

  if (expected.secondary_hazard_middle !== undefined && expected.secondary_hazard_middle.length > 0) {
    const actualMiddles = normalize?.secondary_hazards?.map((h) => h.middle) ?? [];
    if (normalize == null) {
      skip("secondary_hazards", expected.secondary_hazard_middle.join(", "));
    } else {
      const allFound = expected.secondary_hazard_middle.every((em) =>
        actualMiddles.some((am) => am === em || am.includes(em) || em.includes(am)),
      );
      push(
        "secondary_hazards",
        expected.secondary_hazard_middle.join(", "),
        actualMiddles.length > 0 ? actualMiddles.join(", ") : "(없음)",
        allFound,
      );
    }
  }

  if (expected.has_missing_info_questions !== undefined) {
    if (normalize == null) {
      skip("missing_info_questions", expected.has_missing_info_questions ? "있어야 함" : "없어야 함");
    } else {
      const hasMissing = (normalize.missing_info_questions?.length ?? 0) > 0;
      push(
        "missing_info_questions",
        expected.has_missing_info_questions ? "있어야 함" : "없어야 함",
        hasMissing ? `있음 (${normalize.missing_info_questions?.length ?? 0}개)` : "없음",
        hasMissing === expected.has_missing_info_questions,
      );
    }
  }

  if (expected.min_prevention_count !== undefined) {
    if (analyze == null) {
      skip("prevention_count", `최소 ${expected.min_prevention_count}개`);
    } else {
      const actual = analyze.prevention_list?.length ?? 0;
      push("prevention_count", `최소 ${expected.min_prevention_count}개`, `${actual}개`, actual >= expected.min_prevention_count);
    }
  }

  if (expected.expected_prevention_keywords !== undefined && expected.expected_prevention_keywords.length > 0) {
    if (analyze == null) {
      skip("prevention_keywords", expected.expected_prevention_keywords.join(", "));
    } else {
      const allContent = analyze.prevention_list?.map((p) => p.content).join(" ") ?? "";
      const missing = expected.expected_prevention_keywords.filter((kw) => !allContent.includes(kw));
      push(
        "prevention_keywords",
        expected.expected_prevention_keywords.join(", "),
        missing.length === 0 ? "모두 포함" : `미포함: ${missing.join(", ")}`,
        missing.length === 0,
      );
    }
  }

  if (expected.expected_action_guide_keywords !== undefined && expected.expected_action_guide_keywords.length > 0) {
    if (analyze == null) {
      skip("action_guide_keywords", expected.expected_action_guide_keywords.join(", "));
    } else {
      const guideText = [
        analyze.action_guide?.summary,
        ...(analyze.action_guide?.immediate_actions ?? []),
        ...(analyze.action_guide?.follow_up_actions ?? []),
      ]
        .filter(Boolean)
        .join(" ");
      const missing = expected.expected_action_guide_keywords.filter((kw) => !guideText.includes(kw));
      push(
        "action_guide_keywords",
        expected.expected_action_guide_keywords.join(", "),
        missing.length === 0 ? "모두 포함" : `미포함: ${missing.join(", ")}`,
        missing.length === 0,
      );
    }
  }

  return rows;
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    console.warn("Copy failed");
  }
}

function buildScenarioReport(
  scenario: IncidentScenario,
  normalize: NormalizedInput | null,
  analyze: AnalyzeResponse | null,
  compareRows: CompareRow[],
): string {
  const L: string[] = [];

  L.push("[Incident Scenario Lab Result]");
  L.push("");

  L.push("Scenario:");
  L.push(`- id: ${scenario.id}`);
  L.push(`- name: ${scenario.name}`);
  L.push(`- location: ${scenario.occurred_location}`);
  if (scenario.occurred_at) L.push(`- occurred_at: ${scenario.occurred_at}`);
  L.push("");

  L.push("Input:");
  L.push(scenario.situation_text);
  L.push("");

  if (compareRows.length > 0) {
    L.push("Expected vs Actual:");
    for (const row of compareRows) {
      L.push(`- ${row.field}: expected=${row.expected} / actual=${row.actual} / ${row.verdict}`);
    }
    const p = compareRows.filter((r) => r.verdict === "PASS").length;
    const f = compareRows.filter((r) => r.verdict === "FAIL").length;
    const s = compareRows.filter((r) => r.verdict === "SKIP").length;
    L.push(`  → PASS: ${p} / FAIL: ${f} / SKIP: ${s}`);
  } else if (scenario.expected) {
    L.push("Expected vs Actual:");
    L.push("  (normalize 미실행 — 비교 불가)");
  }
  L.push("");

  L.push("Normalize Summary:");
  if (normalize) {
    L.push(`- accident_type: ${normalize.accident_type}`);
    L.push(`- work_type: ${normalize.work_type}`);
    L.push(`- hazard_major_category: ${normalize.hazard_major_category}`);
    L.push(`- hazard_middle_category: ${normalize.hazard_middle_category}`);
    const sec = normalize.secondary_hazards?.map((h) => `${h.major}/${h.middle}`).join(", ") || "(없음)";
    L.push(`- secondary_hazards: ${sec}`);
    L.push(`- environment_factors: ${normalize.environment_factors.join(", ") || "(없음)"}`);
    L.push(`- human_factors: ${normalize.human_factors.join(", ") || "(없음)"}`);
    L.push(`- equipment: ${normalize.equipment ?? "(없음)"}`);
    L.push(`- confidence: ${Math.round(normalize.confidence * 100)}%`);
    const mqCount = normalize.missing_info_questions?.length ?? 0;
    L.push(`- missing_info_questions: ${mqCount > 0 ? `${mqCount}개` : "없음"}`);
    for (const q of normalize.missing_info_questions ?? []) {
      L.push(`  [${q.field}] ${q.question}`);
    }
  } else {
    L.push("  (미실행)");
  }
  L.push("");

  L.push("Analyze Summary:");
  if (analyze) {
    L.push(`- prevention_count: ${analyze.prevention_list.length}개`);
    L.push("- prevention_list:");
    analyze.prevention_list.forEach((item, i) => {
      L.push(`  ${i + 1}. [${item.prevention_id}] ${item.major_category}/${item.middle_category} - ${item.content}`);
      if (item.recommended_reason) L.push(`     reason: ${item.recommended_reason}`);
      const effectVal = Object.values(item.expected_action_result)[0];
      if (effectVal) L.push(`     expected_result: ${effectVal}`);
    });
    if (analyze.action_guide) {
      L.push("- action_guide:");
      L.push(`  summary: ${analyze.action_guide.summary}`);
      L.push("  immediate_actions:");
      analyze.action_guide.immediate_actions.forEach((a) => L.push(`    - ${a}`));
      L.push("  follow_up_actions:");
      analyze.action_guide.follow_up_actions.forEach((a) => L.push(`    - ${a}`));
      L.push(`  expected_result_example: ${analyze.action_guide.expected_result_example}`);
    }
    L.push("- risk_score:");
    L.push(`  level: ${analyze.risk_score.level}`);
    L.push(`  score: ${analyze.risk_score.score}`);
    if ((analyze.risk_score.reasons?.length ?? 0) > 0) {
      L.push("  reasons:");
      analyze.risk_score.reasons?.forEach((r) => L.push(`    - ${r}`));
    }
    L.push("  note: 임시 위험도 / 공식 예상 피해등급 적용 전 값");
    if (analyze.predicted_severity) {
      const sv = analyze.predicted_severity;
      L.push("- predicted_severity:");
      L.push(`  grade: ${sv.grade ?? "null"}`);
      L.push(`  label: ${sv.label}`);
      L.push(`  confidence: ${sv.confidence}`);
      if (sv.prediction_reason.length > 0) {
        L.push("  reasons:");
        sv.prediction_reason.forEach((r) => L.push(`    - ${r}`));
      }
      if (sv.why_not_higher) L.push(`  why_not_higher: ${sv.why_not_higher}`);
      if (sv.why_not_lower) L.push(`  why_not_lower: ${sv.why_not_lower}`);
      if (sv.missing_information.length > 0) L.push(`  missing_information: ${sv.missing_information.join(", ")}`);
      if (sv.validation_warnings.length > 0) L.push(`  validation_warnings: ${sv.validation_warnings.join("; ")}`);
    }
    L.push(`- similar_cases_count: ${analyze.similar_cases.length}`);
    if (analyze.analysis_reason) L.push(`- analysis_reason: ${analyze.analysis_reason}`);
  } else {
    L.push("  (미실행)");
  }
  L.push("");

  L.push("Notes:");
  L.push("-");

  return L.join("\n");
}

function buildRunAllSummary(entries: RunAllEntry[]): string {
  const L: string[] = [];

  L.push("[Incident Scenario Lab Run All Summary]");
  L.push("");

  const totalPass = entries.reduce((a, e) => a + e.passCount, 0);
  const totalFail = entries.reduce((a, e) => a + e.failCount, 0);
  const totalSkip = entries.reduce((a, e) => a + e.skipCount, 0);
  const totalError = entries.filter((e) => e.error).length;

  L.push("Total:");
  L.push(`- scenarios: ${entries.length}`);
  L.push(`- pass: ${totalPass}`);
  L.push(`- fail: ${totalFail}`);
  L.push(`- skip: ${totalSkip}`);
  L.push(`- error: ${totalError}`);
  L.push("");

  L.push("Results:");
  entries.forEach((entry, i) => {
    L.push(`${i + 1}. ${entry.id} ${entry.name}`);
    L.push(`   - PASS: ${entry.passCount}`);
    L.push(`   - FAIL: ${entry.failCount}`);
    if (entry.error) L.push(`   - ERROR: ${entry.error}`);
    const failures = entry.rows.filter((r) => r.verdict === "FAIL");
    if (failures.length > 0) {
      L.push("   - key failures:");
      failures.forEach((f) => L.push(`     ${f.field}: expected=${f.expected} / actual=${f.actual}`));
    }
    L.push("");
  });

  L.push("Notes:");
  L.push("-");

  return L.join("\n");
}

export default function DevIncidentScenarios() {
  const [selectedId, setSelectedId] = useState<string>(INCIDENT_SCENARIOS[0]?.id ?? "");
  const [activeTagFilter, setActiveTagFilter] = useState<string | null>(null);
  const [normalizeResult, setNormalizeResult] = useState<NormalizedInput | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [normalizeLoading, setNormalizeLoading] = useState(false);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [normalizeError, setNormalizeError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [runAllEntries, setRunAllEntries] = useState<RunAllEntry[] | null>(null);
  const [runAllLoading, setRunAllLoading] = useState(false);
  const [runAllProgress, setRunAllProgress] = useState(0);
  const [copyScenarioMsg, setCopyScenarioMsg] = useState<string | null>(null);
  const [copyRunAllMsg, setCopyRunAllMsg] = useState<string | null>(null);

  const filteredScenarios = activeTagFilter
    ? INCIDENT_SCENARIOS.filter((s) => s.tags?.includes(activeTagFilter))
    : INCIDENT_SCENARIOS;

  const selectedScenario = INCIDENT_SCENARIOS.find((s) => s.id === selectedId) ?? null;
  const compareRows = buildComparison(selectedScenario?.expected, normalizeResult, analyzeResult);

  function setTagFilter(tag: string | null) {
    setActiveTagFilter(tag);
    const next = tag ? INCIDENT_SCENARIOS.filter((s) => s.tags?.includes(tag)) : INCIDENT_SCENARIOS;
    if (next.length > 0 && !next.find((s) => s.id === selectedId)) {
      selectScenario(next[0].id);
    }
  }

  function selectScenario(id: string) {
    setSelectedId(id);
    setNormalizeResult(null);
    setAnalyzeResult(null);
    setNormalizeError(null);
    setAnalyzeError(null);
  }

  function resetResults() {
    setNormalizeResult(null);
    setAnalyzeResult(null);
    setNormalizeError(null);
    setAnalyzeError(null);
  }

  async function runNormalize(): Promise<NormalizedInput | null> {
    if (!selectedScenario) return null;
    setNormalizeLoading(true);
    setNormalizeError(null);
    try {
      const result = await normalizeIncident(buildNormalizeRequest(selectedScenario));
      setNormalizeResult(result);
      return result;
    } catch (err) {
      setNormalizeError(friendlyError(err));
      return null;
    } finally {
      setNormalizeLoading(false);
    }
  }

  async function runAnalyze(norm?: NormalizedInput): Promise<void> {
    const normalized = norm ?? normalizeResult;
    if (!normalized) {
      setAnalyzeError("normalize를 먼저 실행하세요");
      return;
    }
    if (!selectedScenario) return;
    setAnalyzeLoading(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeIncident(buildAnalyzeRequest(selectedScenario, normalized));
      setAnalyzeResult(result);
    } catch (err) {
      setAnalyzeError(friendlyError(err));
    } finally {
      setAnalyzeLoading(false);
    }
  }

  async function runBoth() {
    const norm = await runNormalize();
    if (norm) await runAnalyze(norm);
  }

  async function runAll() {
    const scenariosToRun = filteredScenarios;
    const filterNote = activeTagFilter
      ? `\n(현재 "${activeTagFilter}" 태그 필터 적용 중: 전체 ${INCIDENT_SCENARIOS.length}개 중 ${scenariosToRun.length}개)`
      : "";
    const confirmed = window.confirm(
      `${scenariosToRun.length}개 시나리오에 대해 normalize/analyze API를 순차 호출합니다.${filterNote}\nOpenAI API 비용과 시간이 발생할 수 있습니다. 계속할까요?`,
    );
    if (!confirmed) return;

    setRunAllLoading(true);
    setRunAllEntries(null);
    setRunAllProgress(0);

    const entries: RunAllEntry[] = [];

    for (let i = 0; i < scenariosToRun.length; i++) {
      const scenario = scenariosToRun[i];
      setRunAllProgress(i + 1);

      let norm: NormalizedInput | null = null;
      let analyze: AnalyzeResponse | null = null;
      let error: string | null = null;

      try {
        norm = await normalizeIncident(buildNormalizeRequest(scenario));
      } catch (err) {
        error = friendlyError(err);
      }

      if (norm && !error) {
        try {
          analyze = await analyzeIncident(buildAnalyzeRequest(scenario, norm));
        } catch (err) {
          error = friendlyError(err);
        }
      }

      const rows = buildComparison(scenario.expected, norm, analyze);
      entries.push({
        id: scenario.id,
        name: scenario.name,
        rows,
        passCount: rows.filter((r) => r.verdict === "PASS").length,
        failCount: rows.filter((r) => r.verdict === "FAIL").length,
        skipCount: rows.filter((r) => r.verdict === "SKIP").length,
        error,
      });
    }

    setRunAllEntries(entries);
    setRunAllLoading(false);
  }

  async function handleCopyScenarioReport() {
    if (!selectedScenario) return;
    const text = buildScenarioReport(selectedScenario, normalizeResult, analyzeResult, compareRows);
    try {
      await navigator.clipboard.writeText(text);
      setCopyScenarioMsg("요약 텍스트를 복사했습니다.");
    } catch {
      setCopyScenarioMsg("복사에 실패했습니다. 브라우저 권한을 확인하세요.");
    }
    setTimeout(() => setCopyScenarioMsg(null), 3000);
  }

  async function handleCopyRunAllSummary() {
    if (!runAllEntries) return;
    const text = buildRunAllSummary(runAllEntries);
    try {
      await navigator.clipboard.writeText(text);
      setCopyRunAllMsg("Run All 요약을 복사했습니다.");
    } catch {
      setCopyRunAllMsg("복사에 실패했습니다. 브라우저 권한을 확인하세요.");
    }
    setTimeout(() => setCopyRunAllMsg(null), 3000);
  }

  const anyLoading = normalizeLoading || analyzeLoading;

  return (
    <main className="min-h-screen bg-stone-100 p-4">
      <div className="mx-auto max-w-7xl">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="rounded bg-amber-200 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-900">
              DEV ONLY
            </span>
            <h1 className="mt-2 text-2xl font-bold text-stone-900">Incident Scenario Lab</h1>
            <p className="mt-1 text-sm text-stone-600">
              normalize → analyze 흐름을 시나리오 기반으로 확인하는 개발용 페이지입니다.
            </p>
          </div>
          <button
            type="button"
            onClick={runAll}
            disabled={runAllLoading}
            className="rounded-md border border-stone-400 bg-white px-4 py-2 text-sm font-bold text-stone-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {runAllLoading
              ? `실행 중 (${runAllProgress}/${filteredScenarios.length})`
              : activeTagFilter
              ? `Run All [${activeTagFilter}] (${filteredScenarios.length}개)`
              : `Run All Scenarios (${filteredScenarios.length}개)`}
          </button>
        </header>

        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-stone-500 mr-1">필터:</span>
          <button
            type="button"
            onClick={() => setTagFilter(null)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              activeTagFilter === null
                ? "bg-stone-800 text-white"
                : "bg-white border border-stone-300 text-stone-600 hover:border-stone-500"
            }`}
          >
            전체 ({INCIDENT_SCENARIOS.length})
          </button>
          {FILTER_TAGS.map((tag) => {
            const count = INCIDENT_SCENARIOS.filter((s) => s.tags?.includes(tag)).length;
            if (count === 0) return null;
            return (
              <button
                key={tag}
                type="button"
                onClick={() => setTagFilter(tag)}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  activeTagFilter === tag
                    ? `${TAG_COLORS[tag] ?? "bg-stone-100 text-stone-700"} ring-2 ring-stone-400`
                    : `${TAG_COLORS[tag] ?? "bg-stone-100 text-stone-700"} opacity-60 hover:opacity-100`
                }`}
              >
                {tag} ({count})
              </button>
            );
          })}
        </div>

        <div className="flex gap-4 items-start">
          <aside className="w-52 flex-shrink-0 space-y-2">
            {filteredScenarios.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => selectScenario(s.id)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  selectedId === s.id
                    ? "border-field-700 bg-white shadow-sm"
                    : "border-stone-200 bg-white hover:border-stone-400"
                }`}
              >
                <span className="text-xs font-mono font-bold text-stone-400">{s.id}</span>
                <p className="mt-1 text-sm font-semibold text-stone-900 leading-5">{s.name}</p>
                <p className="text-xs text-stone-500">{s.occurred_location}</p>
                {s.tags && s.tags.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {s.tags.map((tag) => (
                      <span
                        key={tag}
                        className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${TAG_COLORS[tag] ?? "bg-stone-100 text-stone-600"}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </aside>

          <div className="flex-1 min-w-0 space-y-4">
            {selectedScenario ? (
              <>
                <section className="rounded-lg border border-stone-200 bg-white p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="text-xs font-mono font-bold text-stone-400">{selectedScenario.id}</span>
                      <h2 className="mt-1 text-lg font-bold text-stone-900">{selectedScenario.name}</h2>
                      <p className="text-sm text-stone-500">발생장소: {selectedScenario.occurred_location}</p>
                    </div>
                    {selectedScenario.tags && (
                      <div className="flex flex-wrap gap-1 flex-shrink-0">
                        {selectedScenario.tags.map((tag) => (
                          <span
                            key={tag}
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${TAG_COLORS[tag] ?? "bg-stone-100 text-stone-600"}`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="mt-3 rounded-md bg-stone-50 p-3">
                    <p className="text-sm font-semibold text-stone-600 mb-1">situation_text</p>
                    <p className="text-sm leading-6 text-stone-900">{selectedScenario.situation_text}</p>
                  </div>
                  {selectedScenario.expected && (
                    <div className="mt-3 rounded-md bg-sky-50 border border-sky-200 p-3">
                      <p className="text-sm font-semibold text-sky-700 mb-2">Expected</p>
                      <div className="space-y-1">
                        {Object.entries(selectedScenario.expected).map(([k, v]) => (
                          <div key={k} className="flex gap-2 text-xs">
                            <span className="font-mono text-sky-600 w-40 flex-shrink-0">{k}</span>
                            <span className="text-stone-700">
                              {Array.isArray(v) ? v.join(", ") : String(v ?? "(없음)")}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </section>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={runNormalize}
                    disabled={anyLoading}
                    className="rounded-md bg-field-700 px-3 py-2 text-sm font-bold text-white disabled:bg-stone-300"
                  >
                    {normalizeLoading ? "실행 중..." : "Run Normalize"}
                  </button>
                  <button
                    type="button"
                    onClick={() => runAnalyze()}
                    disabled={anyLoading || !normalizeResult}
                    className="rounded-md bg-field-700 px-3 py-2 text-sm font-bold text-white disabled:bg-stone-300"
                  >
                    {analyzeLoading ? "실행 중..." : "Run Analyze"}
                  </button>
                  <button
                    type="button"
                    onClick={runBoth}
                    disabled={anyLoading}
                    className="rounded-md bg-stone-800 px-3 py-2 text-sm font-bold text-white disabled:bg-stone-300"
                  >
                    {anyLoading ? "실행 중..." : "Run Normalize + Analyze"}
                  </button>
                  <button
                    type="button"
                    onClick={resetResults}
                    disabled={anyLoading}
                    className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700"
                  >
                    Reset
                  </button>
                  {normalizeResult && (
                    <button
                      type="button"
                      onClick={() => copyText(JSON.stringify(normalizeResult, null, 2))}
                      className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700"
                    >
                      Copy Normalize JSON
                    </button>
                  )}
                  {analyzeResult && (
                    <button
                      type="button"
                      onClick={() => copyText(JSON.stringify(analyzeResult, null, 2))}
                      className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700"
                    >
                      Copy Analyze JSON
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleCopyScenarioReport}
                    disabled={anyLoading}
                    className="rounded-md border border-sky-400 bg-sky-50 px-3 py-2 text-sm font-bold text-sky-800 disabled:opacity-50"
                  >
                    Copy Scenario Report
                  </button>
                </div>

                {copyScenarioMsg && (
                  <div
                    className={`rounded-md border px-3 py-2 text-sm ${
                      copyScenarioMsg.includes("실패")
                        ? "border-red-200 bg-red-50 text-red-700"
                        : "border-emerald-200 bg-emerald-50 text-emerald-700"
                    }`}
                  >
                    {copyScenarioMsg}
                  </div>
                )}

                {normalizeError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    Normalize 오류: {normalizeError}
                  </div>
                )}
                {analyzeError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    Analyze 오류: {analyzeError}
                  </div>
                )}

                {normalizeResult && (
                  <section>
                    <h3 className="mb-2 text-sm font-bold text-stone-700 uppercase tracking-wide">
                      Normalize Result
                    </h3>
                    <AiFactorStatusPanel
                      normalized={normalizeResult}
                      missingInfoQuestions={normalizeResult.missing_info_questions ?? []}
                    />
                    {(normalizeResult.missing_info_questions?.length ?? 0) > 0 && (
                      <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-3">
                        <p className="text-sm font-semibold text-amber-800 mb-2">Missing Info Questions</p>
                        <ul className="space-y-2">
                          {normalizeResult.missing_info_questions?.map((q, i) => (
                            <li key={`${q.field}-${i}`} className="text-sm">
                              <span className="font-mono text-xs text-amber-600">[{q.field}]</span>{" "}
                              <span className="text-stone-800">{q.question}</span>
                              <p className="text-xs text-stone-500 mt-0.5">{q.reason}</p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </section>
                )}

                {analyzeResult && (
                  <section className="space-y-3">
                    <h3 className="text-sm font-bold text-stone-700 uppercase tracking-wide">
                      Analyze Result
                    </h3>

                    <div className="rounded-lg border border-stone-200 bg-white p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-semibold text-stone-500">임시 위험도</p>
                          <p className="text-xl font-bold text-stone-900">{analyzeResult.risk_score.level}</p>
                          <p className="text-xs text-stone-400">공식 예상 피해등급 적용 전 값입니다.</p>
                        </div>
                        <div className="rounded-md bg-field-700 px-4 py-2 text-lg font-bold text-white">
                          {analyzeResult.risk_score.score}
                        </div>
                      </div>
                      {(analyzeResult.risk_score.reasons?.length ?? 0) > 0 && (
                        <ul className="mt-3 list-disc pl-5 space-y-1">
                          {analyzeResult.risk_score.reasons?.map((r, i) => (
                            <li key={`${r}-${i}`} className="text-sm text-stone-700">
                              {r}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {analyzeResult.action_guide && (
                      <div className="rounded-lg border border-stone-200 bg-white p-4">
                        <p className="text-sm font-bold text-stone-800 mb-1">조치 가이드</p>
                        <p className="text-sm text-stone-700 leading-6">{analyzeResult.action_guide.summary}</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <div>
                            <p className="text-xs font-semibold text-stone-600 mb-1">즉시조치</p>
                            <ul className="list-disc pl-4 space-y-1">
                              {analyzeResult.action_guide.immediate_actions.map((a, i) => (
                                <li key={`ia-${i}`} className="text-xs text-stone-700">
                                  {a}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <p className="text-xs font-semibold text-stone-600 mb-1">후속조치</p>
                            <ul className="list-disc pl-4 space-y-1">
                              {analyzeResult.action_guide.follow_up_actions.map((a, i) => (
                                <li key={`fa-${i}`} className="text-xs text-stone-700">
                                  {a}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    )}

                    {analyzeResult.prevention_list.length > 0 && (
                      <div className="rounded-lg border border-stone-200 bg-white p-4">
                        <p className="text-sm font-bold text-stone-800 mb-2">
                          예방대책 ({analyzeResult.prevention_list.length}개)
                        </p>
                        <div className="space-y-2">
                          {analyzeResult.prevention_list.map((item) => (
                            <div
                              key={item.prevention_id}
                              className="rounded border border-stone-100 bg-stone-50 px-3 py-2"
                            >
                              <div className="flex items-center gap-2 text-xs text-stone-500 mb-1">
                                <span className="font-bold text-field-700">#{item.priority}</span>
                                <span className="font-mono">{item.prevention_id}</span>
                                <span>{item.major_category} / {item.middle_category}</span>
                              </div>
                              <p className="text-sm text-stone-900">{item.content}</p>
                              {item.recommended_reason && (
                                <p className="text-xs text-stone-500 mt-1">{item.recommended_reason}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {analyzeResult.similar_cases.length > 0 && (
                      <div className="rounded-lg border border-stone-200 bg-white p-4">
                        <p className="text-sm font-bold text-stone-800 mb-2">유사 사례</p>
                        <div className="space-y-2">
                          {analyzeResult.similar_cases.map((c) => (
                            <div key={c.case_id} className="rounded border border-stone-100 bg-stone-50 px-3 py-2">
                              <div className="flex justify-between text-xs text-stone-500 mb-1">
                                <span className="font-mono">{c.case_id}</span>
                                <span>{Math.round(c.similarity * 100)}%</span>
                              </div>
                              <p className="text-sm text-stone-900">{c.accident_summary}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                )}

                {compareRows.length > 0 && (
                  <section>
                    <h3 className="mb-2 text-sm font-bold text-stone-700 uppercase tracking-wide">
                      Expected vs Actual
                    </h3>
                    <div className="rounded-lg border border-stone-200 bg-white overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-stone-50 border-b border-stone-200">
                            <th className="px-3 py-2 text-left text-xs font-bold text-stone-600 w-40">Field</th>
                            <th className="px-3 py-2 text-left text-xs font-bold text-stone-600">Expected</th>
                            <th className="px-3 py-2 text-left text-xs font-bold text-stone-600">Actual</th>
                            <th className="px-3 py-2 text-left text-xs font-bold text-stone-600 w-16">Result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {compareRows.map((row, i) => (
                            <tr
                              key={`${row.field}-${i}`}
                              className="border-b border-stone-100 last:border-0"
                            >
                              <td className="px-3 py-2 font-mono text-xs text-stone-500">{row.field}</td>
                              <td className="px-3 py-2 text-stone-700">{row.expected}</td>
                              <td className="px-3 py-2 text-stone-900">{row.actual}</td>
                              <td className={`px-3 py-2 text-xs ${VERDICT_COLORS[row.verdict]}`}>
                                {row.verdict}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="bg-stone-50 border-t border-stone-200 px-3 py-2 text-xs text-stone-500">
                        PASS {compareRows.filter((r) => r.verdict === "PASS").length} ·{" "}
                        FAIL {compareRows.filter((r) => r.verdict === "FAIL").length} ·{" "}
                        SKIP {compareRows.filter((r) => r.verdict === "SKIP").length}
                      </div>
                    </div>
                  </section>
                )}

                <section className="space-y-2">
                  <h3 className="text-sm font-bold text-stone-700 uppercase tracking-wide">Debug JSON</h3>
                  {normalizeResult && (
                    <JsonBlock
                      title="Normalize Result"
                      data={normalizeResult}
                      onCopy={() => copyText(JSON.stringify(normalizeResult, null, 2))}
                    />
                  )}
                  {analyzeResult && (
                    <JsonBlock
                      title="Analyze Result"
                      data={analyzeResult}
                      onCopy={() => copyText(JSON.stringify(analyzeResult, null, 2))}
                    />
                  )}
                  {selectedScenario.expected && (
                    <JsonBlock
                      title="Expected JSON"
                      data={selectedScenario.expected}
                      onCopy={() => copyText(JSON.stringify(selectedScenario.expected, null, 2))}
                    />
                  )}
                  <JsonBlock
                    title="Request Payload"
                    data={buildNormalizeRequest(selectedScenario)}
                    onCopy={() => copyText(JSON.stringify(buildNormalizeRequest(selectedScenario), null, 2))}
                  />
                </section>
              </>
            ) : (
              <div className="rounded-lg border border-stone-200 bg-white p-8 text-center text-stone-500">
                왼쪽에서 시나리오를 선택하세요.
              </div>
            )}
          </div>
        </div>

        {runAllEntries && (
          <section className="mt-6">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h3 className="text-sm font-bold text-stone-700 uppercase tracking-wide">
                Run All Results
              </h3>
              <button
                type="button"
                onClick={handleCopyRunAllSummary}
                className="rounded-md border border-sky-400 bg-sky-50 px-3 py-1.5 text-sm font-bold text-sky-800"
              >
                Copy Run All Summary
              </button>
              {copyRunAllMsg && (
                <span
                  className={`text-sm ${
                    copyRunAllMsg.includes("실패") ? "text-red-600" : "text-emerald-700"
                  }`}
                >
                  {copyRunAllMsg}
                </span>
              )}
            </div>
            <div className="rounded-lg border border-stone-200 bg-white overflow-hidden mb-4">
              <div className="bg-stone-50 px-4 py-3 border-b border-stone-200 flex gap-6 text-sm">
                <span>
                  총 <strong>{runAllEntries.length}</strong>개
                </span>
                <span className="text-emerald-700">
                  PASS {runAllEntries.reduce((a, e) => a + e.passCount, 0)}
                </span>
                <span className="text-red-700">
                  FAIL {runAllEntries.reduce((a, e) => a + e.failCount, 0)}
                </span>
                <span className="text-stone-400">
                  SKIP {runAllEntries.reduce((a, e) => a + e.skipCount, 0)}
                </span>
                <span className="text-red-600">
                  ERROR {runAllEntries.filter((e) => e.error).length}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-200 bg-stone-50">
                    <th className="px-3 py-2 text-left text-xs font-bold text-stone-600">ID</th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-stone-600">Name</th>
                    <th className="px-3 py-2 text-center text-xs font-bold text-emerald-700">PASS</th>
                    <th className="px-3 py-2 text-center text-xs font-bold text-red-700">FAIL</th>
                    <th className="px-3 py-2 text-center text-xs font-bold text-stone-400">SKIP</th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-stone-600">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {runAllEntries.map((entry) => (
                    <tr
                      key={entry.id}
                      className={`border-b border-stone-100 last:border-0 ${entry.error ? "bg-red-50" : entry.failCount > 0 ? "bg-orange-50" : ""}`}
                    >
                      <td className="px-3 py-2 font-mono text-xs text-stone-500">{entry.id}</td>
                      <td className="px-3 py-2 text-stone-800">{entry.name}</td>
                      <td className="px-3 py-2 text-center text-emerald-700 font-bold">{entry.passCount}</td>
                      <td className="px-3 py-2 text-center text-red-700 font-bold">{entry.failCount}</td>
                      <td className="px-3 py-2 text-center text-stone-400">{entry.skipCount}</td>
                      <td className="px-3 py-2 text-xs text-red-600">{entry.error ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

interface JsonBlockProps {
  title: string;
  data: unknown;
  onCopy: () => void;
}

function JsonBlock({ title, data, onCopy }: JsonBlockProps) {
  return (
    <details className="rounded-lg border border-stone-300 bg-stone-950 text-stone-100">
      <summary className="cursor-pointer px-4 py-3 text-sm font-bold">{title}</summary>
      <div className="border-t border-stone-700 p-4">
        <button
          type="button"
          onClick={onCopy}
          className="mb-3 rounded-md border border-stone-500 px-3 py-1 text-xs font-semibold text-stone-100"
        >
          복사
        </button>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs leading-5">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </details>
  );
}
