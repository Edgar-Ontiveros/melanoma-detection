const SITE = "https://edgar-ontiveros.com";

/** Atribución institucional (F7b.6/F7b.7): escudo de la UACH y logo de la Facultad de Ingeniería
 * en color, dos líneas de texto y el monograma EO· con sus colores. El nombre y el monograma
 * enlazan al sitio personal del autor (son enlaces, no peticiones del build). Se usa en el pie
 * (logos a 44 px) y en la ficha del modelo (72 px, vía `.thesis`). */
export default function Institution() {
  return (
    <p className="institution">
      <span className="logos">
        <img src="/escudo-uach.png" alt="Escudo de la Universidad Autónoma de Chihuahua" />
        <img src="/facultad-ingenieria.png" alt="Logo de la Facultad de Ingeniería" />
      </span>
      <span className="lines">
        <span className="author">
          <a href={SITE} target="_blank" rel="author noopener">
            Edgar Eduardo Ontiveros Lara · a335951
          </a>
        </span>
        <span className="affiliation">Facultad de Ingeniería · Universidad Autónoma de Chihuahua</span>
      </span>
      <a
        className="eo-link"
        href={SITE}
        target="_blank"
        rel="author noopener"
        aria-label="Sitio personal de Edgar Eduardo Ontiveros Lara"
      >
        <img className="eo" src="/eo.svg" alt="" />
      </a>
    </p>
  );
}
