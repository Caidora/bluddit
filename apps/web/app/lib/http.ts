export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: string
  ) {
    super(message);
  }
}

export async function send<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: 'same-origin',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.method && options.method !== 'GET' ? { 'X-CSRF-Protection': '1' } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Couldn’t connect. Check your connection and try again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      typeof body?.detail === 'string' ? body.detail : 'The request could not be completed.',
      response.headers.get('Retry-After') ?? undefined
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
