import { marked } from "marked";
import { useEffect, useState } from "react";

import {
  ApiError,
  limitations,
  type Interval,
  type Limitations,
  type Metrics,
  type ModelInfo,
} from "../api";
import type { ModelInfoState } from "../App";
import ErrorBox from "../components/ErrorBox";
import { formatDateEs, formatInt, formatPercent } from "../lib/format";

const REPO = "https://github.com/Edgar-Ontiveros/melanoma-detection";
const ISIC_DOI = "https://doi.org/10.34970/2020-ds01"; // DOI del dataset (no es una métrica)

function ci(x: Interval, decimals = 3): string {
  const f = (v: number) => v.toFixed(decimals).replace(".", ",");
  return `${f(x.point)} [${f(x.lo)}, ${f(x.hi)}]`;
}

/** Valor con su intervalo en gris: "0,843" + "[0,804, 0,881]". */
function Val({ text }: { text: string }) {
  const i = text.indexOf("[");
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <span className="ci">{text.slice(i)}</span>
    </>
  );
}

/** Porcentaje con su intervalo cuando la API lo trae. */
function pctCi(
  value: number,
  interval: Interval | undefined,
  decimals = 1,
): string {
  const v = formatPercent(value, decimals);
  if (!interval) return v;
  return `${v} [${formatPercent(interval.lo, decimals)}, ${formatPercent(interval.hi, decimals)}]`;
}

function metricRows(m: Metrics): [string, string][] {
  const t = m.tau_95;
  return [
    ["AUC-ROC", ci(m.auroc)],
    ["AUPRC", ci(m.auprc)],
    [
      "Sensibilidad en τ95",
      `${pctCi(t.sensitivity, t.ci?.sensitivity)} (${t.tp} de ${t.tp + t.fn} melanomas)`,
    ],
    [
      "Especificidad en τ95",
      `${pctCi(t.specificity, t.ci?.specificity)} (${formatInt(t.tn)} de ${formatInt(t.tn + t.fp)} benignas)`,
    ],
    ["Valor predictivo positivo", pctCi(t.ppv, t.ci?.ppv)],
    ["Valor predictivo negativo", pctCi(t.npv, t.ci?.npv, 2)],
    ["Prevalencia en el conjunto de prueba", formatPercent(m.prevalence, 2)],
  ];
}

function Performance({ info }: { info: ModelInfo }) {
  const m = info.metrics;
  const prev = info.previous_model ?? m.previous_model ?? null;
  const level = Math.round(m.ci.level * 100);
  const rows = metricRows(m);
  const prevRows = prev ? metricRows(prev) : null;
  return (
    <>
      {info.ensemble && (
        <p>
          El modelo es un{" "}
          <strong>ensamble de {info.ensemble.members} redes</strong> de la misma
          arquitectura, entrenadas con semillas distintas; su salida es el
          promedio de los logits.
          {prev &&
            " La tabla compara su desempeño con el del modelo único anterior, medido sobre el mismo conjunto de prueba."}
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th scope="col">Métrica</th>
            {prevRows && (
              <th scope="col">{prev?.label ?? "Modelo anterior"}</th>
            )}
            <th scope="col">
              {prevRows
                ? (m.label ?? "Modelo actual")
                : `Valor [intervalo de confianza del ${level} %]`}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, v], i) => (
            <tr key={k}>
              <th scope="row">{k}</th>
              {prevRows && (
                <td className="num">
                  <Val text={prevRows[i][1]} />
                </td>
              )}
              <td className="num">
                <Val text={v} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Medido{" "}
        {prev
          ? "en el segundo y último acceso al conjunto de prueba"
          : "una sola vez"}{" "}
        sobre {formatInt(m.n_images)} imágenes de {formatInt(m.n_patients)}{" "}
        pacientes que el modelo nunca vio, el {formatDateEs(m.date)}
        {prev && `; el modelo anterior, el ${formatDateEs(prev.date)}`}.
        Intervalos del {level} % por bootstrap por paciente (
        {formatInt(m.ci.n_resamples)} remuestreos). El umbral τ95 se fijó sobre
        validación para una sensibilidad objetivo de{" "}
        {formatPercent(info.thresholds.tau_95.sensitivity_target, 0)}.
      </p>
    </>
  );
}

function LimitationsSection() {
  const [data, setData] = useState<Limitations | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const load = () => {
    setError(null);
    setPending(false);
    limitations()
      .then(setData)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) setPending(true);
        else setError(e);
      });
  };
  useEffect(load, []);

  if (pending) {
    return (
      <div className="notice" role="status">
        <strong>Pendiente.</strong> Las limitaciones del modelo (
        <code>docs/f4_limitations.md</code>) todavía no están escritas. Esta
        ficha no está completa sin ellas.
      </div>
    );
  }
  if (error !== null) return <ErrorBox error={error} onRetry={load} />;
  if (!data) return <p className="help">Cargando…</p>;
  const html = marked.parse(data.markdown, { async: false }) as string;
  return (
    <div className="limitations">
      <p className="help">
        Texto del autor, renderizado desde <code>{data.source}</code>.
      </p>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

export default function ModelPage({ state }: { state: ModelInfoState }) {
  const info = state.info;
  return (
    <>
      <div className="model">
        <h1>Ficha del modelo</h1>
        <p className="subtitle">
          Qué es este sistema, cómo se midió, cómo leer su probabilidad y qué no
          puede hacer.
        </p>

        <section aria-labelledby="s1">
          <h2 id="s1">Qué es y qué no es</h2>
          <ul>
            <li>
              Apoyo a la decisión de referir lesiones con sospecha de melanoma
              en imágenes dermatoscópicas: sugiere si conviene referir.
            </li>
            {info?.ensemble && (
              <li>
                Ensamble de {info.ensemble.members} redes convolucionales de la
                misma arquitectura, entrenadas con semillas distintas; la salida
                es el promedio de sus logits.
              </li>
            )}
            <li>
              No detecta otros cánceres de piel ni otras enfermedades; no es un
              diagnóstico.
            </li>
            <li>
              Sin aprobación regulatoria (COFEPRIS, FDA, CE). Uso educativo y de
              investigación.
            </li>
          </ul>
        </section>

        <section aria-labelledby="s2">
          <h2 id="s2">Desempeño validado</h2>
          {info ? (
            <Performance info={info} />
          ) : state.loading ? (
            <p className="help">Cargando…</p>
          ) : (
            <ErrorBox
              error={new ApiError(0, state.error ?? "")}
              onRetry={state.reload}
            />
          )}
        </section>

        <section aria-labelledby="s3">
          <h2 id="s3">Cómo leer la probabilidad</h2>
          <p>
            La probabilidad que muestra la pantalla de análisis está calibrada
            {info
              ? ` (${info.calibration.method === "platt" ? "escalado de Platt" : info.calibration.method}, ajustado sobre ${formatInt(info.calibration.n_images)} imágenes de validación con ${info.calibration.n_positives} melanomas)`
              : ""}
            : un 3 % significa que, de cada 100 lesiones que recibieron esa
            puntuación en validación, alrededor de 3 resultaron melanoma. No es
            la probabilidad de que «el modelo acierte», y una probabilidad baja
            no descarta melanoma: el umbral de referencia está muy por debajo
            del 50 % precisamente para no dejar pasar casos.
          </p>
        </section>

        <section aria-labelledby="s4">
          <h2 id="s4">Limitaciones</h2>
          <LimitationsSection />
        </section>

        <section aria-labelledby="s5">
          <h2 id="s5">Datos y licencias</h2>
          <ul>
            <li>
              Entrenamiento y evaluación: ISIC 2020 Challenge Dataset
              (International Skin Imaging Collaboration), licencia CC-BY-NC 4.0,{" "}
              <a href={ISIC_DOI}>{ISIC_DOI.replace("https://doi.org/", "doi:")}</a>
              . Rotemberg et al., <em>Sci Data</em> 8, 34 (2021). Uso no
              comercial; las imágenes de ejemplo se reproducen con esa
              atribución.
            </li>
            <li>
              Evaluación externa: Diverse Dermatology Images (DDI, Stanford),
              acuerdo de uso académico; sus imágenes no se reproducen en esta
              interfaz ni en el repositorio.
            </li>
            <li>
              Tesis de licenciatura de Edgar Eduardo Ontiveros Lara:
              clasificador educativo de lesiones cutáneas para detección
              asistida de melanoma. Código MIT en <a href={REPO}>{REPO}</a>.
            </li>
          </ul>
        </section>

        <section aria-labelledby="s6">
          <h2 id="s6">Versión</h2>
          {info ? (
            <table>
              <tbody>
                <tr>
                  <th scope="row">Versión del modelo</th>
                  <td>
                    <code>{info.model_version}</code>
                    {info.manifest.kind === "test" &&
                      " (paquete de prueba con pesos aleatorios)"}
                  </td>
                </tr>
                {info.ensemble && info.manifest.members && (
                  <tr>
                    <th scope="row">Miembros</th>
                    <td>
                      {info.manifest.members.map((mb) => (
                        <div key={mb.run}>
                          <code>{mb.run}</code> ·{" "}
                          <code>{mb.checkpoint.sha256.slice(0, 12)}…</code>
                        </div>
                      ))}
                    </td>
                  </tr>
                )}
                <tr>
                  <th scope="row">Commit</th>
                  <td>
                    <a href={`${REPO}/commit/${info.manifest.git_sha}`}>
                      <code>{info.manifest.git_sha}</code>
                    </a>
                  </td>
                </tr>
                <tr>
                  <th scope="row">Exportado</th>
                  <td>{formatDateEs(info.manifest.date)}</td>
                </tr>
                <tr>
                  <th scope="row">Paquete</th>
                  <td>
                    <a
                      href={`${REPO}/releases/tag/model-${info.model_version}`}
                    >
                      release model-{info.model_version}
                    </a>
                    ; ONNX opset {info.manifest.onnx.opset["ai.onnx"]}, entrada{" "}
                    {info.preprocess.input_size} px.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Repositorio</th>
                  <td>
                    <a href={REPO}>{REPO}</a>
                  </td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="help">
              {state.loading ? "Cargando…" : "Ficha del modelo no disponible."}
            </p>
          )}
          <p className="thesis">
            <img
              src="/escudo-color.png"
              alt="Escudo de la Universidad Autónoma de Chihuahua"
              width={44}
              height={44}
            />
            <span>
              Proyecto de tesis de licenciatura — Edgar Eduardo Ontiveros Lara,
              matrícula a335951. Facultad de Ingeniería, Universidad Autónoma de
              Chihuahua, 2026.
            </span>
          </p>
        </section>
      </div>
    </>
  );
}
