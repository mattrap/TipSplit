# TipSplit Authentication & Supabase Setup

This release introduces user authentication backed by Supabase. The desktop
application now requires a successful login **before** the main interface is
displayed. Credentials are synchronised from a Supabase project and cached
locally to allow offline usage.

## 1. Supabase configuration

1. Create (or reuse) a Supabase project on the free tier.
2. Add a table named `users` with the following columns:
   - `email` (`text`, primary key, unique, stored in lowercase recommended).
   - `password_hash` (`text`) – store bcrypt hashes (e.g. generate with
     `bcrypt.hashpw`).
   - `status` (`text`) – use `active`, `disabled`, or `revoked` to control
     access.
   - `updated_at` (`timestamp` with time zone, default `now()` optional).
3. Disable anonymous/public access to the table and note the **service role**
   API key and the project URL (e.g. `https://xyzcompany.supabase.co`).

## 2. Configuring the desktop app

The Supabase settings are stored in the user configuration file. They can be
entered directly inside the application (menu **Réglages → Configurer
Supabase…**) or manually by editing `config.json` in the TipSplit data folder.

The service key is obfuscated before being written to disk to avoid storing the
plain value. Keep the configuration directory accessible only to trusted
administrators.

When the app launches it attempts to synchronise the `users` table. If Supabase
cannot be reached, the last cached list of users is used and the user is warned
about the offline mode. Remote status changes (set to `disabled`/`revoked`) take
effect on the next successful synchronisation.

## 3. Offline behaviour

- Cached credentials are stored in `<user-data-dir>/auth_cache.json`.
- Logins are allowed offline as long as the email/password match the cached
  hash and the cached status is still `active`.
- Once connectivity returns, use **Réglages → Re-synchroniser les accès** to
  refresh immediately or wait for the periodic background sync.

## 4. Manual test checklist

1. Launch the app with an active internet connection – login should succeed
   after Supabase synchronisation.
2. Disable networking and restart the app – login using cached credentials and
   acknowledge the offline warning.
3. Change a user status to `disabled` on Supabase, re-sync, and confirm that the
   next login is blocked.
4. Re-enable networking and trigger “Re-synchroniser les accès” to ensure the
   app exits offline mode.

For any production deployment make sure the Supabase service key is rotated
periodically and that only trusted admins can modify the configuration file.

