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

  // The server streams keepalive whitespace lines while the agent works,
  // then sends the JSON payload at the end. Just read the full body and
  // trim the keepalive whitespace before parsing.
  const text = await res.text()
  return JSON.parse(text.trim()) as T
}
