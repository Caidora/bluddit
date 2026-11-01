import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { EmptyState, ErrorNotice, Loading, PageTitle } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { ApiError } from '@/lib/http';
import { accountsApi } from '@/features/accounts/api';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { eventsApi } from './api';
import {
  detailOptions,
  eventKeys,
  listOptions,
  referencesOptions,
  useEventMutation,
} from './queries';
import { EventTime, localInput } from './fields';
import { EventForm } from './event-form';
import type { EventContent, GuildEvent } from './types';

function Guidance() {
  return (
    <nav
      aria-label="Related handbook guidance"
      className="my-6 flex flex-wrap gap-4 text-primary underline"
    >
      <Link to="/handbook?q=scheduling">Scheduling guidance</Link>
      <Link to="/handbook?q=loot">Loot guidance</Link>
    </nav>
  );
}
function canManage(event: GuildEvent, actor: ReturnType<typeof useAccount>) {
  return (
    actor.permissions.includes('shared_records.correct') ||
    (actor.permissions.includes('events.manage') &&
      event.organizers.some((o) => o.account_id === actor.id && o.active))
  );
}
export function Events() {
  const actor = useAccount();
  const [search, setSearch] = useSearchParams();
  const query = useQuery(listOptions(actor.id, search.toString()));
  function filter(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const params = new URLSearchParams();
    for (const [key, value] of data) if (typeof value === 'string') params.set(key, value);
    setSearch(params);
  }
  function page(offset: number) {
    const params = new URLSearchParams(search);
    params.set('offset', String(offset));
    setSearch(params);
  }
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageTitle description="Good runs start with a plan.">Events</PageTitle>
        {actor.permissions.includes('events.create') && (
          <Link className="text-primary underline" to="/events/new">
            Create event
          </Link>
        )}
      </div>
      <form
        key={search.toString()}
        onSubmit={filter}
        className="mb-5 flex flex-wrap items-end gap-4 rounded-xl border p-4"
      >
        <label className="space-y-2">
          When
          <select
            name="period"
            defaultValue={search.get('period') ?? 'upcoming'}
            className="block rounded-md border bg-background p-2"
          >
            <option value="upcoming">Upcoming</option>
            <option value="past">Past</option>
            <option value="all">All dates</option>
          </select>
        </label>
        <label className="space-y-2">
          Event state
          <select
            name="state"
            defaultValue={search.get('state') ?? 'scheduled'}
            className="block rounded-md border bg-background p-2"
          >
            <option value="scheduled">Scheduled</option>
            <option value="cancelled">Cancelled</option>
            <option value="all">All states</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input
            name="mine"
            type="checkbox"
            value="true"
            defaultChecked={search.get('mine') === 'true'}
          />
          Organized by me
        </label>
        <Button type="submit">Apply filters</Button>
      </form>
      {query.isError && (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      )}
      {query.isPending ? (
        <Loading label="Loading events…" />
      ) : (
        query.data && (
          <>
            {query.data.events.length === 0 ? (
              <EmptyState title="No matching events">
                Create an activity or change the filters.
              </EmptyState>
            ) : (
              <div className="grid gap-4">
                {query.data.events.map((event) => (
                  <article
                    key={event.event_id}
                    className="min-w-0 space-y-2 rounded-xl border bg-card p-5"
                  >
                    <h2 className="break-words text-lg font-semibold">
                      <Link
                        className="text-primary underline"
                        to={`/events/${event.event_id}`}
                      >
                        {event.title}
                      </Link>
                    </h2>
                    <p>
                      <EventTime instant={event.starts_at} />
                    </p>
                    <p>
                      {event.state === 'cancelled' ? 'Cancelled' : 'Scheduled'} ·{' '}
                      {event.organizers.map((o) => o.display_name).join(', ')}
                    </p>
                  </article>
                ))}
              </div>
            )}
            <div className="my-5 flex flex-wrap items-center gap-4">
              <Button
                variant="outline"
                disabled={!query.data.offset || query.isFetching}
                onClick={() => page(Math.max(0, query.data.offset - query.data.limit))}
              >
                Previous
              </Button>
              <span>Page {Math.floor(query.data.offset / query.data.limit) + 1}</span>
              <Button
                variant="outline"
                disabled={!query.data.has_more || query.isFetching}
                onClick={() => page(query.data.offset + query.data.limit)}
              >
                Next
              </Button>
            </div>
          </>
        )
      )}
      <Guidance />
    </>
  );
}

export function EventEditor({ creating = false }: { creating?: boolean }) {
  const actor = useAccount();
  const { eventId } = useParams();
  const id = Number(eventId);
  const navigate = useNavigate();
  const refs = useQuery(referencesOptions(actor.id));
  const query = useQuery({
    ...detailOptions(actor.id, id),
    enabled: !creating && Number.isSafeInteger(id) && id > 0,
  });
  const mutation = useEventMutation((body: EventContent) => {
    if (creating) return eventsApi.create(body);
    const initial = query.data!;
    if (
      body.local_start === localInput(initial.starts_at, initial.scheduling_timezone) &&
      body.scheduling_timezone === initial.scheduling_timezone
    ) {
      const {
        local_start: _local,
        scheduling_timezone: _zone,
        occurrence: _occurrence,
        ...content
      } = body;
      return eventsApi.update(id, content);
    }
    return eventsApi.update(id, body);
  });
  if (
    !creating &&
    (!Number.isSafeInteger(id) ||
      id <= 0 ||
      (query.error instanceof ApiError && query.error.status === 404))
  )
    return <PageTitle>Event not found</PageTitle>;
  if (refs.isPending || (!creating && query.isPending))
    return <Loading label="Loading event form…" />;
  if (!refs.data || (!creating && !query.data))
    return (
      <ErrorNotice
        error={refs.error ?? query.error}
        retry={() => {
          void refs.refetch();
          if (!creating) void query.refetch();
        }}
      />
    );
  if (creating ? !actor.permissions.includes('events.create') : !canManage(query.data!, actor))
    return <PageTitle>Permission denied</PageTitle>;
  if (!creating && query.data?.state === 'cancelled')
    return (
      <>
        <PageTitle>This event is cancelled</PageTitle>
        <Link to={`/events/${id}`}>View event</Link>
      </>
    );
  return (
    <>
      <PageTitle>{creating ? 'Create event' : 'Edit event'}</PageTitle>
      <EventForm
        initial={creating ? undefined : query.data}
        references={refs.data}
        pending={mutation.isPending}
        error={mutation.error}
        save={(body) =>
          mutation.mutate(body, {
            onSuccess: (event) => navigate(`/events/${event.event_id}`),
          })
        }
      />
    </>
  );
}

function OrganizerForm({ event }: { event: GuildEvent }) {
  const actor = useAccount();
  const [selected, setSelected] = useState(
    event.organizers.filter((o) => o.active).map((o) => o.account_id)
  );
  const [offset, setOffset] = useState(0);
  const [saved, setSaved] = useState(false);
  const query = useQuery({
    queryKey: [...eventKeys.all(actor.id), 'organizer-accounts', offset],
    queryFn: ({ signal }) =>
      accountsApi.accounts({ membership_state: 'active', limit: 100, offset }, signal),
  });
  const mutation = useEventMutation((ids: number[]) =>
    eventsApi.organizers(event.event_id, ids)
  );
  return (
    <form
      className="my-5 space-y-4 rounded-xl border p-5"
      onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        mutation.mutate(selected, { onSuccess: () => setSaved(true) });
      }}
    >
      <h2 className="text-lg font-semibold">Organizer assignments</h2>
      <p>Selected organizers: {selected.length}. Only active members can be assigned.</p>
      <fieldset disabled={mutation.isPending} className="space-y-2">
        <legend className="sr-only">Active members</legend>
        {query.isPending && <Loading label="Loading members…" />}
        {query.isError && (
          <ErrorNotice
            error={query.error}
            retry={() => {
              void query.refetch();
            }}
          />
        )}
        {query.data?.accounts.map((account) => (
          <label key={account.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected.includes(account.id)}
              onChange={(e) => {
                setSaved(false);
                setSelected((ids) =>
                  e.target.checked
                    ? [...ids, account.id]
                    : ids.filter((id) => id !== account.id)
                );
              }}
            />
            {account.display_name} ({account.username})
          </label>
        ))}
      </fieldset>
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          disabled={offset === 0 || query.isFetching}
          onClick={() => setOffset(Math.max(0, offset - 100))}
        >
          Previous members
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={(query.data?.accounts.length ?? 0) < 100 || query.isFetching}
          onClick={() => setOffset(offset + 100)}
        >
          More members
        </Button>
      </div>
      {mutation.isError && <ErrorNotice error={mutation.error} />}
      {saved && <p role="status">Organizers saved.</p>}
      <Button type="submit" disabled={mutation.isPending || !selected.length}>
        Save organizers
      </Button>
    </form>
  );
}
export function EventDetails() {
  const actor = useAccount();
  const id = Number(useParams().eventId);
  const query = useQuery(detailOptions(actor.id, id));
  const refs = useQuery(referencesOptions(actor.id));
  const mutation = useEventMutation(() => eventsApi.cancel(id));
  const [confirm, setConfirm] = useState(false);
  if (
    !Number.isSafeInteger(id) ||
    id <= 0 ||
    (query.error instanceof ApiError && query.error.status === 404)
  )
    return <PageTitle>Event not found</PageTitle>;
  if (query.isPending || refs.isPending) return <Loading label="Loading event…" />;
  if (!query.data || !refs.data)
    return (
      <ErrorNotice
        error={query.error ?? refs.error}
        retry={() => {
          void query.refetch();
          void refs.refetch();
        }}
      />
    );
  const event = query.data;
  const dungeon = refs.data.dungeons.find((d) => d.id === event.dungeon_id);
  const editable = event.state === 'scheduled' && canManage(event, actor);
  return (
    <>
      <Link className="text-primary underline" to="/events">
        ← Events
      </Link>
      <PageTitle
        description={refs.data.activities.find((a) => a.id === event.activity_type)?.name}
      >
        {event.title}
      </PageTitle>
      {(query.isError || refs.isError) && <ErrorNotice error={query.error ?? refs.error} />}
      <section aria-label="Event details" className="space-y-4 rounded-xl border bg-card p-5">
        <p className="font-semibold">
          {event.state === 'cancelled' ? 'Cancelled' : 'Scheduled'}
        </p>
        <p>
          <EventTime instant={event.starts_at} />
        </p>
        <p className="text-sm text-muted-foreground">
          Scheduling time:{' '}
          <EventTime instant={event.starts_at} zone={event.scheduling_timezone} />
        </p>
        <p>
          Expected duration:{' '}
          {event.duration_minutes == null
            ? 'Not specified'
            : `${event.duration_minutes} minutes`}
        </p>
        <p>Maximum group size: {event.capacity ?? 'Not specified'}</p>
        <p>
          Organizers:{' '}
          {event.organizers
            .map((o) => `${o.display_name}${o.active ? '' : ' (inactive)'}`)
            .join(', ')}
        </p>
        {dungeon && (
          <p>
            <Link
              className="text-primary underline"
              to={`/bluds?dungeon_id=${encodeURIComponent(dungeon.id)}&dungeon_status=not_completed`}
            >
              {dungeon.name}: Bluds with incomplete progress
            </Link>
          </p>
        )}
        <div>
          <h2 className="font-semibold">Requirements and destination notes</h2>
          <p className="whitespace-pre-wrap break-words">
            {event.requirements || 'None specified'}
          </p>
        </div>
        {editable && (
          <div className="flex flex-wrap items-center gap-4">
            <Link className="text-primary underline" to={`/events/${id}/edit`}>
              Edit event
            </Link>
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => setConfirm(true)}
            >
              Cancel event
            </Button>
          </div>
        )}
        {mutation.isError && <ErrorNotice error={mutation.error} />}
      </section>
      {event.state === 'scheduled' && actor.permissions.includes('shared_records.correct') && (
        <OrganizerForm
          key={event.organizers.map((o) => o.account_id).join(',')}
          event={event}
        />
      )}
      <Guidance />
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel {event.title}?</AlertDialogTitle>
            <AlertDialogDescription>
              The event will remain readable. Cancellation cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep event</AlertDialogCancel>
            <AlertDialogAction onClick={() => mutation.mutate(undefined)}>
              Confirm cancellation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
