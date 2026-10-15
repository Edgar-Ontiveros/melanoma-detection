import { recommendation } from "../lib/recommendation";

/** Bloque 2: recomendación de priorización. Texto fijo; por debajo del umbral, «1 de cada N» desde
 * el VPN del test (/model-info). */
export default function Recommendation({ refer, npvTest }: { refer: boolean; npvTest: number | null }) {
  const r = recommendation({ refer, npvTest });
  return (
    <section className="card" aria-labelledby="rec-title">
      <h2 id="rec-title" className="block-title">
        2 · Recomendación de priorización
      </h2>
      <p className="rec-headline">{r.headline}</p>
      <p>{r.body}</p>
    </section>
  );
}
