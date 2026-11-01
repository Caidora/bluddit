import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { EmptyState, ErrorNotice, Loading, PageTitle } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError } from '@/lib/http';
import { BludForm } from './blud-form';
import { choiceName, SelectField, UpdatedAt } from './fields';
import { bludsOptions, createOptions, referencesOptions } from './queries';

export function Bluds() {
  const actor = useAccount();
  const [search, setSearch] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const references = useQuery(referencesOptions(actor.id));
  const query = useQuery(bludsOptions(actor.id, search.toString()));
  const mutation = useMutation(createOptions(useQueryClient(), actor.id));
  const [creating, setCreating] = useState(false);
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(event.currentTarget)) {
      if (typeof value === 'string' && value.trim()) params.set(key, value.trim());
    }
    // Retain the selected page size while resetting pagination after filtering.
    if (search.has('limit')) params.set('limit', search.get('limit')!);
    setSearch(params);
  }
  function paginate(offset: number) {
    const params = new URLSearchParams(search);
    params.set('offset', String(offset));
    setSearch(params);
  }
  if (
    [query.error, references.error].some(
      (error) => error instanceof ApiError && error.status === 403
    )
  )
    return <Navigate to="/unauthorized" replace />;
  if (references.isPending) return <Loading label="Loading game references…" />;
  if (!references.data)
    return (
      <ErrorNotice
        error={references.error}
        retry={() => {
          void references.refetch();
        }}
      />
    );
  const refs = references.data;
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle description="Find your guild’s characters, professions, and next dungeon run.">
          Bluds
        </PageTitle>
        {actor.permissions.includes('bluds.edit_own') && !creating && (
          <Button
            onClick={() => {
              mutation.reset();
              setCreating(true);
            }}
          >
            Add Blud
          </Button>
        )}
      </div>
      {creating && (
        <div className="mb-6">
          <BludForm
            references={refs}
            pending={mutation.isPending}
            error={mutation.error}
            cancel={() => setCreating(false)}
            submit={(body) =>
              mutation.mutate(body, {
                onSuccess: (blud) =>
                  navigate(`/bluds/${blud.blud_id}`, { state: { listSearch: location.search } }),
              })
            }
          />
        </div>
      )}
      <form
        key={search.toString()}
        onSubmit={filter}
        className="mb-6 space-y-4 rounded-xl border bg-card p-4"
      >
        <div className="space-y-2">
          <Label htmlFor="blud-search">Search characters or members</Label>
          <Input
            id="blud-search"
            name="q"
            maxLength={200}
            defaultValue={search.get('q') ?? ''}
            placeholder="Character or member name"
          />
        </div>
        <div className="grid min-w-0 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <SelectField
            label="Class filter"
            name="class_id"
            choices={refs.classes}
            empty="All classes"
            defaultValue={search.get('class_id') ?? ''}
          />
          <SelectField
            label="Profession filter"
            name="profession_id"
            choices={refs.professions}
            empty="All professions"
            defaultValue={search.get('profession_id') ?? ''}
          />
          <SelectField
            label="Farming zone filter"
            name="farming_zone_id"
            choices={refs.zones}
            empty="All zones"
            defaultValue={search.get('farming_zone_id') ?? ''}
          />
          <SelectField
            label="Dungeon filter"
            name="dungeon_id"
            choices={refs.dungeons}
            empty="All dungeons"
            defaultValue={search.get('dungeon_id') ?? ''}
          />
          <SelectField
            label="Dungeon status filter"
            name="dungeon_status"
            choices={refs.dungeon_statuses}
            empty="Choose a dungeon to filter status"
            defaultValue={search.get('dungeon_status') ?? ''}
          />
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              name="mine"
              value="true"
              defaultChecked={search.get('mine') === 'true'}
            />
            Mine only
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              name="archived"
              value="true"
              defaultChecked={search.get('archived') === 'true'}
            />
            Archived Bluds
          </label>
          <Button type="submit" size="sm">
            Apply filters
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setSearch({})}>
            Clear filters
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Dungeon status applies to the selected dungeon; defaults to Not completed.
        </p>
      </form>
      {references.isError && (
        <ErrorNotice
          error={references.error}
          retry={() => {
            void references.refetch();
          }}
        />
      )}
      {query.isError && (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      )}
      {query.isPending ? (
        <Loading label="Loading Bluds…" />
      ) : (
        query.data && (
          <>
            {query.data.bluds.length === 0 ? (
              <EmptyState title={search.size ? 'No matching Bluds' : 'No Bluds yet'}>
                {search.size
                  ? 'Try changing or clearing the filters.'
                  : 'Add your first character to help the guild plan together.'}
              </EmptyState>
            ) : (
              <div className="grid min-w-0 gap-4" aria-label="Bluds directory">
                {query.data.bluds.map((blud) => (
                  <article key={blud.blud_id} className="min-w-0 rounded-xl border bg-card p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="break-words text-lg font-semibold">
                          <Link
                            className="text-primary underline-offset-4 hover:underline"
                            to={`/bluds/${blud.blud_id}`}
                            state={{ listSearch: location.search }}
                          >
                            {blud.name}
                          </Link>
                        </h2>
                        <p className="break-words text-sm text-muted-foreground">
                          {blud.owner_name} · {choiceName(refs.classes, blud.class_id)}
                          {blud.spec_id &&
                            ` · ${choiceName(refs.classes.find((item) => item.id === blud.class_id)?.specs ?? [], blud.spec_id)}`}
                        </p>
                      </div>
                      <Badge variant="outline">
                        {blud.completed_dungeons}/{blud.total_dungeons} dungeons
                      </Badge>
                    </div>
                    <div className="mt-4 grid min-w-0 gap-4 text-sm sm:grid-cols-2">
                      <div>
                        <h3 className="mb-1 font-medium">Professions</h3>
                        {blud.professions.length ? (
                          blud.professions.map((item) => (
                            <div key={item.profession_id} className="mb-2">
                              {choiceName(refs.professions, item.profession_id)} ·{' '}
                              {item.level ?? 'Level not set'}
                              <br />
                              <UpdatedAt value={item.updated_at} />
                            </div>
                          ))
                        ) : (
                          <p className="text-muted-foreground">Not set</p>
                        )}
                      </div>
                      <div>
                        <h3 className="mb-1 font-medium">Farming zone</h3>
                        <p>{choiceName(refs.zones, blud.farming_zone_id)}</p>
                        <UpdatedAt value={blud.farming_zone_updated_at} />
                        <p className="mt-2 text-muted-foreground">
                          {blud.rerun_dungeons} completed{' '}
                          {blud.rerun_dungeons === 1 ? 'dungeon' : 'dungeons'} wanted again
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                disabled={query.data.offset === 0 || query.isFetching}
                onClick={() => paginate(Math.max(0, query.data.offset - query.data.limit))}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {Math.floor(query.data.offset / query.data.limit) + 1}
              </span>
              <Button
                variant="outline"
                disabled={!query.data.has_more || query.isFetching}
                onClick={() => paginate(query.data.offset + query.data.limit)}
              >
                Next
              </Button>
            </div>
          </>
        )
      )}
    </>
  );
}
