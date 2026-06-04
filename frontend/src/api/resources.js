import { api } from './client';

/**
 * Cienkie funkcje 1:1 do endpointów backendu (/api/v1/*). Zwracają już
 * `res.data`. Tu NIE ma logiki cache'owania — tym zajmuje się React Query
 * (patrz hooks/). Dzięki temu łatwo je testować i ponownie używać.
 */

// --- auth ------------------------------------------------------------------ //
export const authApi = {
  register: (payload) =>
    api.post('/auth/register', payload).then((r) => r.data),
  // backend przyjmuje { login, password }; login = username albo email
  login: (payload) => api.post('/auth/login', payload).then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  logoutAll: () => api.post('/auth/logout-all').then((r) => r.data),
  me: () => api.get('/users/me').then((r) => r.data),
  userById: (id) => api.get(`/users/${id}`).then((r) => r.data),
};

// --- admin (zarządzanie userami) ------------------------------------------- //
export const adminApi = {
  listUsers: (params = {}) =>
    api.get('/admin/users', { params }).then((r) => r.data),
  assignRole: (userId, role) =>
    api.post(`/admin/users/${userId}/roles`, { role }).then((r) => r.data),
  revokeRole: (userId, role) =>
    api.delete(`/admin/users/${userId}/roles/${role}`).then((r) => r.data),
  // backend: { permission, granted } (granted=false => deny override)
  grantPermission: (userId, permission, granted) =>
    api
      .post(`/admin/users/${userId}/permissions`, { permission, granted })
      .then((r) => r.data),
  // backend: { blocked } (blocked=true => konto zablokowane)
  setStatus: (userId, blocked) =>
    api
      .patch(`/admin/users/${userId}/status`, { blocked })
      .then((r) => r.data),
};

// --- categories ------------------------------------------------------------ //
export const categoriesApi = {
  list: () => api.get('/categories').then((r) => r.data),
  create: (payload) => api.post('/categories', payload).then((r) => r.data),
  remove: (id) => api.delete(`/categories/${id}`).then((r) => r.data),
};

// --- tags ------------------------------------------------------------------ //
export const tagsApi = {
  list: () => api.get('/tags').then((r) => r.data),
  create: (name) => api.post('/tags', { name }).then((r) => r.data),
};

// --- posts ----------------------------------------------------------------- //
export const postsApi = {
  // params: { cursor, limit, category_id, tag, author_id }
  list: (params = {}) =>
    api.get('/posts', { params }).then((r) => r.data),
  get: (id) => api.get(`/posts/${id}`).then((r) => r.data),
  create: (payload) => api.post('/posts', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/posts/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/posts/${id}`).then((r) => r.data),
};

// --- files ----------------------------------------------------------------- //
export const filesApi = {
  // Upload „proxied” przez backend (multipart). Pewniejszy w dev niż presigned
  // PUT prosto do MinIO (ten wymaga CORS po stronie MinIO).
  uploadDirect: (file, onProgress) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post('/files', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
        },
      })
      .then((r) => r.data);
  },
  get: (id) => api.get(`/files/${id}`).then((r) => r.data),
  remove: (id) => api.delete(`/files/${id}`).then((r) => r.data),
  // Listy załączników są publiczne (presigned URL-e w odpowiedzi).
  listForPost: (postId) =>
    api.get(`/posts/${postId}/files`).then((r) => r.data),
  listForComment: (commentId) =>
    api.get(`/comments/${commentId}/files`).then((r) => r.data),
  attachToPost: (postId, fileIds) =>
    api.post(`/posts/${postId}/files`, { file_ids: fileIds }).then((r) => r.data),
  attachToComment: (commentId, fileIds) =>
    api
      .post(`/comments/${commentId}/files`, { file_ids: fileIds })
      .then((r) => r.data),
  setAvatar: (file) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post('/users/me/avatar', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  setCategoryImage: (categoryId, file) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post(`/categories/${categoryId}/image`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  // Ikona wątku (osobny endpoint, owner_type=post_icon na backendzie).
  setPostIcon: (postId, file) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post(`/posts/${postId}/icon`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
};

// --- engagement (polubienia + statystyki) ---------------------------------- //
export const engagementApi = {
  // target: 'posts' | 'comments'
  likeState: (target, publicId) =>
    api.get(`/${target}/${publicId}/likes`).then((r) => r.data),
  like: (target, publicId) =>
    api.post(`/${target}/${publicId}/like`).then((r) => r.data),
  unlike: (target, publicId) =>
    api.delete(`/${target}/${publicId}/like`).then((r) => r.data),
  userStats: (userId) =>
    api.get(`/users/${userId}/stats`).then((r) => r.data),
  // Najczęściej polubiony wątek (opcjonalnie w obrębie kategorii).
  featuredPost: (categoryId) =>
    api
      .get('/featured-post', { params: categoryId ? { category_id: categoryId } : {} })
      .then((r) => r.data),
};

// --- comments -------------------------------------------------------------- //
export const commentsApi = {
  // płaska lista w kolejności DFS (frontend składa drzewo po `path`/`parent_id`)
  listForPost: (postId) =>
    api.get('/comments', { params: { post_id: postId } }).then((r) => r.data),
  add: (payload) => api.post('/comments', payload).then((r) => r.data),
  update: (id, payload) =>
    api.put(`/comments/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/comments/${id}`).then((r) => r.data),
};
