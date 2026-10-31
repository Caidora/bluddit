import { FeaturePlaceholder } from '@/components/feature-placeholder';
import { destinations } from '@/navigation';

export default function Page() {
  return <FeaturePlaceholder destination={destinations.events} />;
}
