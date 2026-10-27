import Institution from "./Institution";

export default function Footer({ onModel }: { onModel: (e: React.MouseEvent) => void }) {
  return (
    <footer className="bottom">
      <div className="container">
        <p className="legal">
          Apoyo a la decisión de referir lesiones con sospecha de melanoma en dermatoscopía, con
          fines educativos. No es un diagnóstico, no detecta otros cánceres de piel, no sustituye a
          un dermatólogo y no tiene aprobación regulatoria. Las imágenes no se almacenan.{" "}
          <a href="/modelo" onClick={onModel}>
            Ficha del modelo
          </a>
          .
        </p>
        <Institution />
      </div>
    </footer>
  );
}
