import { useId, useState } from "react";

import type { CamOut } from "../api";

const LABEL =
  "Muestra dónde el modelo encontró evidencia a favor de melanoma. No muestra qué evaluó para descartarla. Resolución: 7 × 7 celdas sobre el recorte; es una limitación del método.";

/** Mapa de activación: el recorte de 224 px que vio el modelo con el CAM superpuesto, chip con
 * el nombre, control de opacidad y vista sin mapa. Si no hay evidencia positiva: solo el recorte
 * y el texto. Nunca un mapa uniforme. */
export default function CamViewer({ cam }: { cam: CamOut }) {
  const [opacity, setOpacity] = useState(1);
  const [showMap, setShowMap] = useState(true);
  const sliderId = useId();
  const crop = `data:image/png;base64,${cam.crop_png_base64}`;
  const hasMap = cam.status === "ok" && cam.png_base64 !== null;

  return (
    <section className="card" aria-labelledby="cam-title">
      <p id="cam-title" className="label">
        Mapa de activación
      </p>
      <div className="cam-img">
        <span className="chip">Mapa de activación · recorte de 224 px</span>
        <img src={crop} alt="Recorte de 224 por 224 píxeles que evaluó el modelo" />
        {hasMap && showMap && (
          <img
            src={`data:image/png;base64,${cam.png_base64}`}
            alt="Mapa de activación de clase superpuesto sobre el recorte"
            style={{ opacity }}
          />
        )}
      </div>
      {hasMap ? (
        <div className="cam-controls">
          <label htmlFor={sliderId}>Opacidad {Math.round(opacity * 100)} %</label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={100}
            value={Math.round(opacity * 100)}
            onChange={(e) => setOpacity(Number(e.target.value) / 100)}
            disabled={!showMap}
          />
          <button type="button" className="secondary sm" onClick={() => setShowMap((v) => !v)}>
            {showMap ? "Ver sin mapa" : "Ver el mapa"}
          </button>
        </div>
      ) : (
        <p className="small">
          <strong>El modelo no encontró evidencia positiva en esta imagen.</strong> Se muestra el recorte sin mapa.
        </p>
      )}
      <p className="help">{LABEL}</p>
    </section>
  );
}
