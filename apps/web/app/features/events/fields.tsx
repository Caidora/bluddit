export function viewerTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}
export function formatTime(instant: string, zone = viewerTimezone()) {
  return `${new Intl.DateTimeFormat(undefined, { timeZone: zone, dateStyle: 'full', timeStyle: 'short' }).format(new Date(instant))} (${zone})`;
}
export function EventTime({ instant, zone }: { instant: string; zone?: string }) {
  return <time dateTime={instant}>{formatTime(instant, zone)}</time>;
}
export function localInput(instant: string, zone: string) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: zone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(instant));
  const part = (name: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === name)!.value;
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}:${part('second')}`;
}
