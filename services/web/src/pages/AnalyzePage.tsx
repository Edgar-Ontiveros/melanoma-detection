import { useEffect, useRef, useState } from "react";

import { predict, type PredictResponse } from "../api";
import type { ModelInfoState } from "../App";
import CamViewer from "../components/CamViewer";
import Details from "../components/Details";
import ErrorBox from "../components/ErrorBox";
import Examples, { type Example } from "../components/Examples";
import ProbabilityBlock from "../components/ProbabilityBlock";
import Recommendation from "../components/Recommendation";
import Uploader from "../components/Uploader";
import { formatSeconds } from "../lib/format";

interface Pending {
  blob: Blob;
  name: string;
  previewUrl: string;
  example: Example | null;
}

export default function AnalyzePage({
  state,
  onBusy,
}: {
  state: ModelInfoState;
  onBusy?: (busy: boolean) => void;
}) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);

  useEffect(() => {
    onBusy?.(loading);
    if (!loading) return;
    startedAt.current = performance.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed(performance.now() - startedAt.current), 100);
    return () => window.clearInterval(id);
  }, [loading, onBusy]);

  useEffect(
    () => () => {
      if (pending) URL.revokeObjectURL(pending.previewUrl);
    },
    [pending],
  );

  const analyze = async (p: Pending) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await predict(p.blob, p.name));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  const submit = (blob: Blob, name: string, example: Example | null) => {
    const p: Pending = { blob, name, previewUrl: URL.createObjectURL(blob), example };
    setPending(p);
    void analyze(p);
  };

  const reset = () => {
    setPending(null);
    setResult(null);
    setError(null);
  };

  const metrics = state.info?.metrics ?? null;

  if (!pending) {
    return (
      <>
        <h1>Analizar una dermatoscopía</h1>
        <p className="subtitle">Apoyo a la decisión de referir lesiones en dermatoscopía. No es un diagnóstico.</p>
        <Uploader onFile={(f) => submit(f, f.name, null)} disabled={loading} />
        <Examples onPick={(ex, blob) => submit(blob, `${ex.image_id}.jpg`, ex)} disabled={loading} />
      </>
    );
  }

  return (
    <>
      <h1 className="sr-only">Resultado del análisis</h1>
      <div className="result-line">
        <span className="id">
          <code>{pending.name}</code>
          {loading && (
            <span className="elapsed" aria-live="polite">
              Analizando… {formatSeconds(elapsed)}
            </span>
          )}
        </span>
        <button type="button" className="secondary" onClick={reset} disabled={loading}>
          Analizar otra imagen
        </button>
      </div>

      <div className="result">
        <div className="image">
          <img src={pending.previewUrl} alt={`Vista previa de ${pending.name}`} />
          {pending.example && (
            <p className="caption">Ejemplo de validación de ISIC 2020, CC BY-NC: {pending.example.note}.</p>
          )}
        </div>
        <div className="panels">
          {error !== null && <ErrorBox error={error} onRetry={() => void analyze(pending)} />}
          {result && (
            <>
              <ProbabilityBlock
                probability={result.probability}
                threshold={result.threshold}
                prevalence={metrics?.prevalence ?? null}
              />
              <Recommendation refer={result.refer} npvTest={metrics?.tau_95.npv ?? null} />
              <CamViewer cam={result.cam} />
              <Details result={result} />
              <p className="caption">{result.disclaimer}</p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
