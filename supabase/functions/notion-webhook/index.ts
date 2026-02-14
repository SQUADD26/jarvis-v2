import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";
import { getServiceClient } from "../_shared/supabase.ts";

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Notion sends a verification request on webhook setup
  if (req.method === "GET") {
    return new Response("ok", { status: 200 });
  }

  try {
    const body = await req.json();
    const supabase = getServiceClient();

    // Log the webhook event
    console.log("Notion webhook event:", JSON.stringify(body).slice(0, 500));

    const eventType = body.type;

    // Handle different Notion event types
    switch (eventType) {
      case "page.created":
      case "page.content_updated":
      case "page.properties_updated":
      case "page.deleted":
      case "page.undeleted": {
        // Find the user linked to this Notion workspace
        const workspaceId = body.workspace_id;
        if (!workspaceId) break;

        const { data: account } = await supabase
          .from("notion_accounts")
          .select("user_id")
          .eq("workspace_id", workspaceId)
          .limit(1)
          .single();

        if (account) {
          // Enqueue a task for the worker to process the update
          await supabase.from("task_queue").insert({
            user_id: account.user_id,
            task_type: "notion_webhook_event",
            payload: {
              event_type: eventType,
              page_id: body.data?.id || body.entity?.id,
              workspace_id: workspaceId,
              timestamp: body.timestamp,
            },
            status: "pending",
            priority: 5,
          });

          console.log(
            `Queued ${eventType} for user ${account.user_id}, page ${body.data?.id || body.entity?.id}`,
          );
        }
        break;
      }

      default:
        console.log(`Unhandled Notion webhook event: ${eventType}`);
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("Notion webhook error:", e);
    // Always return 200 to avoid Notion retrying
    return new Response(JSON.stringify({ error: e.message }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
});
