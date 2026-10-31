import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { PageTitle } from '@/components/patterns';
import { AuthFrame } from './auth-frame';

export function Unauthorized() {
  return (
    <AuthFrame>
      <PageTitle description="Your account does not have permission to open this page.">
        Access restricted
      </PageTitle>
      <Button asChild>
        <Link to="/home">Back to home</Link>
      </Button>
    </AuthFrame>
  );
}
