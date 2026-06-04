import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  categoriesApi,
  commentsApi,
  postsApi,
  tagsApi,
} from '../api/resources';
import { qk } from '../query/keys';

/* ------------------------------------------------------------------ */
/* Kategorie                                                          */
/* ------------------------------------------------------------------ */
export function useCategories() {
  return useQuery({
    queryKey: qk.categories.all(),
    queryFn: categoriesApi.list,
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => categoriesApi.create(payload),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.categories.all() }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => categoriesApi.remove(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.categories.all() }),
  });
}

/* ------------------------------------------------------------------ */
/* Tagi                                                              */
/* ------------------------------------------------------------------ */
export function useTags() {
  return useQuery({ queryKey: qk.tags.all(), queryFn: tagsApi.list });
}

/* ------------------------------------------------------------------ */
/* Posty                                                            */
/* ------------------------------------------------------------------ */

/** Pojedyncza strona postów (np. na stronie głównej). */
export function usePosts(filters = {}) {
  return useQuery({
    queryKey: qk.posts.list(filters),
    queryFn: () => postsApi.list(filters),
  });
}

/** Lista z keyset-paginacją (przycisk „pokaż więcej”). */
export function useInfinitePosts(filters = {}) {
  return useInfiniteQuery({
    queryKey: qk.posts.list({ ...filters, infinite: true }),
    queryFn: ({ pageParam }) =>
      postsApi.list({ ...filters, cursor: pageParam ?? undefined }),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

export function usePost(id) {
  return useQuery({
    queryKey: qk.posts.detail(id),
    queryFn: () => postsApi.get(id),
    enabled: Boolean(id),
  });
}

export function useCreatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => postsApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.posts.all() }),
  });
}

export function useUpdatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => postsApi.update(id, payload),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: qk.posts.all() });
      if (updated?.id) {
        qc.invalidateQueries({ queryKey: qk.posts.detail(updated.id) });
      }
    },
  });
}

export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => postsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.posts.all() }),
  });
}

/* ------------------------------------------------------------------ */
/* Komentarze                                                       */
/* ------------------------------------------------------------------ */
export function useComments(postId) {
  return useQuery({
    queryKey: qk.comments.forPost(postId),
    queryFn: () => commentsApi.listForPost(postId),
    enabled: Boolean(postId),
  });
}

export function useAddComment(postId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => commentsApi.add(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.comments.forPost(postId) });
      // odśwież licznik komentarzy na liście/detalu posta
      qc.invalidateQueries({ queryKey: qk.posts.detail(postId) });
    },
  });
}

export function useUpdateComment(postId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => commentsApi.update(id, payload),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.comments.forPost(postId) }),
  });
}

export function useDeleteComment(postId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => commentsApi.remove(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.comments.forPost(postId) }),
  });
}
