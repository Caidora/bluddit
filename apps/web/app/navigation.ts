import { Home, Users, Crosshair, CalendarDays, Hammer, BookOpen } from 'lucide-react';

export const destinations = {
  home: { path: '/home', label: 'Home', icon: Home, description: 'Your guild, all in one place.' },
  bluds: {
    path: '/bluds',
    label: 'Bluds',
    icon: Users,
    description: 'Your guild’s characters, professions, and dungeon progress.',
  },
  gear: {
    path: '/gear',
    label: 'Gear & Farming',
    icon: Crosshair,
    description: 'Plan upgrades and make each run count.',
  },
  events: {
    path: '/events',
    label: 'Events',
    icon: CalendarDays,
    description: 'Good runs start with a plan.',
  },
  crafting: {
    path: '/crafting',
    label: 'Crafting Directory',
    icon: Hammer,
    description: 'Find the right hands for the job.',
  },
  handbook: {
    path: '/handbook',
    label: 'Guild Handbook',
    icon: BookOpen,
    description: 'How we progress together and keep it friendly.',
  },
} as const;

export type MemberDestination = (typeof destinations)[keyof typeof destinations];
