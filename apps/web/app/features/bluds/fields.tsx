import { useId, type ComponentProps } from 'react';
import { Label } from '@/components/ui/label';
import type { Choice } from './types';

export function SelectField({
  label,
  choices,
  empty = 'Not set',
  ...props
}: {
  label: string;
  choices: Choice[];
  empty?: string;
} & ComponentProps<'select'>) {
  const id = useId();
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        className="h-10 w-full min-w-0 rounded-md border border-input bg-background px-3 text-sm"
        {...props}
      >
        <option value="">{empty}</option>
        {choices.map((choice) => (
          <option key={choice.id} value={choice.id}>
            {choice.name}
          </option>
        ))}
      </select>
    </div>
  );
}
export function choiceName(choices: Choice[], id: string | null) {
  return id ? (choices.find((choice) => choice.id === id)?.name ?? id) : 'Not set';
}
export function UpdatedAt({ value }: { value: string | null }) {
  return value ? (
    <span className="text-xs text-muted-foreground">
      Updated <time dateTime={value}>{new Date(value).toLocaleString()}</time>
    </span>
  ) : null;
}
