import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { PageTitle } from './patterns';
import { AuthFrame } from '@/features/auth/auth-frame';

export function NotFound() {
  return (
    <AuthFrame>
      <PageTitle description="This page could not be found.">Page not found</PageTitle>
      <Button asChild>
        <Link to="/">Back to Bluddit</Link>
      </Button>
    </AuthFrame>
  );
}
