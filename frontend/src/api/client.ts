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

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // Look for a complete SSE data line
    const dataMatch = buffer.match(/^data: (.+)$/m)
    if (dataMatch) {
      reader.cancel()
      return JSON.parse(dataMatch[1]) as T
    }
  }

  throw new Error("SSE stream ended without data event")
}
