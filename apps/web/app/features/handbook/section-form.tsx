import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { ErrorNotice } from '@/components/patterns';
import { ApiError } from '@/lib/http';
import type { HandbookCreate, HandbookSection } from './types';

export function SectionForm({
  section,
  pending,
  error,
  submit,
  cancel,
}: {
  section?: HandbookSection;
  pending: boolean;
  error: unknown;
  submit: (content: HandbookCreate) => void;
  cancel: () => void;
}) {
  const [slug, setSlug] = useState(section?.slug ?? '');
  const [title, setTitle] = useState(section?.title ?? '');
  const [body, setBody] = useState(section?.body ?? '');
  const conflict = !!section && error instanceof ApiError && error.status === 409;
  function save(event: FormEvent) {
    event.preventDefault();
    submit({ slug: slug.trim(), title: title.trim(), body: body.trim() });
  }
  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <h2 className="font-semibold">
          {section ? `Editing revision ${section.revision}` : 'New handbook section'}
        </h2>
        <p className="text-sm text-muted-foreground">
          Content uses Markdown. Every save publishes immediately and keeps the previous revision.
        </p>
        <form onSubmit={save} className="space-y-4">
          {!section && (
            <div className="space-y-2">
              <Label htmlFor="section-slug">URL slug</Label>
              <Input
                id="section-slug"
                required
                maxLength={80}
                pattern="[a-z][a-z0-9-]{0,79}"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                aria-describedby="slug-help"
              />
              <p id="slug-help" className="text-sm text-muted-foreground">
                Start with a lowercase letter; use lowercase letters, numbers, and hyphens. This URL
                stays fixed.
              </p>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="section-title">Title</Label>
            <Input
              id="section-title"
              required
              maxLength={160}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="section-body">Section text</Label>
            <textarea
              id="section-body"
              required
              maxLength={30000}
              rows={12}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full min-w-0 rounded-md border bg-background p-3 text-base"
              aria-describedby="section-body-help"
            />
            <p id="section-body-help" className="text-sm text-muted-foreground">
              Use ## Heading, **bold**, - list items, and [link text](https://example.com).
              Tables and task lists are supported. Separate paragraphs with a blank line.
              HTML is displayed as text.
            </p>
          </div>
          {error != null && <ErrorNotice error={error} />}
          {conflict && (
            <p className="text-sm">
              Your draft is retained above. Copy it before cancelling; reopen the editor to use the
              latest revision.
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={pending || conflict || !title.trim() || !body.trim()}>
              {pending ? 'Saving…' : section ? 'Save revision' : 'Create section'}
            </Button>
            <Button variant="outline" type="button" disabled={pending} onClick={cancel}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
