import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import App from "./App";
import "@/styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <App />
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: {
              background: "oklch(0.178 0 0)",
              border: "1px solid oklch(1 0 0 / 0.06)",
              color: "oklch(0.985 0 0)",
            },
          }}
        />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
