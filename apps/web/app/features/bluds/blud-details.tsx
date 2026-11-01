import { useState, type FormEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import { Link, Navigate, useLocation, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { ErrorNotice, Loading, PageTitle } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ApiError } from '@/lib/http';
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
import { BludForm } from './blud-form';
import { choiceName, UpdatedAt } from './fields';
import { bludOptions, referencesOptions, updateOptions } from './queries';
import type { Blud, BludPatch, DungeonStatus, ProfessionInput, References } from './types';

function ProfessionForm({
  blud,
  references: currentReferences,
  pending,
  error,
  save,
  cancel,
}: {
  blud: Blud;
  references: References;
  pending: boolean;
  error: unknown;
  save: (body: BludPatch) => void;
  cancel: () => void;
}) {
  const [references] = useState(currentReferences);
  const [professions, setProfessions] = useState<ProfessionInput[]>(() =>
    blud.professions.map(({ profession_id, level }) => ({ profession_id, level }))
  );
  const primaryCount = professions.filter(
    (item) =>
      references.professions.find((ref) => ref.id === item.profession_id)?.category ===
      'primary'
  ).length;
  function submit(event: FormEvent) {
    event.preventDefault();
    save({ professions });
  }
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">Edit professions</h2>
      <p className="text-sm text-muted-foreground">
        Choose up to {references.max_primary_professions} primary professions and any secondary
        professions. Leave unknown levels blank.
      </p>
      {(['primary', 'secondary', null] as const).map((category) => (
        <fieldset key={category ?? 'unknown'} className="min-w-0 space-y-3">
          <legend className="mb-3 font-medium capitalize">
            {category ?? 'Unclassified'} professions
          </legend>
          {references.professions
            .filter(
              (item) =>
                item.category === category &&
                (item.active || professions.some((p) => p.profession_id === item.id))
            )
            .map((reference) => {
              const assigned = professions.find((item) => item.profession_id === reference.id);
              return (
                <div
                  key={reference.id}
                  className="grid min-w-0 grid-cols-[minmax(0,1fr)_6rem] items-center gap-3"
                >
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!!assigned}
                      disabled={
                        pending ||
                        (!assigned && (!reference.active || reference.category === null)) ||
                        (!assigned &&
                          category === 'primary' &&
                          primaryCount >= references.max_primary_professions)
                      }
                      onChange={(event) =>
                        setProfessions((current) =>
                          event.target.checked
                            ? [...current, { profession_id: reference.id, level: null }]
                            : current.filter((item) => item.profession_id !== reference.id)
                        )
                      }
                    />
                    {reference.name}
                    {!reference.active || reference.category === null ? ' (unavailable)' : ''}
                  </label>
                  <Input
                    type="number"
                    aria-label={`${reference.name} level`}
                    min={0}
                    max={reference.max_level ?? undefined}
                    step={1}
                    disabled={
                      !assigned || pending || !reference.active || reference.category === null
                    }
                    value={assigned?.level ?? ''}
                    placeholder="Level"
                    onChange={(event) =>
                      setProfessions((current) =>
                        current.map((item) =>
                          item.profession_id === reference.id
                            ? {
                                ...item,
                                level:
                                  event.target.value === '' ? null : Number(event.target.value),
                              }
                            : item
                        )
                      )
                    }
                  />
                </div>
              );
            })}
        </fieldset>
      ))}
      {error != null && <ErrorNotice error={error} />}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : 'Save professions'}
        </Button>
        <Button type="button" variant="outline" disabled={pending} onClick={cancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function DungeonRow({
  dungeon,
  blud,
  references,
  editable,
  pending,
  save,
  draft,
  setDraft,
}: {
  dungeon: References['dungeons'][number];
  blud: Blud;
  references: References;
  editable: boolean;
  pending: boolean;
  save: (body: BludPatch, done: () => void) => void;
  draft: DungeonStatus | undefined;
  setDraft: (status: DungeonStatus | undefined) => void;
}) {
  const progress = blud.dungeons.find((item) => item.dungeon_id === dungeon.id);
  const status = progress?.status ?? 'not_completed';
  return (
    <li className="min-w-0 space-y-3 border-t py-4 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="break-words font-medium">{dungeon.name}</h3>
          <p className="text-sm text-muted-foreground">
            {dungeon.suggested_level_min != null && dungeon.suggested_level_max != null
              ? `Suggested levels ${dungeon.suggested_level_min}–${dungeon.suggested_level_max}`
              : 'Levels unknown'}
            {dungeon.location ? ` · ${dungeon.location}` : ''}
          </p>
        </div>
        <Badge
          variant={status === 'not_completed' ? 'outline' : 'secondary'}
          className="h-auto whitespace-normal"
        >
          {choiceName(references.dungeon_statuses, status)}
        </Badge>
      </div>
      <div className="flex flex-wrap gap-4 text-sm">
        {dungeon.guide_url && (
          <a
            className="text-primary underline"
            href={dungeon.guide_url}
            target="_blank"
            rel="noreferrer"
          >
            Dungeon guide<span className="sr-only"> for {dungeon.name}</span>
          </a>
        )}
        {dungeon.quest_guide_url && (
          <a
            className="text-primary underline"
            href={dungeon.quest_guide_url}
            target="_blank"
            rel="noreferrer"
          >
            Quest guide<span className="sr-only"> for {dungeon.name}</span>
          </a>
        )}
        <UpdatedAt value={progress?.updated_at ?? null} />
      </div>
      {editable && (dungeon.active || progress) && (
        <form
          className="flex min-w-0 flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            save({ dungeons: [{ dungeon_id: dungeon.id, status: draft ?? status }] }, () =>
              setDraft(undefined)
            );
          }}
        >
          <select
            aria-label={`${dungeon.name} status`}
            value={draft ?? status}
            disabled={pending}
            onChange={(event) => setDraft(event.target.value as DungeonStatus)}
            className="h-10 min-w-0 max-w-full flex-1 rounded-md border bg-background px-2 text-sm sm:flex-none"
          >
            {references.dungeon_statuses
              .filter(
                (choice) =>
                  dungeon.active || choice.id === status || choice.id === 'not_completed'
              )
              .map((choice) => (
                <option key={choice.id} value={choice.id}>
                  {choice.name}
                </option>
              ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            type="submit"
            disabled={pending || draft === undefined || draft === status}
          >
            Save<span className="sr-only"> {dungeon.name} status</span>
          </Button>
        </form>
      )}
    </li>
  );
}

export function BludDetails() {
  const actor = useAccount();
  const { bludId } = useParams();
  const id = Number(bludId);
  const validId = Number.isSafeInteger(id) && id > 0;
  const location = useLocation();
  const listSearch =
    typeof location.state?.listSearch === 'string' && location.state.listSearch.startsWith('?')
      ? location.state.listSearch
      : '';
  const references = useQuery(referencesOptions(actor.id));
  const query = useQuery({ ...bludOptions(actor.id, id), enabled: validId });
  const mutation = useMutation(updateOptions(useQueryClient(), actor.id, id));
  const [editing, setEditing] = useState(false);
  const [professionsEditing, setProfessionsEditing] = useState(false);
  const [correcting, setCorrecting] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [message, setMessage] = useState('');
  const [dungeonDrafts, setDungeonDrafts] = useState<Record<string, DungeonStatus>>({});
  function draftFor(dungeonId: string) {
    return {
      draft: dungeonDrafts[dungeonId],
      setDraft: (status: DungeonStatus | undefined) =>
        setDungeonDrafts((current) => {
          const next = { ...current };
          if (status === undefined) delete next[dungeonId];
          else next[dungeonId] = status;
          return next;
        }),
    };
  }
  function save(body: BludPatch, done: () => void = () => {}) {
    setMessage('');
    mutation.mutate(body, {
      onSuccess: () => {
        done();
        setMessage('Blud saved.');
      },
    });
  }
  const back = (
    <Link className="mb-5 inline-block text-sm text-primary" to={`/bluds${listSearch}`}>
      ← Bluds
    </Link>
  );
  if (!validId || (query.error instanceof ApiError && query.error.status === 404))
    return (
      <>
        {back}
        <PageTitle>Blud not found</PageTitle>
      </>
    );
  if (
    [query.error, references.error].some(
      (error) => error instanceof ApiError && error.status === 403
    )
  )
    return <Navigate to="/unauthorized" replace />;
  if (query.isPending || references.isPending) return <Loading label="Loading Blud…" />;
  if (!query.data || !references.data)
    return (
      <>
        {back}
        <ErrorNotice
          error={query.error ?? references.error}
          retry={() => {
            void query.refetch();
            void references.refetch();
          }}
        />
      </>
    );
  const blud = query.data;
  const refs = references.data;
  const own = blud.account_id === actor.id && actor.permissions.includes('bluds.edit_own');
  const canCorrect = actor.permissions.includes('shared_records.correct');
  const editable = own || (canCorrect && correcting);
  const activeDungeons = refs.dungeons.filter((d) => d.active);
  const retiredDungeons = refs.dungeons.filter(
    (d) => !d.active && blud.dungeons.some((p) => p.dungeon_id === d.id)
  );
  const bracketFor = (level: number | null) =>
    level == null ? -1 : Math.floor(level / 10) * 10;
  const brackets = [
    ...new Set(activeDungeons.map((d) => bracketFor(d.suggested_level_min))),
  ].sort((a, b) => a - b);
  return (
    <>
      {back}
      <PageTitle
        description={`${blud.owner_name} · ${choiceName(refs.classes, blud.class_id)}${blud.spec_id ? ` · ${choiceName(refs.classes.find((item) => item.id === blud.class_id)?.specs ?? [], blud.spec_id)}` : ''}`}
      >
        {blud.name}
      </PageTitle>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        {blud.archived && <Badge variant="outline">Archived</Badge>}
        <Badge variant="secondary">
          {blud.completed_dungeons}/{blud.total_dungeons} dungeons completed
        </Badge>
        <span className="text-sm text-muted-foreground">
          {blud.rerun_dungeons} looking to rerun
        </span>
      </div>
      {!own && canCorrect && (
        <div className="mb-5 space-y-2 rounded-xl border border-primary/30 p-4">
          <p className="text-sm">
            {correcting
              ? 'Officer correction: changes will be attributed to your account.'
              : 'This character belongs to another member.'}
          </p>
          <Button
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => {
              setCorrecting(!correcting);
              setEditing(false);
              setProfessionsEditing(false);
              mutation.reset();
            }}
          >
            {correcting ? 'Finish corrections' : 'Correct this Blud'}
          </Button>
        </div>
      )}
      {message && (
        <p role="status" className="mb-4 text-sm text-primary">
          {message}
        </p>
      )}
      {mutation.isError && <ErrorNotice error={mutation.error} />}
      {(query.isError || references.isError) && (
        <ErrorNotice
          error={query.error ?? references.error}
          retry={() => {
            void query.refetch();
            void references.refetch();
          }}
        />
      )}
      {editing && editable ? (
        <BludForm
          references={refs}
          initial={blud}
          pending={mutation.isPending}
          error={mutation.error}
          cancel={() => setEditing(false)}
          submit={(body) => save(body, () => setEditing(false))}
        />
      ) : (
        <section
          className="mb-5 space-y-4 rounded-xl border bg-card p-5"
          aria-label="Character details"
        >
          <h2 className="text-lg font-semibold">Character details</h2>
          <dl className="grid min-w-0 gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Character creation date</dt>
              <dd>
                <time dateTime={blud.character_created_on}>{blud.character_created_on}</time>
              </dd>
            </div>
          </dl>
          {editable && (
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() => {
                  mutation.reset();
                  setEditing(true);
                }}
              >
                Edit details
              </Button>
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() =>
                  blud.archived ? save({ archived: false }) : setConfirmArchive(true)
                }
              >
                {blud.archived ? 'Restore Blud' : 'Archive Blud'}
              </Button>
            </div>
          )}
        </section>
      )}
      <div className="my-5">
        {professionsEditing && editable ? (
          <ProfessionForm
            blud={blud}
            references={refs}
            pending={mutation.isPending}
            error={mutation.error}
            cancel={() => setProfessionsEditing(false)}
            save={(body) => save(body, () => setProfessionsEditing(false))}
          />
        ) : (
          <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="Professions">
            <h2 className="text-lg font-semibold">Professions</h2>
            {blud.professions.length ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {blud.professions.map((item) => (
                  <div key={item.profession_id} className="text-sm">
                    <p>
                      {choiceName(refs.professions, item.profession_id)} ·{' '}
                      {item.level ?? 'Level not set'}
                    </p>
                    <UpdatedAt value={item.updated_at} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No professions set.</p>
            )}
            {editable && (
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() => {
                  mutation.reset();
                  setProfessionsEditing(true);
                }}
              >
                Edit professions
              </Button>
            )}
          </section>
        )}
      </div>
      <section className="min-w-0 rounded-xl border bg-card p-5" aria-label="Dungeon progress">
        <details key={blud.blud_id} className="group">
          <summary className="flex min-w-0 cursor-pointer list-none flex-wrap items-center gap-3 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
            <h2 className="text-lg font-semibold">Dungeon progress</h2>
            <Badge variant="secondary">
              {blud.completed_dungeons}/{blud.total_dungeons} completed
            </Badge>
            <ChevronDown
              aria-hidden="true"
              className="ml-auto size-5 shrink-0 group-open:rotate-180"
            />
          </summary>
          <p className="mt-2 text-sm text-muted-foreground">
            Both completed states count toward your total. Choose “Completed — looking to rerun”
            to show the guild you’re keen to go again.
          </p>
          {!activeDungeons.length && (
            <p className="mt-4 text-sm text-muted-foreground">No dungeons available.</p>
          )}
          {brackets.map((bracket) => (
            <div key={bracket} className="mt-6 min-w-0">
              <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
                {bracket === -1 ? 'Levels unknown' : `Starting around level ${bracket}`}
              </h3>
              <ul className="min-w-0">
                {activeDungeons
                  .filter((item) => bracketFor(item.suggested_level_min) === bracket)
                  .map((dungeon) => (
                    <DungeonRow
                      key={dungeon.id}
                      dungeon={dungeon}
                      {...draftFor(dungeon.id)}
                      blud={blud}
                      references={refs}
                      editable={editable}
                      pending={mutation.isPending}
                      save={save}
                    />
                  ))}
              </ul>
            </div>
          ))}
          {retiredDungeons.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold">Previous dungeon progress</h3>
              <p className="text-sm text-muted-foreground">
                These dungeons are no longer available. Saved progress is retained.
              </p>
              <ul>
                {retiredDungeons.map((dungeon) => (
                  <DungeonRow
                    key={dungeon.id}
                    {...draftFor(dungeon.id)}
                    dungeon={dungeon}
                    blud={blud}
                    references={refs}
                    editable={editable}
                    pending={mutation.isPending}
                    save={save}
                  />
                ))}
              </ul>
            </div>
          )}
        </details>
      </section>
      <details className="mt-5 break-words text-sm text-muted-foreground">
        <summary className="cursor-pointer">Game references</summary>
        <p className="my-2">
          Game data is supplied by Blizzard. Suggested levels are guidance.
        </p>
        <ul className="space-y-2">
          {refs.sources.map((source) => (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noreferrer" className="underline">
                {source.label}
              </a>
            </li>
          ))}
        </ul>
      </details>
      <AlertDialog open={confirmArchive} onOpenChange={setConfirmArchive}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive {blud.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This hides the character from the default guild list. All progress is retained,
              and the owner or an officer can restore it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirmArchive(false);
                save({ archived: true });
              }}
            >
              Confirm archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
