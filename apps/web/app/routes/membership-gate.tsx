import { CapabilityGate } from '@/components/session';
export default function MembershipGate() {
  return <CapabilityGate permission="accounts.manage" />;
}
