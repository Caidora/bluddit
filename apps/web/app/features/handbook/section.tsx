import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { editOptions, revisionsOptions, sectionOptions, sectionsOptions } from './queries';
import { SectionForm } from './section-form';
import type { HandbookSection } from './types';

export function Attribution({ section }: { section: HandbookSection }) {
  return (
    <p className="my-3 [overflow-wrap:anywhere] text-sm text-muted-foreground">
      Revision {section.revision} · {new Date(section.updated_at).toLocaleString()} ·{' '}
      {section.author_name} (account #{section.author_account_id})
    </p>
  );
}

export function HandbookSectionPage() {
  const { slug = '' } = useParams();
  return <Section key={slug} slug={slug} />;
}

function Section({ slug }: { slug: string }) {
  const actor = useAccount();
  const query = useQuery(sectionOptions(actor.id, slug));
  const navigation = useQuery(sectionsOptions(actor.id));
  const mutation = useMutation(editOptions(useQueryClient(), actor.id, slug));
  const [draft, setDraft] = useState<HandbookSection | null>(null);
  const [history, setHistory] = useState(false);
  const [saved, setSaved] = useState(false);
  const editor = actor.permissions.includes('handbook.edit');
  if (query.isPending) return <Loading label="Loading section…" />;
  if (query.isError && !query.data)
    return (
      <>
        <Link to="/handbook" className="underline">
          Back to handbook
        </Link>
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      </>
    );
  const section = query.data!;
  return (
    <div className="[overflow-wrap:anywhere]">
      <Link to="/handbook" className="mb-4 inline-block text-sm text-primary underline">
        Back to handbook
      </Link>
      <PageTitle>{section.title}</PageTitle>
      <nav
        aria-label="Other handbook sections"
        className="mb-6 flex flex-wrap gap-x-4 gap-y-2 text-sm"
      >
        {navigation.data?.map((item) => (
          <Link
            key={item.slug}
            to={`/handbook/${item.slug}`}
            aria-current={item.slug === slug ? 'page' : undefined}
            className="text-primary underline"
          >
            {item.title}
          </Link>
        ))}
      </nav>
      {query.isError && (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      )}
      <Attribution section={section} />
      <article className="max-w-3xl whitespace-pre-wrap [overflow-wrap:anywhere] leading-relaxed">
        {section.body}
      </article>
      {saved && (
        <p role="status" className="mt-4">
          Revision saved.
        </p>
      )}
      {editor && (
        <div className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={draft !== null}
              onClick={() => {
                mutation.reset();
                setSaved(false);
                setDraft(section);
              }}
            >
              Edit section
            </Button>
            <Button variant="outline" onClick={() => setHistory(!history)}>
              {history ? 'Hide revisions' : 'View revisions'}
            </Button>
          </div>
          {draft && (
            <SectionForm
              key={draft.revision}
              section={draft}
              pending={mutation.isPending}
              error={mutation.error}
              cancel={() => setDraft(null)}
              submit={({ title, body }) =>
                mutation.mutate(
                  { expected_revision: draft.revision, title, body },
                  {
                    onSuccess: () => {
                      setDraft(null);
                      setSaved(true);
                    },
                  }
                )
              }
            />
          )}
          {history && <History slug={slug} />}
        </div>
      )}
    </div>
  );
}

function History({ slug }: { slug: string }) {
  const actor = useAccount();
  const [offset, setOffset] = useState(0);
  const query = useQuery(revisionsOptions(actor.id, slug, offset));
  return (
    <section aria-label="Revision history" className="space-y-4">
      <h2 className="text-xl font-semibold">Revision history</h2>
      {query.isPending ? (
        <Loading label="Loading revisions…" />
      ) : query.isError ? (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      ) : (
        <>
          {query.data.length === 0 && <p>No more revisions.</p>}
          {query.data.map((item) => (
            <details key={item.revision} className="rounded-md border p-4">
              <summary className="cursor-pointer [overflow-wrap:anywhere]">
                Revision {item.revision}: {item.title}
              </summary>
              <Attribution section={item} />
              <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{item.body}</p>
            </details>
          ))}
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              disabled={offset === 0 || query.isFetching}
              onClick={() => setOffset(Math.max(0, offset - 10))}
            >
              Newer revisions
            </Button>
            <Button
              variant="outline"
              disabled={query.data.length < 10 || query.isFetching}
              onClick={() => setOffset(offset + 10)}
            >
              Older revisions
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
