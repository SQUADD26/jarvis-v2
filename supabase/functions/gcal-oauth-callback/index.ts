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

    // Exchange code for tokens
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: Deno.env.get("GOOGLE_CLIENT_ID")!,
        client_secret: Deno.env.get("GOOGLE_CLIENT_SECRET")!,
        redirect_uri: `${Deno.env.get("SUPABASE_URL")}/functions/v1/gcal-oauth-callback`,
        grant_type: "authorization_code",
      }),
    });

    const tokens = await tokenRes.json();
    if (tokens.error) {
      throw new Error(tokens.error_description || tokens.error);
    }

    // Get user email from Google
    const profileRes = await fetch(
      "https://www.googleapis.com/oauth2/v2/userinfo",
      { headers: { Authorization: `Bearer ${tokens.access_token}` } },
    );
    const profile = await profileRes.json();

    // Save to DB
    const supabase = getServiceClient();
    const { error } = await supabase.from("google_calendar_accounts").upsert(
      {
        user_id: userId,
        email: profile.email,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: new Date(
          Date.now() + tokens.expires_in * 1000,
        ).toISOString(),
        scopes: tokens.scope?.split(" ") ?? [],
        updated_at: new Date().toISOString(),
      },
      { onConflict: "user_id,email" },
    );

    if (error) throw error;

    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(`${webappUrl}/settings?integration=gcal&status=success`, 302);
  } catch (e) {
    console.error("GCal OAuth callback error:", e);
    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(
      `${webappUrl}/settings?integration=gcal&status=error&message=${encodeURIComponent(e.message)}`,
      302,
    );
  }
});
