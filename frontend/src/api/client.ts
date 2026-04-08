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

    // SSE events are delimited by a blank line.
    // Support both \n\n and \r\n\r\n line endings.
    let eventEnd = buffer.indexOf("\n\n")
    let skip = 2
    if (eventEnd === -1) {
      eventEnd = buffer.indexOf("\r\n\r\n")
      skip = 4
    }
    if (eventEnd === -1) continue

    const event = buffer.slice(0, eventEnd)
    buffer = buffer.slice(eventEnd + skip)

    // Extract the data payload — everything after "data: " prefix
    const dataPrefix = "data: "
    const dataLine = event.split(/\r?\n/).find(line => line.startsWith(dataPrefix))
    if (dataLine) {
      reader.cancel()
      return JSON.parse(dataLine.slice(dataPrefix.length)) as T
    }
    // Not a data event (keepalive comment) — continue
  }

  throw new Error("SSE stream ended without data event")
}
