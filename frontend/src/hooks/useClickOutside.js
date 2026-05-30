import { useEffect } from 'react';

/**
 * Wywołuje `handler`, gdy użytkownik kliknie poza elementem `ref`.
 * Używane przez dropdowny (menu użytkownika w TopBar).
 */
export function useClickOutside(ref, handler, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    function onPointerDown(event) {
      const el = ref.current;
      if (!el || el.contains(event.target)) return;
      handler(event);
    }
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
    };
  }, [ref, handler, enabled]);
}
