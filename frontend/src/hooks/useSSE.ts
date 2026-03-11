'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import type { SSEEvent } from '@/lib/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network';

interface UseSSEOptions {
  eventTypes?: string[];
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
}

export function useSSE({ eventTypes, enabled = true, onEvent }: UseSSEOptions = {}) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef(0);
  const maxRetries = 10;

  const connect = useCallback(() => {
    if (!enabled || typeof window === 'undefined') return;

    const token = localStorage.getItem('pulso_access_token');
    if (!token) return;

    const params = new URLSearchParams();
    if (eventTypes?.length) params.set('types', eventTypes.join(','));

    // EventSource doesn't support custom headers, so pass token as query param
    // For production, use a proper SSE library or cookie-based auth
    const url = `${API_BASE}/api/v1/events/stream?token=${token}&${params}`;

    try {
      const source = new EventSource(url);
      sourceRef.current = source;

      source.onopen = () => {
        setConnected(true);
        retryRef.current = 0;
      };

      source.onmessage = (e) => {
        try {
          const event: SSEEvent = JSON.parse(e.data);
          setLastEvent(event);
          onEvent?.(event);
        } catch {
          // Heartbeat or non-JSON message
        }
      };

      source.onerror = () => {
        setConnected(false);
        source.close();
        sourceRef.current = null;

        // Exponential backoff reconnect
        if (retryRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryRef.current), 30000);
          retryRef.current++;
          setTimeout(connect, delay);
        }
      };
    } catch {
      // EventSource not supported or URL invalid
    }
  }, [enabled, eventTypes, onEvent]);

  useEffect(() => {
    connect();
    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [connect]);

  return { connected, lastEvent };
}
