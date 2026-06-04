/**
 * Fabryka kluczy zapytań React Query.
 *
 * Jedno miejsce na wszystkie klucze => spójna inwalidacja. To jest też punkt
 * zaczepienia pod WebSocket: gdy w przyszłości przyjdzie wiadomość typu
 * "post <id> zaktualizowany", wystarczy:
 *     queryClient.invalidateQueries({ queryKey: qk.posts.detail(id) })
 * i widok sam pobierze świeże dane (GET) — dokładnie model, który opisałeś.
 */
export const qk = {
  auth: {
    me: () => ['auth', 'me'],
  },
  categories: {
    all: () => ['categories'],
  },
  tags: {
    all: () => ['tags'],
  },
  posts: {
    all: () => ['posts'],
    list: (filters = {}) => ['posts', 'list', filters],
    detail: (id) => ['posts', 'detail', id],
  },
  comments: {
    forPost: (postId) => ['comments', 'post', postId],
  },
  files: {
    forPost: (postId) => ['files', 'post', postId],
    forComment: (commentId) => ['files', 'comment', commentId],
    mine: () => ['files', 'mine'],
  },
  users: {
    detail: (id) => ['users', id],
    stats: (id) => ['users', id, 'stats'],
  },
  likes: {
    // target: 'posts' | 'comments'
    state: (target, id) => ['likes', target, id],
  },
  featured: {
    // categoryId | null
    post: (categoryId = null) => ['featured', 'post', categoryId],
  },
};
