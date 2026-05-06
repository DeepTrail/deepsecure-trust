"use client";

import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

export function Header() {
  const handleLogout = async () => {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/api/auth/logout";
    document.body.appendChild(form);
    form.submit();
  };

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div />
      <Button variant="ghost" size="sm" className="gap-2" onClick={handleLogout}>
        <LogOut className="h-4 w-4" />
        Sign out
      </Button>
    </header>
  );
}
