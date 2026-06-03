import { useMemo } from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

/**
 * Bezpieczny rendering treści posta/komentarza.
 *
 * `html: true` pozwala osadzać media, których markdown nie ma natywnie
 * (np. <video>, <u>) — całość jest potem sanityzowana przez DOMPurify, więc
 * mimo włączonego HTML nie ma ryzyka XSS. Backend i tak przechowuje treść jako
 * markdown (content_format), a nie HTML.
 */
const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
});

// Dozwolone tagi/atrybuty media (DOMPurify domyślnie zna img/video/audio/source,
// ale jawnie dopisujemy atrybuty kontrolek/wymiarów dla pewności).
const PURIFY_CONFIG = {
  ADD_TAGS: ['video', 'audio', 'source'],
  ADD_ATTR: ['controls', 'src', 'type', 'poster', 'width', 'height', 'target', 'rel'],
  // żadnych iframe / script / event-handlerów — DOMPurify usuwa je domyślnie
};

// Linki zawsze otwieramy w nowej karcie i z rel=noopener.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

export function Markdown({ source, format = 'markdown', className = '' }) {
  const html = useMemo(() => {
    if (!source) return '';
    if (format === 'plain') {
      const escaped = source
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br/>');
      return DOMPurify.sanitize(escaped, PURIFY_CONFIG);
    }
    return DOMPurify.sanitize(md.render(source), PURIFY_CONFIG);
  }, [source, format]);

  return (
    <div
      className={`md ${className}`}
      // treść sanityzowana powyżej
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
