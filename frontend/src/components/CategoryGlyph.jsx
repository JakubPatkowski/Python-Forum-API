import { useEffect, useState } from 'react';
import { categoryGlyph } from '../utils/format';

/**
 * „Glyph"/ikona kategorii: próbuje obraz z publicznego
 * `GET /categories/{id}/image?variant=thumb` (307 → MinIO); przy braku/błędzie
 * pokazuje 3-literowy kod z nazwy. Bez auth (endpoint publiczny). `version`
 * busta cache po zmianie obrazka.
 */
export function CategoryGlyph({ categoryId, name, version = 0 }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [version]);

  if (categoryId && !failed) {
    const v = version ? `&v=${version}` : '';
    return (
      <div className="cat-glyph cat-glyph-img">
        <img
          src={`/api/v1/categories/${categoryId}/image?variant=thumb${v}`}
          alt={name}
          onError={() => setFailed(true)}
          loading="lazy"
        />
      </div>
    );
  }
  return <div className="cat-glyph">{categoryGlyph(name)}</div>;
}
