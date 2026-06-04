import { useRef, useState } from 'react';
import { useTranslation } from '../../i18n/LangContext';
import { Icon } from '../Icon';
import { filesApi } from '../../api/resources';

/**
 * Wybór i upload plików (proxied POST /files). Każdy plik leci od razu po
 * wybraniu; rodzic dostaje przez `onChange` listę już wgranych FileResponse
 * (z `id`), które potem podpina do posta/komentarza.
 *
 * Stan uploadu (uploading/done/error) trzymany lokalnie, żeby pokazać postęp.
 */
export function FileUploader({ onChange, disabled = false }) {
  const t = useTranslation();
  const inputRef = useRef(null);
  const [items, setItems] = useState([]); // {localId, name, status, progress, file?}

  const emitUploaded = (next) => {
    const uploaded = next.filter((i) => i.status === 'done' && i.file).map((i) => i.file);
    if (onChange) onChange(uploaded);
  };

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList);
    for (const f of files) {
      const localId = `${f.name}-${Date.now()}-${Math.random()}`;
      setItems((prev) => [
        ...prev,
        { localId, name: f.name, status: 'uploading', progress: 0 },
      ]);
      try {
        const resp = await filesApi.uploadDirect(f, (p) =>
          setItems((prev) =>
            prev.map((i) => (i.localId === localId ? { ...i, progress: p } : i)),
          ),
        );
        setItems((prev) => {
          const next = prev.map((i) =>
            i.localId === localId ? { ...i, status: 'done', file: resp } : i,
          );
          emitUploaded(next);
          return next;
        });
      } catch (err) {
        setItems((prev) =>
          prev.map((i) =>
            i.localId === localId
              ? { ...i, status: 'error', error: err?.message ?? 'error' }
              : i,
          ),
        );
      }
    }
  };

  const removeItem = (localId) => {
    setItems((prev) => {
      const target = prev.find((i) => i.localId === localId);
      // jeśli plik był już wgrany ale nie został podpięty — usuń go z backendu
      // (sprzątanie „sierot"), bez blokowania UI na wyniku
      if (target?.status === 'done' && target.file?.id) {
        filesApi.remove(target.file.id).catch(() => {});
      }
      const next = prev.filter((i) => i.localId !== localId);
      emitUploaded(next);
      return next;
    });
  };

  return (
    <div className="uploader">
      <button
        type="button"
        className="btn"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
      >
        <Icon name="plus" size={12} /> {t.files.add}
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = '';
        }}
      />

      {items.length > 0 && (
        <ul className="upload-list">
          {items.map((i) => (
            <li key={i.localId} className={`upload-item ${i.status}`}>
              <span className="upload-name">{i.name}</span>
              {i.status === 'uploading' && (
                <span className="mono dim">{i.progress}%</span>
              )}
              {i.status === 'done' && <span className="mono ok">✓</span>}
              {i.status === 'error' && (
                <span className="mono" style={{ color: 'var(--bad)' }} title={i.error}>
                  {i.error || t.files.uploadError}
                </span>
              )}
              <button
                type="button"
                className="link-btn danger"
                onClick={() => removeItem(i.localId)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
