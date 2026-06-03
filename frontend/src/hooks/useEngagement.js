import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { engagementApi } from '../api/resources';
import { qk } from '../query/keys';

/**
 * Stan polubienia (count + liked) dla posta/komentarza. Pobierany leniwie.
 * target: 'posts' | 'comments'.
 */
export function useLikeState(target, publicId, enabled = true) {
  return useQuery({
    queryKey: qk.likes.state(target, publicId),
    queryFn: () => engagementApi.likeState(target, publicId),
    enabled: Boolean(publicId) && enabled,
  });
}

/**
 * Przełącznik polubienia z optimistic update — UI reaguje natychmiast, a po
 * odpowiedzi serwera synchronizuje licznik. Gdy dojdzie WebSocket, wystarczy
 * invalidacja qk.likes.state(...) z eventu.
 */
export function useToggleLike(target, publicId) {
  const qc = useQueryClient();
  const key = qk.likes.state(target, publicId);

  return useMutation({
    mutationFn: (liked) =>
      liked
        ? engagementApi.unlike(target, publicId)
        : engagementApi.like(target, publicId),
    onMutate: async (liked) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData(key);
      qc.setQueryData(key, (old) => {
        const count = old?.count ?? 0;
        return { count: liked ? Math.max(0, count - 1) : count + 1, liked: !liked };
      });
      return { prev };
    },
    onError: (_err, _liked, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
    },
    onSuccess: (data) => {
      qc.setQueryData(key, data);
    },
  });
}

/** Statystyki użytkownika z widoku DB (/users/{id}/stats). */
export function useUserStats(userId) {
  return useQuery({
    queryKey: qk.users.stats(userId),
    queryFn: () => engagementApi.userStats(userId),
    enabled: Boolean(userId),
  });
}

/** Najczęściej polubiony wątek (do „wątku tygodnia"); opcjonalnie per kategoria. */
export function useFeaturedPost(categoryId = null) {
  return useQuery({
    queryKey: qk.featured.post(categoryId),
    queryFn: () => engagementApi.featuredPost(categoryId),
  });
}
