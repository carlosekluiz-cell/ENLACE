'use client';

import { useState, useEffect, useCallback } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiReturn<T> extends UseApiState<T> {
  refetch: () => void;
}

/**
 * Generic API fetch hook with loading and error states.
 * Gracefully handles API unavailability.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: any[] = []
): UseApiReturn<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const fetchData = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetcher();
      setState({ data, loading: false, error: null });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'An unexpected error occurred';
      setState({ data: null, loading: false, error: message });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { ...state, refetch: fetchData };
}

/**
 * Lazy API hook - only fetches when explicitly called.
 */
export function useLazyApi<T, P = void>(
  fetcher: (params: P) => Promise<T>
): {
  data: T | null;
  loading: boolean;
  error: string | null;
  execute: (params: P) => Promise<T | null>;
  reset: () => void;
} {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (params: P): Promise<T | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await fetcher(params);
        setState({ data, loading: false, error: null });
        return data;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred';
        setState({ data: null, loading: false, error: message });
        return null;
      }
    },
    [fetcher]
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}
