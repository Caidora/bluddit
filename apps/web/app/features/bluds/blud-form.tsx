import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ErrorNotice } from '@/components/patterns';
import { SelectField } from './fields';
import type { BludContent, References } from './types';

export function BludForm({
  references: currentReferences,
  initial,
  pending,
  error,
  submit,
  cancel,
}: {
  references: References;
  initial?: BludContent;
  pending: boolean;
  error: unknown;
  submit: (body: BludContent) => void;
  cancel: () => void;
}) {
  const [references] = useState(currentReferences);
  const [name, setName] = useState(initial?.name ?? '');
  const [classId, setClassId] = useState(initial?.class_id ?? '');
  const [specId, setSpecId] = useState(initial?.spec_id ?? '');
  const [createdOn, setCreatedOn] = useState(initial?.character_created_on ?? '');
  function save(event: FormEvent) {
    event.preventDefault();
    submit({
      name: name.trim(),
      class_id: classId,
      spec_id: specId || null,
      character_created_on: createdOn,
    });
  }
  return (
    <form onSubmit={save} className="space-y-4 rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">{initial ? 'Character details' : 'New Blud'}</h2>
      <div className="space-y-2">
        <Label htmlFor="blud-name">Character name</Label>
        <Input
          id="blud-name"
          required
          maxLength={100}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="grid min-w-0 gap-4 sm:grid-cols-2">
        <SelectField
          label="Class"
          choices={references.classes.filter((c) => c.active || c.id === initial?.class_id)}
          empty="Choose a class"
          required
          value={classId}
          onChange={(event) => {
            setClassId(event.target.value);
            setSpecId('');
          }}
        />
        <SelectField
          label="Spec"
          choices={(references.classes.find((item) => item.id === classId)?.specs ?? []).filter(
            (s) => s.active || s.id === initial?.spec_id
          )}
          value={specId}
          onChange={(event) => setSpecId(event.target.value)}
        />
        <div className="min-w-0 space-y-2">
          <Label htmlFor="blud-created">Character creation date</Label>
          <Input
            className="min-w-0"
            id="blud-created"
            type="date"
            required
            value={createdOn}
            onChange={(event) => setCreatedOn(event.target.value)}
          />
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Enter the date you created the character in game. Spec can stay blank.
      </p>
      {error != null && <ErrorNotice error={error} />}
      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          disabled={
            pending ||
            !name.trim() ||
            !classId ||
            !createdOn ||
            (!initial && !references.classes.some((c) => c.active))
          }
        >
          {pending ? 'Saving…' : initial ? 'Save details' : 'Create Blud'}
        </Button>
        <Button type="button" variant="outline" disabled={pending} onClick={cancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
