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

    const clientId = Deno.env.get("FATHOM_CLIENT_ID")!;
    const clientSecret = Deno.env.get("FATHOM_CLIENT_SECRET")!;
    const redirectUri = `${Deno.env.get("SUPABASE_PUBLIC_URL")}/functions/v1/fathom-oauth-callback`;

    // Exchange code for tokens
    const tokenRes = await fetch("https://fathom.video/external/v1/oauth2/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });

    const tokens = await tokenRes.json();
    if (tokens.error) {
      throw new Error(tokens.error_description || tokens.error);
    }

    // Save to DB
    const supabase = getServiceClient();
    const { error } = await supabase.from("fathom_oauth_tokens").upsert(
      {
        user_id: userId,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: new Date(
          Date.now() + (tokens.expires_in || 3600) * 1000,
        ).toISOString(),
        updated_at: new Date().toISOString(),
      },
      { onConflict: "user_id" },
    );

    if (error) throw error;

    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(`${webappUrl}/settings?integration=fathom&status=success`, 302);
  } catch (e) {
    console.error("Fathom OAuth callback error:", e);
    const webappUrl = Deno.env.get("WEBAPP_URL") || "https://jarvis.squadd.it";
    return Response.redirect(
      `${webappUrl}/settings?integration=fathom&status=error&message=${encodeURIComponent(e.message)}`,
      302,
    );
  }
});
