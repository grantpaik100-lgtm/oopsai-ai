import type { AnalyzeResponse } from "../types/api";
import AiDebugPanel from "../components/AiDebugPanel";

interface ResultDetailProps {
  result: AnalyzeResponse;
  onReset: () => void;
}

export default function ResultDetail({ result, onReset }: ResultDetailProps) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-semibold text-field-700">접수 번호 {result.meta.case_id}</p>
        <h2 className="mt-1 text-2xl font-bold text-field-900">AI 예방대책 결과</h2>
      </div>

      <section className="rounded-lg border border-stone-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-stone-600">임시 위험도</p>
            <p className="mt-1 text-2xl font-bold text-field-900">{result.risk_score.level}</p>
            <p className="mt-1 text-sm text-stone-500">공식 예상 피해등급 적용 전 값입니다.</p>
          </div>
          <div className="rounded-md bg-field-700 px-4 py-3 text-xl font-bold text-white">
            {result.risk_score.score}
          </div>
        </div>
        {(result.risk_score.reasons?.length ?? 0) > 0 && (
          <div className="mt-4 border-t border-stone-200 pt-3">
            <p className="text-sm font-semibold text-stone-700">판단 근거</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">
              {result.risk_score.reasons?.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}
            </ul>
          </div>
        )}
      </section>

      {result.predicted_severity && (
        <section className="rounded-lg border border-stone-200 bg-white p-4">
          <p className="text-xs text-stone-400 mb-1">아차사고가 실제 사고로 이어졌을 경우의 예상 등급입니다.</p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-stone-600">예상 피해등급</p>
              <p className="mt-1 text-2xl font-bold text-field-900">
                {result.predicted_severity.label}
              </p>
              <p className="mt-1 text-sm text-stone-500">
                신뢰도: {result.predicted_severity.confidence}
              </p>
            </div>
            {result.predicted_severity.grade && (
              <div className="rounded-md bg-field-700 px-4 py-3 text-2xl font-bold text-white">
                {result.predicted_severity.grade}
              </div>
            )}
          </div>
          {result.predicted_severity.prediction_reason.length > 0 && (
            <div className="mt-3 border-t border-stone-200 pt-3">
              <p className="text-sm font-semibold text-stone-700">판단 근거</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">
                {result.predicted_severity.prediction_reason.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          {result.predicted_severity.why_not_higher && (
            <p className="mt-2 text-sm text-stone-500">더 높은 등급이 아닌 이유: {result.predicted_severity.why_not_higher}</p>
          )}
          {result.predicted_severity.why_not_lower && (
            <p className="mt-2 text-sm text-stone-500">더 낮은 등급이 아닌 이유: {result.predicted_severity.why_not_lower}</p>
          )}
          {result.predicted_severity.missing_information.length > 0 && (
            <p className="mt-2 text-sm text-amber-600">
              부족한 정보: {result.predicted_severity.missing_information.join(", ")}
            </p>
          )}
          {result.predicted_severity.validation_warnings.length > 0 && (
            <p className="mt-2 text-sm text-red-600">
              주의: {result.predicted_severity.validation_warnings.join("; ")}
            </p>
          )}
        </section>
      )}

      {result.action_guide && (
        <section className="rounded-lg border border-stone-200 bg-white p-4">
          <h3 className="text-lg font-bold text-field-900">조치 가이드</h3>
          <p className="mt-2 text-sm leading-6 text-stone-700">{result.action_guide.summary}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-stone-700">즉시조치</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">
                {result.action_guide.immediate_actions.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-stone-700">후속조치</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">
                {result.action_guide.follow_up_actions.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
          <p className="mt-4 rounded-md bg-field-50 px-3 py-2 text-sm leading-6 text-stone-700">
            기대 결과 예시: {result.action_guide.expected_result_example}
          </p>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-lg font-bold text-field-900">예방대책</h3>
        <div className="space-y-3">
          {result.prevention_list.map((item) => (
            <article key={item.prevention_id} className="rounded-lg border border-stone-200 bg-white p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-stone-600">
                <span className="font-bold text-field-700">#{item.priority}</span>
                <span>{item.major_category}</span>
                <span>/</span>
                <span>{item.middle_category}</span>
              </div>
              <p className="font-medium leading-7 text-stone-900">{item.content}</p>
              {item.recommended_reason && (
                <p className="mt-2 rounded-md bg-field-50 px-3 py-2 text-sm leading-6 text-stone-700">
                  추천 근거: {item.recommended_reason}
                </p>
              )}
              <p className="mt-2 text-sm text-stone-600">
                기대효과: {item.expected_action_result.expected_effect || item.expected_action_result.effect_summary}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-lg font-bold text-field-900">유사 사례</h3>
        <div className="space-y-3">
          {result.similar_cases.map((item) => (
            <article key={item.case_id} className="rounded-lg border border-stone-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between text-sm text-stone-600">
                <span className="font-semibold">{item.case_id}</span>
                <span>{Math.round(item.similarity * 100)}%</span>
              </div>
              <p className="leading-7 text-stone-900">{item.accident_summary}</p>
              <p className="mt-2 text-sm text-stone-600">사고유형: {item.accident_type}</p>
            </article>
          ))}
        </div>
      </section>

      <button
        type="button"
        onClick={onReset}
        className="w-full rounded-md border border-field-700 bg-white px-4 py-3 text-sm font-bold text-field-700"
      >
        새 신고 작성
      </button>

      <AiDebugPanel
        title="AI Debug · Analyze Result"
        data={{
          analysis_reason: result.analysis_reason,
          predicted_severity: result.predicted_severity,
          risk_score: result.risk_score,
          action_guide: result.action_guide,
          prevention_list: result.prevention_list.map((item) => ({
            prevention_id: item.prevention_id,
            priority: item.priority,
            recommended_reason: item.recommended_reason,
            content: item.content,
          })),
          similar_cases: result.similar_cases,
          raw: result,
        }}
      />
    </div>
  );
}
