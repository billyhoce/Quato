const BASE_URL = "/api"

let getSessionId: () => string = () => {
  throw new Error("Session provider not initialized")
}

export function setSessionIdGetter(getter: () => string) {
  getSessionId = getter
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Session-ID": getSessionId(),
    ...(options.headers as Record<string, string> || {}),
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `API error ${res.status}`)
  }

  return res.json()
}

/**
 * POST to an SSE endpoint and return the first `data:` event parsed as JSON.
 * Keepalive comments (`: keepalive`) are silently consumed while waiting.
 */
export async function apiSSEFetch<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errBody.detail || `API error ${res.status}`)
  }

  // Wait for the full response. The server sends SSE keepalives to prevent
  // Cloudflare 524 timeouts; the browser consumes them transparently.
  // We only need the final "data: " event.
  const text = await res.text()

  // Find the last "data: " line — that's our JSON payload
  for (const line of text.split(/\r?\n/).reverse()) {
    if (line.startsWith("data: ")) {
      return JSON.parse(line.slice(6)) as T
    }
  }

  throw new Error("SSE stream ended without data event")
}
