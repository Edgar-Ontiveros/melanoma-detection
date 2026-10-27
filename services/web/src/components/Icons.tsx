/** Íconos propios, inline SVG de trazo (1.5 px, currentColor). Sin marcas ajenas ni recursos
 * externos. El símbolo «lente» es el mismo dibujo que public/mark.svg (F7b.3). */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Símbolo «lente»: anillo y punto descentrado. */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" focusable="false">
      <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="19.5" cy="19.5" r="4" fill="currentColor" />
    </svg>
  );
}

/** Flecha hacia arriba (zona de carga). */
export function UploadIcon({ size = 20, strokeWidth = 1.5 }: { size?: number; strokeWidth?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" focusable="false">
      <path d="M10 16V4m0 0-5 5m5-5 5 5" {...stroke} strokeWidth={strokeWidth} />
    </svg>
  );
}

/** Chevron hacia la derecha (detalles plegados). */
export function ChevronIcon({ size = 16 }: { size?: number }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} aria-hidden="true" focusable="false">
      <path d="M6 3l5 5-5 5" {...stroke} />
    </svg>
  );
}

/** Círculo con una i (avisos y errores). */
export function InfoIcon({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" focusable="false">
      <circle cx="10" cy="10" r="8" {...stroke} />
      <path d="M10 9v5M10 6.5v.5" {...stroke} />
    </svg>
  );
}
