import { useLocation } from 'react-router';
import { PageTitle, EmptyState } from '@/components/patterns';
import { destinations } from '@/components/shell';
import { useAccount } from '@/components/session';
import { Badge } from '@/components/ui/badge';

export default function FeaturePlaceholder() {
  const location = useLocation();
  const account = useAccount();
  const destination =
    destinations.find((item) => item.path === location.pathname) ?? destinations[0];
  return (
    <>
      <div className="mb-5 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="size-2 rounded-full bg-primary" /> BLUDS GUILD{' '}
        <span className="mx-1">/</span> {destination.label.toUpperCase()}
      </div>
      <PageTitle description={destination.description}>
        {destination.label === 'Home' ? `Welcome, ${account.display_name}` : destination.label}
      </PageTitle>
      <EmptyState
        title={`${destination.label === 'Home' ? 'Your member home is' : destination.label + ' is'} taking shape`}
      >
        <p>
          These member tools are coming in a future update. You’re in the right place — there’s
          nothing to set up here yet.
        </p>
      </EmptyState>
      <div className="mt-6 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <Badge variant="outline">Member access</Badge>
        <span>Good company. Shared progress.</span>
      </div>
    </>
  );
}
