import { formatPercent, formatRatio, logPosition } from "../lib/format";

/** Tarjeta de probabilidad: número en grande, razón contra la tasa base, barra logarítmica de
 * 0,1 % a 100 % con dos marcas (umbral: línea sólida; tasa base: línea discontinua). Un solo
 * color; nada de semáforo. Todos los valores vienen de la API. */
export default function ProbabilityBlock({
  probability,
  threshold,
  prevalence,
}: {
  probability: number;
  threshold: number;
  prevalence: number | null;
}) {
  const pos = logPosition(probability) * 100;
  const ratio = prevalence !== null ? formatRatio(probability, prevalence) : null;
  return (
    <section className="card" aria-labelledby="prob-title">
      <p id="prob-title" className="label">
        Probabilidad calibrada
      </p>
      <div className="prob-row">
        <p className="prob-big" aria-live="polite">
          {formatPercent(probability)}
        </p>
        <p className="prob-line">
          {prevalence !== null && ratio !== null
            ? ratio === "1,0"
              ? `igual a la tasa base (${formatPercent(prevalence)})`
              : `${ratio} veces la tasa base (${formatPercent(prevalence)})`
            : "tasa base no disponible"}
        </p>
      </div>
      <div
        className="logbar"
        role="img"
        aria-label={`Barra logarítmica de 0,1 % a 100 %: probabilidad ${formatPercent(probability)}, umbral ${formatPercent(threshold, 2)}${
          prevalence !== null ? `, tasa base ${formatPercent(prevalence)}` : ""
        }`}
      >
        <div className="fill" style={{ width: `${pos}%` }} />
        {prevalence !== null && (
          <>
            <div className="mark dashed" style={{ left: `${logPosition(prevalence) * 100}%` }} />
            <div className="mark-label" style={{ left: `${logPosition(prevalence) * 100}%` }}>
              tasa base
            </div>
          </>
        )}
        <div className="mark" style={{ left: `${logPosition(threshold) * 100}%` }} />
        <div className="mark-label below" style={{ left: `${logPosition(threshold) * 100}%` }}>
          umbral
        </div>
        <span className="axis first" style={{ left: 0 }}>
          0,1 %
        </span>
        <span className="axis last" style={{ left: "100%" }}>
          100 %
        </span>
      </div>
      <p className="scale-note">Escala logarítmica. De cada 100 lesiones con esta puntuación en validación, esta es la cantidad que resultó melanoma.</p>
    </section>
  );
}
