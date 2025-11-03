# TipSplit Desktop Access Control

This project now relies on environment configuration for remote access control.

1. Copy `.env.example` to `.env` and fill in your Supabase project values before running the application locally. The app also reads from `supabase.env`, which is the file distributed with production builds.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python MainApp.py` (or `python app.py`) and sign in with an authorized Supabase account.
4. In Supabase, execute the SQL found in `supabase/setup.sql` to provision the required tables, indexes, and policies.

The admin CLI in `admin/admin_toggle.py` requires the service role key in your local `.env`. Never distribute this key with application builds.

## Shipping builds

- `supabase.env` in the project root contains the public Supabase URL and anon key that ship with releases. Update this file whenever the production project changes; the PyInstaller spec bundles it next to the executable.
- The app loads `supabase.env` first and then `.env`, so local overrides remain possible without affecting the packaged artifact.
- Only the URL and anon key should live in shipping artifacts. Keep the service role key exclusively in local `.env` files or secure secret stores for administrative tools.
