import { recommendation } from "../lib/recommendation";

/** Tarjeta de recomendación. Texto fijo (F7); por encima del umbral, fondo con tinte del
 * acento; por debajo, superficie neutra. Sin números por encima del umbral. */
export default function Recommendation({ refer, npvTest }: { refer: boolean; npvTest: number | null }) {
  const r = recommendation({ refer, npvTest });
  return (
    <section className={`card rec${refer ? " refer" : ""}`} aria-labelledby="rec-title">
      <p id="rec-title" className="label">
        Recomendación
      </p>
      <p className="rec-headline">{r.headline}</p>
      <p className="rec-body">{r.body}</p>
    </section>
  );
}
