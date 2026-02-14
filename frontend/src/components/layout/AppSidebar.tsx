import { NavLink } from "react-router-dom";
import {
  MessageSquare,
  LayoutDashboard,
  Calendar,
  Mail,
  CheckSquare,
  BookOpen,
  BarChart3,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";

const navItems = [
  { icon: MessageSquare, label: "Chat", to: "/chat" },
  { icon: LayoutDashboard, label: "Dashboard", to: "/dashboard" },
  { icon: Calendar, label: "Calendario", to: "/calendar" },
  { icon: Mail, label: "Email", to: "/email" },
  { icon: CheckSquare, label: "Task", to: "/tasks" },
  { icon: BookOpen, label: "Knowledge", to: "/knowledge" },
  { icon: BarChart3, label: "Costi", to: "/costs" },
  { icon: Settings, label: "Impostazioni", to: "/settings" },
];

export default function AppSidebar() {
  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="p-4">
        <div className="flex items-center gap-2">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-lg font-bold text-primary">
            J
          </span>
          <span className="truncate text-sm font-semibold group-data-[collapsible=icon]:hidden">
            Jarvis
          </span>
        </div>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild tooltip={item.label}>
                    <NavLink
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-2",
                          isActive && "text-primary glass-selected rounded-md"
                        )
                      }
                    >
                      <item.icon className="size-4 shrink-0" />
                      <span>{item.label}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarSeparator />

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Account">
              <div className="flex items-center gap-2">
                <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                  R
                </div>
                <span className="truncate text-sm group-data-[collapsible=icon]:hidden">
                  Roberto
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Esci">
              <LogOut className="size-4 shrink-0" />
              <span>Esci</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
