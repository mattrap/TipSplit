# TipSplit Desktop Authentication Demo

This project adds a Supabase-backed sign-in flow to the TipSplit desktop client. Users authenticate with email and password, and access is controlled by row-level security on the `public.user_profiles` table.

## Prerequisites
- Python 3.10+
- A Supabase project with the `user_profiles` table and policies described in this repository

## Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the sample environment file and provide your Supabase project details:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `APP_NAME`.
4. Start the desktop client:
   ```bash
   python main.py
   ```

## Security Model
- The desktop client **only** uses the Supabase anon key. The Supabase service role key is never bundled with the application.
- Row Level Security policies on `public.user_profiles` restrict users to their own row and only when `is_active = true`.
- The application verifies the profile immediately after login and on demand from the main window. If the owner disables a user by setting `is_active = false`, the profile read fails and the client logs the user out with a clear message.
- All database reads go through the Supabase REST API, respecting the defined RLS policies.

## Troubleshooting
- **Invalid email or password**: Ensure the credentials are correct and that the user exists in Supabase Auth.
- **Your account is disabled. Contact the owner.**: The profile is missing or `is_active = false`. Ask the owner to enable the account in Supabase.
- **Can't reach the server. Check your connection and try again.**: There may be a network issue or Supabase outage. Verify internet connectivity and retry.
- **Session expired. Please log in again.**: The session token can expire. Log in once more to refresh the credentials.

Logs are printed to the terminal for debugging login attempts, profile checks, and session lifecycle events.
