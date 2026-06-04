/**
 * Składa płaską listę komentarzy (kolejność DFS z backendu) w drzewo.
 * Backend daje `parent_id` i `depth`, więc wystarczy mapowanie po id.
 * Kolejność wejściowa jest zachowana (DFS), więc dzieci trafiają do rodziców
 * w poprawnej kolejności.
 */
export function buildCommentTree(items = []) {
  const byId = new Map();
  const roots = [];

  for (const c of items) {
    byId.set(c.id, { ...c, children: [] });
  }
  for (const c of items) {
    const node = byId.get(c.id);
    if (c.parent_id && byId.has(c.parent_id)) {
      byId.get(c.parent_id).children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}
