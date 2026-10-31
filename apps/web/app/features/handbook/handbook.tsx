import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading, EmptyState } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { createOptions, sectionsOptions } from './queries';
import { SectionForm } from './section-form';
import { Attribution } from './section';

export function Handbook() {
  const actor = useAccount();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = (params.get('q') ?? '').slice(0, 200);
  const query = useQuery(sectionsOptions(actor.id, q));
  const create = useMutation(createOptions(useQueryClient(), actor.id));
  const [creating, setCreating] = useState(false);
  const editor = actor.permissions.includes('handbook.edit');
  return (
    <>
      <PageTitle description="Guild rules, shared expectations, and useful contacts.">
        Guild Handbook
      </PageTitle>
      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const search = String(new FormData(event.currentTarget).get('q') ?? '').trim();
          setParams(search ? { q: search } : {});
        }}
      >
        <div className="min-w-0 flex-1">
          <Label htmlFor="handbook-search">Search the handbook</Label>
          <Input
            key={q}
            id="handbook-search"
            name="q"
            type="search"
            maxLength={200}
            defaultValue={q}
          />
        </div>
        <Button type="submit">Search</Button>
        {q && (
          <Button type="button" variant="outline" onClick={() => setParams({})}>
            Clear search
          </Button>
        )}
      </form>
      {editor && (
        <div className="mb-6 space-y-4">
          <Button
            disabled={creating}
            onClick={() => {
              create.reset();
              setCreating(true);
            }}
          >
            Add section
          </Button>
          {creating && (
            <SectionForm
              pending={create.isPending}
              error={create.error}
              cancel={() => setCreating(false)}
              submit={(content) =>
                create.mutate(content, {
                  onSuccess: (section) => {
                    void navigate(`/handbook/${section.slug}`);
                  },
                })
              }
            />
          )}
        </div>
      )}
      {query.isPending ? (
        <Loading label="Loading handbook…" />
      ) : query.isError ? (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      ) : query.data.length === 0 ? (
        <EmptyState title={q ? 'No matching sections' : 'No handbook sections yet'}>
          {q
            ? 'Try a different search.'
            : editor
              ? 'Add a section to publish the guild’s guidance.'
              : 'Officers will publish guild guidance here.'}
        </EmptyState>
      ) : (
        <nav aria-label="Handbook sections" className="grid gap-4 md:grid-cols-2">
          {query.data.map((section) => (
            <Card key={section.slug} className="min-w-0">
              <CardContent className="p-5">
                <Link
                  to={`/handbook/${section.slug}`}
                  className="[overflow-wrap:anywhere] text-lg font-semibold text-primary underline underline-offset-4"
                >
                  {section.title}
                </Link>
                <Attribution section={section} />
                <p className="line-clamp-3 [overflow-wrap:anywhere] text-sm text-muted-foreground">
                  {section.body}
                </p>
              </CardContent>
            </Card>
          ))}
        </nav>
      )}
    </>
  );
}
