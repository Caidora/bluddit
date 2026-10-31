import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { ErrorNotice } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { accountActionOptions } from './queries';
import type { Account, AccountAction } from './types';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog';

const actionLabels: Record<AccountAction, string> = {
  approve: 'Approve membership',
  reject: 'Reject application',
  deactivate: 'Deactivate account',
  activate: 'Activate account',
  'promote-to-officer': 'Promote to Officer',
  'demote-to-member': 'Demote to Member',
  'pass-guild-master': 'Pass Guild Master',
};
export function AccountControls({ target }: { target: Account }) {
  const actor = useAccount();
  const client = useQueryClient();
  const mutation = useMutation(accountActionOptions(client, actor.id, target.id));
  const [confirmation, setConfirmation] = useState<AccountAction | null>(null);
  const [completed, setCompleted] = useState('');
  const actions: AccountAction[] = [];
  if (target.role_name !== 'guild_master') {
    if (target.membership_state === 'pending') actions.push('approve', 'reject');
    else if (target.membership_state === 'active') actions.push('deactivate');
    else actions.push('activate');
    if (actor.role_name === 'guild_master' && actor.id !== target.id) {
      if (target.role_name === 'member') actions.push('promote-to-officer');
      if (target.role_name === 'officer') actions.push('demote-to-member');
      if (target.membership_state === 'active') actions.push('pass-guild-master');
    }
  }
  function act(action: AccountAction) {
    setCompleted('');
    mutation.mutate(action, {
      onSuccess: () => setCompleted(`${actionLabels[action]} completed.`),
    });
  }
  return (
    <div className="mt-6">
      <h2 className="mb-3 text-lg font-semibold">Account actions</h2>
      {target.role_name === 'guild_master' && (
        <p className="text-sm text-muted-foreground">
          The Guild Master is protected. Only the current GM can pass the role to another active
          account.
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        {actions.map((action) => (
          <Button
            key={action}
            variant={action === 'approve' || action === 'activate' ? 'default' : 'outline'}
            disabled={mutation.isPending}
            onClick={() =>
              action === 'approve' || action === 'activate' ? act(action) : setConfirmation(action)
            }
          >
            {actionLabels[action]}
          </Button>
        ))}
      </div>
      {mutation.isPending && (
        <p role="status" className="mt-3 text-sm">
          Updating and refreshing account…
        </p>
      )}
      {completed && (
        <p role="status" className="mt-3 text-sm text-primary">
          {completed}
        </p>
      )}
      {mutation.isError && <ErrorNotice error={mutation.error} />}
      <AlertDialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmation(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmation && actionLabels[confirmation]}?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmation === 'pass-guild-master'
                ? `Transfer leadership to ${target.display_name}? You will become an Officer and lose GM-only controls.`
                : `This will change access for ${target.display_name} (${target.username}). Confirm that this is the intended account.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmation) act(confirmation);
                setConfirmation(null);
              }}
            >
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
