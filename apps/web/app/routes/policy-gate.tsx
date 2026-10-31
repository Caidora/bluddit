import { CapabilityGate } from '@/components/session';
export default function PolicyGate() {
  return <CapabilityGate permission="policy.read" />;
}
