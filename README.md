# TipSplit Desktop Access Control

This project now relies on environment configuration for remote access control.

1. Copy `.env.example` to `.env` and fill in your Supabase project values before running the application locally.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python MainApp.py` (or `python app.py`) and sign in with an authorized Supabase account.
4. In Supabase, execute the SQL found in `supabase/setup.sql` to provision the required tables, indexes, and policies.

The admin CLI in `admin/admin_toggle.py` requires the service role key in your local `.env`. Never distribute this key with application builds.
