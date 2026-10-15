import { describe, expect, it } from "vitest";

import { recommendation } from "./recommendation";

const test = { npvTest: 0.9986462093862816 };

describe("recommendation", () => {
  it("por encima del umbral: texto fijo, sin números", () => {
    const r = recommendation({ refer: true, ...test });
    expect(r.refer).toBe(true);
    expect(r.headline).toBe("Referir a dermatología.");
    expect(r.body).toBe("Una referencia no es un diagnóstico.");
    expect(r.body).not.toMatch(/\d/);
  });

  it("por debajo del umbral: 1 de cada N desde el VPN", () => {
    const r = recommendation({ refer: false, ...test });
    expect(r.refer).toBe(false);
    expect(r.headline).toBe("Por debajo del umbral de referencia.");
    expect(r.body).toBe(
      "Aproximadamente 1 de cada 750 lesiones en este grupo es melanoma. Ante duda clínica, referir de todos modos.",
    );
  });

  it("sin métricas no inventa números", () => {
    expect(recommendation({ refer: true, npvTest: null }).body).toBe("Una referencia no es un diagnóstico.");
    const below = recommendation({ refer: false, npvTest: null });
    expect(below.body).toContain("Aproximadamente n/d lesiones");
  });
});
