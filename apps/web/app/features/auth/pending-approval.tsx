import { CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { PageTitle } from '@/components/patterns';
import { AuthFrame } from './auth-frame';

export function PendingApproval() {
  return (
    <AuthFrame>
      <CheckCircle2 className="mb-6 size-10 text-primary" />
      <PageTitle description="An officer needs to approve your account before you can log in. Contact a guild officer if you need help.">
        Awaiting approval
      </PageTitle>
      <p className="mb-6 text-sm text-muted-foreground">
        After approval, continue with Battle.net to sign in.
      </p>
      <Button asChild className="w-full rounded-full">
        <Link to="/login">Back to login</Link>
      </Button>
    </AuthFrame>
  );
}
