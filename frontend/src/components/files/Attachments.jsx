import { Icon } from '../Icon';

/**
 * Renderuje listę załączników (FileResponse[]) wg pola `kind`:
 *  - image → miniatura w galerii (klik = pełny rozmiar)
 *  - video → odtwarzacz <video controls>
 *  - audio → <audio controls>
 *  - inne  → link „pobierz" (pdf/word itd.)
 *
 * URL-e to presigned linki MinIO ze świeżej odpowiedzi listy (endpoint
 * publiczny), więc działają w <img>/<video> bez nagłówka auth.
 */
export function Attachments({ files }) {
  if (!files || files.length === 0) return null;

  const images = files.filter((f) => f.kind === 'image');
  const videos = files.filter((f) => f.kind === 'video');
  const audios = files.filter((f) => f.kind === 'audio');
  const docs = files.filter(
    (f) => !['image', 'video', 'audio'].includes(f.kind),
  );

  return (
    <div className="attachments">
      {images.length > 0 && (
        <div className="attach-gallery">
          {images.map((f) => (
            <a
              key={f.id}
              href={f.url}
              target="_blank"
              rel="noreferrer"
              className="attach-thumb"
              title={f.original_name}
            >
              <img src={thumbUrl(f)} alt={f.original_name} loading="lazy" />
            </a>
          ))}
        </div>
      )}

      {videos.map((f) => (
        <video key={f.id} className="attach-media" controls preload="metadata" src={f.url}>
          <track kind="captions" />
        </video>
      ))}

      {audios.map((f) => (
        <audio key={f.id} className="attach-audio" controls preload="metadata" src={f.url} />
      ))}

      {docs.length > 0 && (
        <div className="attach-files">
          {docs.map((f) => (
            <a
              key={f.id}
              href={f.download_url || f.url}
              target="_blank"
              rel="noreferrer"
              className="attach-doc"
            >
              <Icon name="doc" size={14} />
              <span className="attach-name">{f.original_name}</span>
              <span className="mono dim">{formatSize(f.size_bytes)}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function thumbUrl(file) {
  return file.variants?.thumb?.url || file.variants?.small?.url || file.url;
}

function formatSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
