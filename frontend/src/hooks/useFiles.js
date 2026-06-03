import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { filesApi } from '../api/resources';
import { qk } from '../query/keys';

/** Załączniki posta (publiczny GET, presigned URL-e). */
export function usePostFiles(postId) {
  return useQuery({
    queryKey: qk.files.forPost(postId),
    queryFn: () => filesApi.listForPost(postId),
    enabled: Boolean(postId),
  });
}

/** Załączniki komentarza — pobierane leniwie (enabled), żeby nie strzelać N razy. */
export function useCommentFiles(commentId, enabled = true) {
  return useQuery({
    queryKey: qk.files.forComment(commentId),
    queryFn: () => filesApi.listForComment(commentId),
    enabled: Boolean(commentId) && enabled,
  });
}

/** Upload jednego pliku (proxied). Zwraca FileResponse z `id`. */
export function useUploadFile() {
  return useMutation({
    mutationFn: ({ file, onProgress }) => filesApi.uploadDirect(file, onProgress),
  });
}

export function useAttachToPost(postId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileIds) => filesApi.attachToPost(postId, fileIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.files.forPost(postId) }),
  });
}

export function useAttachToComment(commentId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileIds) => filesApi.attachToComment(commentId, fileIds),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.files.forComment(commentId) }),
  });
}

export function useSetAvatar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file) => filesApi.setAvatar(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.auth.me() }),
  });
}

export function useSetCategoryImage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ categoryId, file }) =>
      filesApi.setCategoryImage(categoryId, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.categories.all() }),
  });
}

/** Ustawia ikonę wątku. Po sukcesie odświeża listy/detal posta. */
export function useSetPostIcon() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, file }) => filesApi.setPostIcon(postId, file),
    onSuccess: (_data, { postId }) => {
      qc.invalidateQueries({ queryKey: qk.posts.all() });
      qc.invalidateQueries({ queryKey: qk.posts.detail(postId) });
    },
  });
}

/** Usunięcie pliku (uploader / file.delete.any) — sprzątanie sierot. */
export function useDeleteFile() {
  return useMutation({ mutationFn: (id) => filesApi.remove(id) });
}
