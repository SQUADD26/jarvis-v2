import { createContext, useContext } from "react";
import { Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import AppSidebar from "@/components/layout/AppSidebar";

export type LayoutMode = "custom" | "fullscreen" | "standard";

type LayoutContextValue = {
  mode: LayoutMode;
  setMode: (mode: LayoutMode) => void;
};

const LayoutContext = createContext<LayoutContextValue>({
  mode: "standard",
  setMode: () => {},
});

export function useLayoutMode() {
  return useContext(LayoutContext);
}

import { useState } from "react";

export default function AppLayout() {
  const [mode, setMode] = useState<LayoutMode>("standard");

  const mainClassName = cn(
    "flex-1 overflow-auto",
    mode === "custom" && "h-full",
    mode === "fullscreen" && "p-2",
    mode === "standard" && "p-6 lg:p-8 max-w-7xl mx-auto"
  );

  return (
    <LayoutContext.Provider value={{ mode, setMode }}>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border/40 px-4 md:hidden">
            <SidebarTrigger />
          </header>
          <div className={mainClassName}>
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </LayoutContext.Provider>
  );
}
