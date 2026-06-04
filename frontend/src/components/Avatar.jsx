import { useEffect, useState } from 'react';
import { initials } from '../utils/format';

/**
 * Awatar użytkownika. Próbuje obraz z publicznego `GET /users/{id}/avatar?variant=thumb`
 * (307 → MinIO); przy 404/błędzie pokazuje inicjały. Endpoint publiczny, więc
 * <img> działa bez nagłówka auth. `version` busta cache po zmianie awatara.
 */
export function Avatar({ userId, username, size = 'md', version = 0, className = '' }) {
  const [failed, setFailed] = useState(false);
  // po zmianie awatara (version) spróbuj załadować ponownie
  useEffect(() => setFailed(false), [version]);

  const showImg = userId && !failed;
  const cls = `av av-${size} ${className}`.trim();

  if (showImg) {
    const v = version ? `&v=${version}` : '';
    return (
      <span className={cls}>
        <img
          src={`/api/v1/users/${userId}/avatar?variant=thumb${v}`}
          alt={username ?? ''}
          className="av-img"
          onError={() => setFailed(true)}
          loading="lazy"
        />
      </span>
    );
  }
  return <span className={cls}>{initials(username)}</span>;
}
