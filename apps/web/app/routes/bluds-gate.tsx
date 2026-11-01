import { CapabilityGate } from '@/components/session';
export default function BludsGate() {
  return <CapabilityGate permission="bluds.view" />;
}
