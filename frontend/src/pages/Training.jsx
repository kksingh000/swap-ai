import { useState } from 'react'

import { LeadBadge, useFetch, useToasts } from '../components/common'
import { api } from '../services/api'

export default function Training() {
  const results = useFetch(api.trainingResults, [])
  const [busy, setBusy] = useState('')
  const [text, setText] = useState('Mujhe branded jackets chahiye 1500 tak, is hafte chahiye')
  const [comparison, setComparison] = useState(null)
  const [benchmark, setBenchmark] = useState(null)
  const [samples, setSamples] = useState(null)
  const { push, host } = useToasts()

  const metrics = results.data?.metrics
  const report = metrics?.classification_report

  async function run(kind, fn, message) {
    setBusy(kind)
    try {
      const result = await fn()
      push(message, 'success')
      return result
    } catch (error) {
      push(error.message, 'warn')
      return null
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="stack">
      {host}

      <div className="banner">
        <span>🧠</span>
        <div>
          <strong>Phase 1 is prompting + rules + RAG; Phase 2 is a small trained classifier.</strong>{' '}
          A 3-billion-parameter LLM is overkill for “is this lead hot?”, so that job goes to a TF-IDF
          (word + character n-gram) model — a few hundred KB, sub-millisecond on CPU, and character
          n-grams absorb Hinglish spelling variation like <em>nahi / nahin / nai</em>.
        </div>
      </div>

      <div className="grid grid-3">
        <div className="card">
          <div className="card-title">1 · Dataset</div>
          <div className="faint" style={{ marginBottom: 12 }}>
            {results.data?.dataset_rows || 0} synthetic utterances across English, Hindi and Hinglish.
          </div>
          <button
            disabled={busy === 'dataset'}
            onClick={async () => {
              const result = await run(
                'dataset',
                () => api.generateDataset({ samples_per_label: 180, seed: 42 }),
                'Dataset generated',
              )
              if (result) {
                setSamples(result.sample)
                results.reload()
              }
            }}
          >
            {busy === 'dataset' ? 'Generating…' : 'Generate dataset'}
          </button>
        </div>

        <div className="card">
          <div className="card-title">2 · Train</div>
          <div className="faint" style={{ marginBottom: 12 }}>
            Held out by <strong>whole template</strong>, so the test set contains phrasings the model
            has never seen.
          </div>
          <button
            className="btn-primary"
            disabled={busy === 'train'}
            onClick={async () => {
              const result = await run(
                'train',
                () => api.trainModel({ model_type: 'tfidf_logreg', test_size: 0.2 }),
                'Model trained',
              )
              if (result) results.reload()
            }}
          >
            {busy === 'train' ? 'Training…' : 'Train classifier'}
          </button>
        </div>

        <div className="card">
          <div className="card-title">3 · Benchmark</div>
          <div className="faint" style={{ marginBottom: 12 }}>
            Rules vs classifier, and how often they agree.
          </div>
          <button
            disabled={busy === 'bench'}
            onClick={async () => {
              const result = await run('bench', api.benchmark, 'Benchmark complete')
              if (result) setBenchmark(result)
            }}
          >
            {busy === 'bench' ? 'Running…' : 'Run benchmark'}
          </button>
        </div>
      </div>

      {metrics && (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)' }}>
          <div className="card">
            <div className="card-title">Model performance</div>
            <div className="grid grid-2" style={{ marginBottom: 16 }}>
              <div>
                <div className="faint">Holdout accuracy (unseen phrasings)</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--success)' }}>
                  {(metrics.accuracy * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="faint">5-fold cross-validation</div>
                <div style={{ fontSize: 26, fontWeight: 700 }}>
                  {(metrics.cv_mean_accuracy * 100).toFixed(1)}%
                </div>
                <div className="faint">± {(metrics.cv_std * 100).toFixed(1)}%</div>
              </div>
            </div>
            <div className="faint" style={{ marginBottom: 12 }}>
              Split: {metrics.split_strategy} · {metrics.rows} rows · {metrics.model}
            </div>

            {report && (
              <table className="table">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1</th>
                    <th>Support</th>
                  </tr>
                </thead>
                <tbody>
                  {['HOT', 'WARM', 'COLD'].map(
                    (label) =>
                      report[label] && (
                        <tr key={label} style={{ cursor: 'default' }}>
                          <td><LeadBadge status={label} /></td>
                          <td>{report[label].precision.toFixed(3)}</td>
                          <td>{report[label].recall.toFixed(3)}</td>
                          <td>{report[label]['f1-score'].toFixed(3)}</td>
                          <td>{report[label].support}</td>
                        </tr>
                      ),
                  )}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <div className="card-title">Confusion matrix</div>
            <table className="table">
              <thead>
                <tr>
                  <th>true ↓ / pred →</th>
                  {metrics.confusion_matrix.labels.map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.confusion_matrix.matrix.map((row, index) => (
                  <tr key={index} style={{ cursor: 'default' }}>
                    <td><strong>{metrics.confusion_matrix.labels[index]}</strong></td>
                    {row.map((value, column) => (
                      <td
                        key={column}
                        style={{
                          fontWeight: index === column ? 700 : 400,
                          color: index === column ? 'var(--success)' : 'var(--text-dim)',
                        }}
                      >
                        {value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="card-title" style={{ marginTop: 20 }}>Dataset mix</div>
            <div className="wrap">
              {Object.entries(metrics.dataset_stats?.by_language || {}).map(([language, count]) => (
                <span className="chip" key={language}>{language}: {count}</span>
              ))}
              {Object.entries(metrics.dataset_stats?.by_label || {}).map(([label, count]) => (
                <span className="chip chip-accent" key={label}>{label}: {count}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {benchmark && (
        <div className="card">
          <div className="card-title">Benchmark: rules vs classifier</div>
          <div className="grid grid-3">
            <div>
              <div className="faint">Rules accuracy</div>
              <strong style={{ fontSize: 20 }}>{(benchmark.rules_accuracy * 100).toFixed(1)}%</strong>
            </div>
            <div>
              <div className="faint">Classifier accuracy</div>
              <strong style={{ fontSize: 20 }}>
                {benchmark.classifier_accuracy != null
                  ? `${(benchmark.classifier_accuracy * 100).toFixed(1)}%`
                  : 'not trained'}
              </strong>
            </div>
            <div>
              <div className="faint">Agreement</div>
              <strong style={{ fontSize: 20 }}>
                {benchmark.agreement != null ? `${(benchmark.agreement * 100).toFixed(1)}%` : '—'}
              </strong>
            </div>
          </div>
          <div className="faint" style={{ marginTop: 12 }}>{benchmark.note}</div>
        </div>
      )}

      <div className="card">
        <div className="card-title">Try it: classify one utterance</div>
        <div className="row">
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && api.classify(text).then(setComparison)}
            placeholder="Type English, Hindi or Hinglish…"
          />
          <button className="btn-primary" onClick={() => api.classify(text).then(setComparison).catch((e) => push(e.message, 'warn'))}>
            Classify
          </button>
        </div>

        {comparison && (
          <>
            <div className="grid grid-3" style={{ marginTop: 16 }}>
              <div className="card" style={{ background: 'var(--bg)' }}>
                <div className="faint">Rules engine</div>
                <div className="row" style={{ marginTop: 4 }}>
                  <LeadBadge status={comparison.methods.rules.label} />
                  <strong>{comparison.methods.rules.score}/100</strong>
                </div>
              </div>
              <div className="card" style={{ background: 'var(--bg)' }}>
                <div className="faint">Trained classifier</div>
                <div className="row" style={{ marginTop: 4 }}>
                  {comparison.methods.classifier ? (
                    <>
                      <LeadBadge status={comparison.methods.classifier.label} />
                      <strong>{Math.round(comparison.methods.classifier.confidence * 100)}%</strong>
                    </>
                  ) : (
                    <span className="faint">not trained</span>
                  )}
                </div>
              </div>
              <div className="card" style={{ background: 'var(--bg)' }}>
                <div className="faint">LLM</div>
                <div className="row" style={{ marginTop: 4 }}>
                  {comparison.methods.llm ? (
                    <LeadBadge status={comparison.methods.llm.label} />
                  ) : (
                    <span className="faint">no LLM configured</span>
                  )}
                </div>
              </div>
            </div>

            <div className="card-title" style={{ marginTop: 18 }}>Structured extraction</div>
            <div className="wrap">
              <span className="chip chip-accent">intent: {comparison.extracted.intent}</span>
              <span className="chip">language: {comparison.extracted.language}</span>
              {comparison.extracted.budget?.amount && (
                <span className="chip">budget: ₹{comparison.extracted.budget.amount} ({comparison.extracted.budget.qualifier || 'exact'})</span>
              )}
              {comparison.extracted.product_categories?.map((category) => (
                <span className="chip" key={category}>item: {category}</span>
              ))}
              {comparison.extracted.brands?.map((brand) => (
                <span className="chip" key={brand}>brand: {brand}</span>
              ))}
              <span className="chip">urgency: {comparison.extracted.urgency}</span>
              <span className="chip">sentiment: {comparison.extracted.sentiment}</span>
              {comparison.extracted.requires_whatsapp && <span className="chip chip-good">wants catalogue</span>}
              {comparison.extracted.requires_callback && <span className="chip chip-good">wants callback</span>}
            </div>
          </>
        )}
      </div>

      {samples && (
        <div className="card">
          <div className="card-title">Sample training rows</div>
          {samples.map((row, index) => (
            <div className="kv" key={index}>
              <span className="kv-key">{row.utterance}</span>
              <span className="row">
                <span className="chip">{row.language}</span>
                <LeadBadge status={row.label} />
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
