// Texto de la recomendación de priorización (F7.2). Por encima del umbral el texto es fijo y sin
// números; por debajo, el «1 de cada N» se interpola desde el VPN de /model-info (metrics).
// Nada aquí conoce el umbral ni la prevalencia: si falta el VPN, se dice «n/d» en vez de inventar.

import { oneInN } from "./format";

export interface RecommendationInput {
  refer: boolean;
  /** valor predictivo negativo en τ95 (metrics.tau_95.npv), para «1 de cada N» */
  npvTest: number | null;
}

export interface Recommendation {
  headline: string;
  body: string;
  refer: boolean;
}

export function recommendation(input: RecommendationInput): Recommendation {
  if (input.refer) {
    return {
      refer: true,
      headline: "Referir a dermatología.",
      body: "Una referencia no es un diagnóstico.",
    };
  }
  const missRate = input.npvTest === null ? null : 1 - input.npvTest;
  const oneIn = missRate === null ? "n/d" : oneInN(missRate);
  return {
    refer: false,
    headline: "Por debajo del umbral de referencia.",
    body:
      `Aproximadamente ${oneIn} lesiones en este grupo es melanoma. ` +
      "Ante duda clínica, referir de todos modos.",
  };
}
