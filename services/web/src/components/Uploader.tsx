import { useId, useRef, useState } from "react";

import { UploadIcon } from "./Icons";

const ACCEPT = "image/jpeg,image/png,image/webp";

/** Zona de arrastrar o seleccionar archivo (F7b.7): toda la tarjeta es clicable y accesible por
 * teclado; el input nativo va oculto. No valida nada del modelo: la API decide. */
export default function Uploader({
  onFile,
  disabled,
}: {
  onFile: (file: File) => void;
  disabled: boolean;
}) {
  const [active, setActive] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();

  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) onFile(f);
  };
  const open = () => {
    if (!disabled) input.current?.click();
  };

  return (
    <div
      className={`dropzone${active ? " active" : ""}${disabled ? " disabled" : ""}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Subir una dermatoscopía: arrastre un archivo o presione para seleccionarlo"
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setActive(true);
      }}
      onDragLeave={() => setActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setActive(false);
        if (!disabled) pick(e.dataTransfer.files);
      }}
    >
      <span className="circle" aria-hidden="true">
        <UploadIcon size={32} strokeWidth={1.75} />
      </span>
      <p className="lead">Arrastre una dermatoscopía aquí</p>
      <p className="hint">o seleccione un archivo · JPEG, PNG o WebP · hasta 10 MB</p>
      <button
        type="button"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          open();
        }}
      >
        Seleccionar archivo
      </button>
      <p className="note">Puede ser la foto original sin recortar. La imagen se analiza y no se almacena.</p>
      <input
        id={id}
        ref={input}
        type="file"
        accept={ACCEPT}
        disabled={disabled}
        tabIndex={-1}
        aria-hidden="true"
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
