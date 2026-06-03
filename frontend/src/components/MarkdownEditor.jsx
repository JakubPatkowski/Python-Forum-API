import { useRef, useState } from 'react';
import { useTranslation } from '../i18n/LangContext';
import { Markdown } from './Markdown';
import { filesApi } from '../api/resources';

/**
 * Edytor treści z paskiem narzędzi. Backend przechowuje markdown
 * (content_format='markdown'), więc przyciski wstawiają składnię markdown,
 * a dla rzeczy spoza markdowna (podkreślenie, wideo) — bezpieczny HTML, który
 * przy renderze sanityzuje DOMPurify.
 *
 * Wstawianie obrazu/wideo uploaduje plik (proxied POST /files) i wkleja jego
 * presigned URL w treść. (Uwaga: presigned URL ma TTL — dla trwałych mediów
 * lepiej trzymać je też jako załącznik; to robimy osobno.)
 */
export function MarkdownEditor({ value, onChange, placeholder, rows = 8 }) {
  const t = useTranslation();
  const taRef = useRef(null);
  const imgInputRef = useRef(null);
  const vidInputRef = useRef(null);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);

  // Owija zaznaczenie znacznikami before/after; jeśli nic nie zaznaczono,
  // wstawia placeholder.
  const wrap = (before, after = before, placeholderText = '') => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = value.slice(start, end) || placeholderText;
    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      ta.focus();
      ta.selectionStart = start + before.length;
      ta.selectionEnd = start + before.length + selected.length;
    });
  };

  // Dodaje prefiks na początku każdej zaznaczonej linii (listy, cytat, nagłówek).
  const linePrefix = (prefix) => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    const block = value.slice(lineStart, end);
    const prefixed = block
      .split('\n')
      .map((l, i) => (typeof prefix === 'function' ? prefix(l, i) : prefix + l))
      .join('\n');
    const next = value.slice(0, lineStart) + prefixed + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => ta.focus());
  };

  const insertAtCursor = (text) => {
    const ta = taRef.current;
    const pos = ta ? ta.selectionStart : value.length;
    const next = value.slice(0, pos) + text + value.slice(pos);
    onChange(next);
    requestAnimationFrame(() => ta?.focus());
  };

  const uploadAndInsert = async (file, asVideo) => {
    setBusy(true);
    try {
      const resp = await filesApi.uploadDirect(file);
      if (asVideo || resp.kind === 'video') {
        insertAtCursor(`\n<video controls src="${resp.url}"></video>\n`);
      } else {
        insertAtCursor(`\n![${resp.original_name}](${resp.url})\n`);
      }
    } catch (err) {
      insertAtCursor(`\n<!-- ${t.files.uploadError}: ${err?.message ?? ''} -->\n`);
    } finally {
      setBusy(false);
    }
  };

  const tools = [
    { label: 'B', title: t.editor.bold, cls: 'tb-b', run: () => wrap('**', '**', t.editor.boldText) },
    { label: 'I', title: t.editor.italic, cls: 'tb-i', run: () => wrap('*', '*', t.editor.italicText) },
    { label: 'U', title: t.editor.underline, cls: 'tb-u', run: () => wrap('<u>', '</u>', t.editor.underlineText) },
    { label: 'S', title: t.editor.strike, cls: 'tb-s', run: () => wrap('~~', '~~', t.editor.strikeText) },
    { label: 'H', title: t.editor.heading, run: () => linePrefix('## ') },
    { label: '•', title: t.editor.list, run: () => linePrefix('- ') },
    { label: '1.', title: t.editor.olist, run: () => linePrefix((l, i) => `${i + 1}. ${l}`) },
    { label: '❝', title: t.editor.quote, run: () => linePrefix('> ') },
    { label: '</>', title: t.editor.code, run: () => wrap('`', '`', 'code') },
    { label: '🔗', title: t.editor.link, run: () => wrap('[', '](https://)', t.editor.linkText) },
  ];

  return (
    <div className="mde">
      <div className="mde-toolbar">
        {tools.map((tool) => (
          <button
            key={tool.title}
            type="button"
            className={`mde-btn ${tool.cls ?? ''}`}
            title={tool.title}
            onClick={tool.run}
          >
            {tool.label}
          </button>
        ))}
        <button
          type="button"
          className="mde-btn"
          title={t.editor.image}
          onClick={() => imgInputRef.current?.click()}
          disabled={busy}
        >
          🖼
        </button>
        <button
          type="button"
          className="mde-btn"
          title={t.editor.video}
          onClick={() => vidInputRef.current?.click()}
          disabled={busy}
        >
          🎬
        </button>
        <span className="filler" />
        {busy && <span className="mono dim">{t.editor.uploading}</span>}
        <button
          type="button"
          className={`mde-btn ${preview ? 'on' : ''}`}
          title={t.editor.preview}
          onClick={() => setPreview((v) => !v)}
        >
          {t.editor.preview}
        </button>
      </div>

      {preview ? (
        <div className="mde-preview">
          {value.trim() ? (
            <Markdown source={value} />
          ) : (
            <span className="mono mute">{t.common.empty}</span>
          )}
        </div>
      ) : (
        <textarea
          ref={taRef}
          className="mde-textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={rows}
        />
      )}

      <input
        ref={imgInputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = '';
          if (f) uploadAndInsert(f, false);
        }}
      />
      <input
        ref={vidInputRef}
        type="file"
        accept="video/*"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = '';
          if (f) uploadAndInsert(f, true);
        }}
      />
    </div>
  );
}
