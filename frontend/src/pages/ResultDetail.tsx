import type { AnalyzeResponse } from "../types/api";

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
            <p className="text-sm font-semibold text-stone-600">위험도</p>
            <p className="mt-1 text-2xl font-bold text-field-900">{result.risk_score.level}</p>
          </div>
          <div className="rounded-md bg-field-700 px-4 py-3 text-xl font-bold text-white">
            {result.risk_score.score}
          </div>
        </div>
      </section>

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
    </div>
  );
}
