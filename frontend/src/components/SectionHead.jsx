/**
 * Nagłówek sekcji: tytuł + meta po prawej + linia + opcjonalna akcja.
 */
export function SectionHead({ title, meta, right }) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      {meta && <span className="meta">{meta}</span>}
      <span className="line" />
      {right}
    </div>
  );
}
