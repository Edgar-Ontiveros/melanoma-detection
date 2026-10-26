import type { PredictResponse } from "../api";

import { ChevronIcon } from "./Icons";

/** Detalles técnicos, plegados: versión, latencia, dimensiones de entrada, estado del mapa y
 * el JSON completo (sin las imágenes en base64, que se resumen). */
export default function Details({ result }: { result: PredictResponse }) {
  const compact = {
    ...result,
    cam: {
      ...result.cam,
      png_base64: result.cam.png_base64 ? `<${result.cam.png_base64.length} caracteres base64>` : null,
      crop_png_base64: `<${result.cam.crop_png_base64.length} caracteres base64>`,
    },
  };
  return (
    <details className="tech">
      <summary>
        <ChevronIcon />
        Detalles técnicos
      </summary>
      <div className="body">
        <dl className="defs">
          <dt>Versión del modelo</dt>
          <dd>
            <code>{result.model_version}</code>
          </dd>
          <dt>Latencia en el servidor</dt>
          <dd className="num">{result.latency_ms.toFixed(0)} ms</dd>
          <dt>Imagen recibida</dt>
          <dd className="num">
            {result.input.width} × {result.input.height} px, {result.input.format}
          </dd>
          <dt>Estado del mapa</dt>
          <dd>
            <code>{result.cam.status}</code>
          </dd>
        </dl>
        <pre>{JSON.stringify(compact, null, 2)}</pre>
      </div>
    </details>
  );
}
