export function safeReturn(value: string | null) {
  if (
    !value ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    /[\\\u0000-\u0020\u007f]/.test(value)
  )
    return '/home';
  let path: string;
  try {
    // Match browser URL normalization and the router's decoded, case-insensitive paths.
    path =
      decodeURIComponent(new URL(value, 'https://bluddit.invalid').pathname)
        .replace(/\/+$/, '')
        .toLowerCase() || '/';
  } catch {
    return '/home';
  }
  if (['/', '/login', '/register', '/logout', '/pending-approval'].includes(path)) return '/home';
  return value;
}
