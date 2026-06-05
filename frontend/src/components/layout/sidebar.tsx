"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Shield,
  Plug,
  ScrollText,
  BarChart3,
  Lock,
  ListTodo,
  KeyRound,
  ServerCog,
  HeartPulse,
  Users,
  FileKey2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useUserRole } from "@/hooks/useUserRole";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/agents", label: "Agents", icon: Bot },
  { href: "/dashboard/policies", label: "Policies", icon: Shield },
  { href: "/dashboard/services", label: "Services", icon: Plug },
  { href: "/dashboard/audit", label: "Audit Trail", icon: ScrollText },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/vault", label: "Vault", icon: Lock },
  { href: "/dashboard/delegation", label: "Delegation", icon: KeyRound },
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
];

const ADMIN_NAV_ITEMS: NavItem[] = [
  { href: "/dashboard/admin/services", label: "Service Catalog", icon: ServerCog },
  { href: "/dashboard/admin/health", label: "Health & Emergency", icon: HeartPulse },
  { href: "/dashboard/admin/agents", label: "Agent Fleet", icon: Users },
  { href: "/dashboard/admin/delegations", label: "Delegations", icon: FileKey2 },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isAdmin } = useUserRole();

  return (
    <aside className="flex w-64 flex-col border-r bg-muted/40">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
          <Shield className="h-5 w-5" />
          <span>DeepSecure</span>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Button
              key={item.href}
              variant={isActive ? "secondary" : "ghost"}
              className={cn("w-full justify-start gap-3")}
              asChild
            >
              <Link href={item.href}>
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            </Button>
          );
        })}

        {isAdmin && (
          <>
            <Separator className="my-3" />
            <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Admin
            </p>
            {ADMIN_NAV_ITEMS.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Button
                  key={item.href}
                  variant={isActive ? "secondary" : "ghost"}
                  className={cn("w-full justify-start gap-3")}
                  asChild
                >
                  <Link href={item.href}>
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                </Button>
              );
            })}
          </>
        )}
      </nav>
    </aside>
  );
}
