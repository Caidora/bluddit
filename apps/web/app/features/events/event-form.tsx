import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { ErrorNotice } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { eventsApi } from './api';
import { eventKeys } from './queries';
import { formatTime, localInput, viewerTimezone } from './fields';
import type { EventContent, GuildEvent, References, Schedule } from './types';

const selectClass = 'h-10 w-full min-w-0 rounded-md border bg-background px-2';
export function EventForm({
  initial,
  references,
  pending,
  error,
  save,
}: {
  initial?: GuildEvent;
  references: References;
  pending: boolean;
  error: unknown;
  save: (body: EventContent) => void;
}) {
  const actor = useAccount();
  const browserZone = viewerTimezone();
  const [local, setLocal] = useState(
    initial ? localInput(initial.starts_at, initial.scheduling_timezone) : ''
  );
  const [zone, setZone] = useState(
    initial?.scheduling_timezone ??
      (references.timezones.includes(browserZone) ? browserZone : 'UTC')
  );
  const [occurrence, setOccurrence] = useState<Schedule['occurrence']>();
  const preview = useQuery({
    queryKey: [...eventKeys.all(actor.id), 'preview', local, zone],
    queryFn: ({ signal }) =>
      eventsApi.preview({ local_start: local, scheduling_timezone: zone }, signal),
    enabled: !!local && !!zone,
    retry: false,
  });
  const existingOccurrence =
    initial &&
    local === localInput(initial.starts_at, initial.scheduling_timezone) &&
    zone === initial.scheduling_timezone
      ? preview.data?.candidates.find(
          (c) => new Date(c.starts_at).getTime() === new Date(initial.starts_at).getTime()
        )?.occurrence
      : undefined;
  const selectedOccurrence = occurrence ?? existingOccurrence;
  const chosen = preview.data?.candidates.find(
    (c) => preview.data.status === 'valid' || c.occurrence === selectedOccurrence
  );
  const pinned = ['Pacific/Auckland', 'Australia/Sydney', 'Australia/Perth', 'UTC'];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !preview.data || preview.isError) return;
    const data = new FormData(event.currentTarget);
    const text = (name: string) => String(data.get(name) ?? '');
    save({
      title: text('title'),
      activity_type: text('activity_type'),
      dungeon_id: text('dungeon_id') || null,
      duration_minutes: text('duration_minutes') ? Number(text('duration_minutes')) : null,
      capacity: text('capacity') ? Number(text('capacity')) : null,
      requirements: text('requirements'),
      local_start: local,
      scheduling_timezone: zone,
      ...(selectedOccurrence ? { occurrence: selectedOccurrence } : {}),
    });
  }
  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border bg-card p-5">
      <fieldset disabled={pending} className="grid min-w-0 gap-5 sm:grid-cols-2">
        <label className="space-y-2 sm:col-span-2">
          Title
          <Input name="title" required maxLength={200} defaultValue={initial?.title} />
        </label>
        <label className="space-y-2">
          Activity type
          <select
            name="activity_type"
            className={selectClass}
            defaultValue={initial?.activity_type ?? 'dungeon'}
          >
            {references.activities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          Dungeon destination
          <select
            name="dungeon_id"
            className={selectClass}
            defaultValue={initial?.dungeon_id ?? ''}
          >
            <option value="">No dungeon destination</option>
            {references.dungeons.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 space-y-2">
          Local start date and time
          <Input
            type="datetime-local"
            step="1"
            required
            value={local}
            onChange={(e) => {
              setLocal(e.target.value);
              setOccurrence(undefined);
            }}
          />
        </label>
        <label className="min-w-0 space-y-2">
          Scheduling timezone
          <select
            className={selectClass}
            value={zone}
            onChange={(e) => {
              setZone(e.target.value);
              setOccurrence(undefined);
            }}
          >
            {[
              ...pinned.filter((z) => references.timezones.includes(z)),
              ...references.timezones.filter((z) => !pinned.includes(z)),
            ].map((z) => (
              <option key={z}>{z}</option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          Expected duration (minutes, optional)
          <Input
            type="number"
            name="duration_minutes"
            min={1}
            step={1}
            defaultValue={initial?.duration_minutes ?? ''}
          />
        </label>
        <label className="space-y-2">
          Maximum group size (optional)
          <Input
            type="number"
            name="capacity"
            min={1}
            step={1}
            defaultValue={initial?.capacity ?? ''}
          />
        </label>
        <label className="space-y-2 sm:col-span-2">
          Requirements and destination notes
          <textarea
            name="requirements"
            maxLength={10000}
            defaultValue={initial?.requirements ?? ''}
            className="min-h-28 w-full rounded-md border bg-background p-3"
          />
        </label>
      </fieldset>
      {local && preview.isPending && <p role="status">Checking scheduled time…</p>}
      {preview.isError && (
        <ErrorNotice
          error={preview.error}
          retry={() => {
            void preview.refetch();
          }}
        />
      )}
      {preview.data?.status === 'nonexistent' && (
        <p role="alert">
          This local time does not exist because the clocks move forward. Choose another time.
        </p>
      )}
      {preview.data?.status === 'ambiguous' && (
        <fieldset className="space-y-3" disabled={pending}>
          <legend>This time occurs twice. Choose an occurrence.</legend>
          {preview.data.candidates.map((c) => (
            <label className="flex gap-2" key={c.occurrence}>
              <input
                type="radio"
                name="occurrence"
                value={c.occurrence}
                checked={selectedOccurrence === c.occurrence}
                onChange={() => setOccurrence(c.occurrence)}
              />
              {c.occurrence === 'earlier' ? 'Earlier' : 'Later'} — UTC{c.utc_offset} (
              {c.starts_at})
            </label>
          ))}
        </fieldset>
      )}
      {chosen && !preview.isError && (
        <p role="status">
          Scheduled: {formatTime(chosen.starts_at, zone)} · UTC{chosen.utc_offset}
        </p>
      )}
      {error != null && <ErrorNotice error={error} />}
      <div className="flex flex-wrap gap-4">
        <Button
          type="submit"
          disabled={pending || !chosen || preview.isFetching || preview.isError}
        >
          {pending ? 'Saving…' : initial ? 'Save event' : 'Create event'}
        </Button>
        <Link
          className="self-center text-primary underline"
          to={initial ? `/events/${initial.event_id}` : '/events'}
        >
          Back without saving
        </Link>
      </div>
    </form>
  );
}
