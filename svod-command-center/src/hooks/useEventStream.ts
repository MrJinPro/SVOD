import { useEffect, useRef, useState } from 'react';
import { apiFetchRaw } from '@/lib/api';

type StreamEvent = {
  event: string;
  data: any;
};

function parseEventBlock(block: string): StreamEvent | null {
  // SSE format: lines like "event: name" and "data: ..." (can be multiple)
  const lines = block.split('\n').map((l) => l.trimEnd());
  let eventName = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue;
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim() || 'message';
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
      continue;
    }
  }

  if (dataLines.length === 0) return null;

  const dataText = dataLines.join('\n');
  let data: any = dataText;
  try {
    data = JSON.parse(dataText);
  } catch {
    // keep as string
  }

  return { event: eventName, data };
}

export function useEventStream(options: {
  path: string;
  enabled: boolean;
  onEvent: (evt: StreamEvent) => void;
}) {
  const { path, enabled, onEvent } = options;
  const [status, setStatus] = useState<'idle' | 'connecting' | 'open' | 'error'>('idle');
  const lastErrorRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus('idle');
      return;
    }

    const controller = new AbortController();
    const decoder = new TextDecoder('utf-8');

    async function run() {
      setStatus('connecting');
      lastErrorRef.current = null;

      try {
        const res = await apiFetchRaw(path, {
          method: 'GET',
          signal: controller.signal,
          headers: {
            Accept: 'text/event-stream',
          },
        });

        if (!res.body) {
          throw new Error('Stream not supported (no body)');
        }

        setStatus('open');

        const reader = res.body.getReader();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by blank line
          let idx = buffer.indexOf('\n\n');
          while (idx !== -1) {
            const block = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const evt = parseEventBlock(block);
            if (evt) onEvent(evt);
            idx = buffer.indexOf('\n\n');
          }
        }
      } catch (e: any) {
        if (controller.signal.aborted) return;
        lastErrorRef.current = e?.message || 'Stream error';
        setStatus('error');
      }
    }

    run();

    return () => {
      controller.abort();
    };
  }, [enabled, path, onEvent]);

  return { status, error: lastErrorRef.current };
}
