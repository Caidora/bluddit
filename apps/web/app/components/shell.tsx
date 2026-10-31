import { Link, NavLink, Outlet } from 'react-router';
import {
  Home,
  Users,
  Crosshair,
  CalendarDays,
  Hammer,
  BookOpen,
  ShieldCheck,
  KeyRound,
  LogOut,
} from 'lucide-react';
import {
  Sidebar,
  SidebarProvider,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarTrigger,
  SidebarInset,
  useSidebar,
} from '@/components/ui/sidebar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Brand } from './patterns';
import { useAccount } from './session';

export const destinations = [
  { path: '/home', label: 'Home', icon: Home, description: 'Your guild, all in one place.' },
  {
    path: '/roster',
    label: 'Roster & Squads',
    icon: Users,
    description: 'Find your people and build a balanced group.',
  },
  {
    path: '/gear',
    label: 'Gear & Farming',
    icon: Crosshair,
    description: 'Plan upgrades and make each run count.',
  },
  {
    path: '/events',
    label: 'Events',
    icon: CalendarDays,
    description: 'Good runs start with a plan.',
  },
  {
    path: '/crafting',
    label: 'Crafting Directory',
    icon: Hammer,
    description: 'Find the right hands for the job.',
  },
  {
    path: '/handbook',
    label: 'Guild Handbook',
    icon: BookOpen,
    description: 'How we progress together and keep it friendly.',
  },
];
function Navigation() {
  const account = useAccount();
  const { setOpenMobile } = useSidebar();
  const items = [
    ...destinations,
    ...(account.permissions.includes('accounts.manage')
      ? [{ path: '/admin/accounts', label: 'Membership', icon: ShieldCheck }]
      : []),
    ...(account.permissions.includes('policy.read')
      ? [{ path: '/admin/permissions', label: 'Permissions', icon: KeyRound }]
      : []),
  ];
  return (
    <Sidebar collapsible="offcanvas" className="top-16 h-[calc(100svh-4rem)]">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="my-3 uppercase tracking-widest">
            Your guild
          </SidebarGroupLabel>
          <SidebarMenu>
            {items.map((item) => (
              <SidebarMenuItem key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.path === '/home'}
                  onClick={() => setOpenMobile(false)}
                >
                  {({ isActive }) => (
                    <SidebarMenuButton asChild isActive={isActive} className="h-11">
                      <span>
                        <item.icon />
                        <span>{item.label}</span>
                      </span>
                    </SidebarMenuButton>
                  )}
                </NavLink>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 p-5">
        <Separator />
        <p className="text-xs leading-relaxed text-muted-foreground">
          AU · NZ · PERTH
          <br />
          Progress together. Keep it friendly.
        </p>
      </SidebarFooter>
    </Sidebar>
  );
}
export function Shell() {
  const account = useAccount();
  return (
    <SidebarProvider className="pt-16">
      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between gap-2 border-b bg-background px-3 sm:px-6">
        <div className="flex items-center gap-3">
          <SidebarTrigger aria-label="Toggle navigation" />
          <Link to="/home" aria-label="Bluddit home">
            <Brand />
          </Link>
          <Separator orientation="vertical" className="hidden h-6 sm:block" />
          <span className="hidden text-sm text-muted-foreground sm:block">Bluds guild</span>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <span className="hidden max-w-40 truncate text-sm sm:block">{account.display_name}</span>
          <Badge variant="secondary" className="hidden md:inline-flex">
            {account.role_name.replaceAll('_', ' ')}
          </Badge>
          <Button asChild variant="ghost" size="sm">
            <Link to="/logout">
              <LogOut className="size-4" />
              <span>Log out</span>
            </Link>
          </Button>
        </div>
      </header>
      <Navigation />
      <SidebarInset className="min-w-0">
        <main id="main-content" className="mx-auto w-full max-w-5xl p-4 sm:p-8 lg:p-10">
          <Outlet context={account} />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
export default Shell;
