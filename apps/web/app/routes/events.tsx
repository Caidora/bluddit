import { Link } from 'react-router';
import { FeaturePlaceholder } from '@/components/feature-placeholder';
import { destinations } from '@/navigation';

export default function Page() {
  return (
    <>
      <FeaturePlaceholder destination={destinations.events} />
      <nav
        aria-label="Related handbook guidance"
        className="mt-6 flex flex-wrap gap-4 text-primary underline"
      >
        <Link to="/handbook?q=scheduling">Scheduling guidance</Link>
        <Link to="/handbook?q=loot">Loot guidance</Link>
      </nav>
    </>
  );
}
