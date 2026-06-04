/** Względny czas „X temu” — lekki, bez zależności. */
export function timeAgo(iso, lang = 'pl') {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const sec = Math.max(1, Math.floor((Date.now() - then) / 1000));

  const units = [
    [60, 's', 's'],
    [60, 'min', 'min'],
    [24, 'godz', 'h'],
    [7, 'd', 'd'],
    [4.345, 'tyg', 'w'],
    [12, 'mc', 'mo'],
    [Number.POSITIVE_INFINITY, 'lat', 'y'],
  ];

  let value = sec;
  let i = 0;
  while (i < units.length - 1 && value >= units[i][0]) {
    value = Math.floor(value / units[i][0]);
    i += 1;
  }
  const label = lang === 'en' ? units[i][2] : units[i][1];
  return `${value} ${label}`;
}

/** Inicjały z nazwy użytkownika do awatara. */
export function initials(name) {
  if (!name) return '??';
  return name.slice(0, 2).toUpperCase();
}

/**
 * Zwięzły fragment treści. Usuwa składnię markdown tak, by nie pokazywać
 * „surowych" obrazów/linków w podglądzie:
 *  - obrazy ![alt](url)            → znikają całkowicie (nie da się przewidzieć,
 *                                     czy wątek zaczyna się od zdjęcia),
 *  - linki [tekst](url)            → zostaje sam tekst,
 *  - gołe URL-e i pozostałe znaki  → wycinane.
 */
export function excerptOf(text, max = 200) {
  if (!text) return '';
  const plain = text
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ') // obrazy markdown
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // linki → tekst
    .replace(/!\[[^\]]*\]/g, ' ') // niedomknięte ![...]
    .replace(/https?:\/\/\S+/g, ' ') // gołe URL-e
    .replace(/[#*_`>~]/g, '') // pozostałe znaczniki inline/blokowe
    .replace(/\s+/g, ' ')
    .trim();
  return plain.length > max ? `${plain.slice(0, max)}…` : plain;
}

/** Krótki kod kategorii (3 litery) z nazwy — na potrzeby designu „glyph”. */
export function categoryGlyph(name) {
  if (!name) return '···';
  return name.replace(/[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]/g, '').slice(0, 3).toUpperCase() || '···';
}
