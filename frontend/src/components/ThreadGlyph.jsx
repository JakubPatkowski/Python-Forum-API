import { useEffect, useState } from 'react';
import { CategoryGlyph } from './CategoryGlyph';

/**
 * Ikona wątku. Kolejność fallbacków:
 *   1. własna ikona wątku: GET /posts/{id}/icon?variant=thumb (307 → MinIO),
 *   2. ikona kategorii wątku (CategoryGlyph),
 *   3. neutralny placeholder „···".
 * Endpoint jest publiczny (jak posty). `version` busta cache po zmianie ikony.
 */
export function ThreadGlyph({ postId, category, name, version = 0 }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [version, postId]);

  if (postId && !failed) {
    const v = version ? `&v=${version}` : '';
    return (
      <div className="cat-glyph cat-glyph-img">
        <img
          src={`/api/v1/posts/${postId}/icon?variant=thumb${v}`}
          alt={name || 'icon'}
          onError={() => setFailed(true)}
          loading="lazy"
        />
      </div>
    );
  }

  if (category) {
    return (
      <CategoryGlyph
        categoryId={category.public_id}
        name={category.name}
      />
    );
  }
  return <div className="cat-glyph">···</div>;
}
