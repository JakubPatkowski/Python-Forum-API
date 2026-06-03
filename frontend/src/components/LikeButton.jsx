import { useAuth } from '../auth/AuthContext';
import { Icon } from './Icon';
import { useLikeState, useToggleLike } from '../hooks/useEngagement';

/**
 * Przycisk polubienia z licznikiem. target: 'posts' | 'comments'.
 * Dla niezalogowanych pokazuje sam licznik (klik nie robi nic — backend i tak
 * wymaga auth). Optimistic update w hooku.
 */
export function LikeButton({ target, publicId, size = 'md' }) {
  const { isAuthenticated } = useAuth();
  const { data } = useLikeState(target, publicId);
  const toggle = useToggleLike(target, publicId);

  const count = data?.count ?? 0;
  const liked = data?.liked ?? false;

  const onClick = () => {
    if (!isAuthenticated) return;
    toggle.mutate(liked);
  };

  return (
    <button
      type="button"
      className={`like-btn like-${size}` + (liked ? ' liked' : '')}
      onClick={onClick}
      disabled={!isAuthenticated}
      aria-pressed={liked}
      title={isAuthenticated ? '' : undefined}
    >
      <Icon name="heart" size={size === 'sm' ? 12 : 14} />
      <span className="like-count">{count}</span>
    </button>
  );
}
