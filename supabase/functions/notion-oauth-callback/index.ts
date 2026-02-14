import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";
import { getServiceClient } from "../_shared/supabase.ts";

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const url = new URL(req.url);
    const code = url.searchParams.get("code");
    const userId = url.searchParams.get("state");

    if (!code || !userId) {
      return new Response("Missing code or state", { status: 400 });
    }

    const clientId = Deno.env.get("NOTION_OAUTH_CLIENT_ID")!;
    const clientSecret = Deno.env.get("NOTION_OAUTH_CLIENT_SECRET")!;
    const redirectUri = `${Deno.env.get("SUPABASE_URL")}/functions/v1/notion-oauth-callback`;

    // Exchange code for access token
    const tokenRes = await fetch("https://api.notion.com/v1/oauth/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Basic ${btoa(`${clientId}:${clientSecret}`)}`,
      },
      body: JSON.stringify({
        grant_type: "authorization_code",
        code,
        redirect_uri: redirectUri,
      }),
    });

    const tokens = await tokenRes.json();
    if (tokens.error) {
      throw new Error(tokens.error_description || tokens.error);
    }

    // Save to DB
    const supabase = getServiceClient();
    const { error } = await supabase.from("notion_accounts").upsert(
      {
        user_id: userId,
        workspace_name: tokens.workspace_name || null,
        workspace_id: tokens.workspace_id || null,
        access_token: tokens.access_token,
        bot_id: tokens.bot_id || null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "user_id,workspace_id" },
    );

    if (error) throw error;

    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(`${webappUrl}/settings?integration=notion&status=success`, 302);
  } catch (e) {
    console.error("Notion OAuth callback error:", e);
    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(
      `${webappUrl}/settings?integration=notion&status=error&message=${encodeURIComponent(e.message)}`,
      302,
    );
  }
});
