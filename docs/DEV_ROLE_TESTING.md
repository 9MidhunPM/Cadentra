# Explicit demo role testing

Disabled by default. Enable only the intended demo instance with both
DEV_TOOLS_ENABLED=true and DEMO_INSTANCE=true; privately configure an Argon2
DEV_PASSWORD_HASH. There is no shared default password or frontend credential.
Existing production HTTPS/proxy/CSRF and email rules remain enforced. Real actions
persist; normal email delivery remains enabled except existing demo-contact rules.

Only a normal, active, non-impersonated administrator session can unlock. Grants
expire absolutely after30minutes or sooner if the original session expires.
They retain hashed tokens and a credential fingerprint, never raw session tokens.
Every linked authenticated request validates current grant cookie, target session,
original administrator/session, enabled settings and credential fingerprint.
Grant-aware sessions keep actual target User/role/customer_id; User rows are never
modified by switching. Switch revokes prior linked sessions; End revokes all linked
sessions and restores a fresh ordinary admin session. Normal login/logout ends the
whole context, including revocation of its original Admin source session. Failed unlocks and switches/end are audited without request payloads, query
strings or credentials. Linked business writes validate grant authority, Origin and
normal CSRF before a durable DEV_BUSINESS_WRITE_ATTEMPT is recorded. Attempt
storage failure returns503 before the route executes. A separate outcome records
the actual HTTP status, including unhandled500 exceptions. Outcome storage failure
preserves the existing business response and leaves the durable attempt pending
with unknown outcome, plus a sanitized exception-class warning. It never invents
success or encourages a retry after an already committed success. Normal login
and logout recovery are excluded from business pre-audit storage dependencies.

API startup checks migration0003 then durably revokes all grants when disabled,
or grants with a changed credential fingerprint when enabled. Unavailable or
unmigrated databases keep developer tools disabled. Invalid linked authority is
also durably revoked when observed. The optional private operator command `python -m app.modules.identity.dev_tools --revoke-all`. can revoke all grants independently. Environment changes take effect after API
restart; startup revocation prevents old grants reviving after disable/reenable.

## HTTP contract

Prefix `/api/v1/dev-tools`. Disabled status safely returns
`{data:{enabled:false,unlocked:false}}`; other disabled routes return404.

- GET status: `{data:{enabled,unlocked,dev_csrf_token?,expires_at?,operator?:{id,name},target?:actor}}`.
- POST unlock `{password}`: normal session CSRF/Origin and existing normal Admin;
  returns unlocked status and sets HttpOnly grant cookie. Wrong password403
  DEV_ACCESS_DENIED, preserving the normal Admin session.
- GET accounts `?page=1&page_size=25&q=`: active existing User identities only;
  `{items:[{id,name,role,customer_id,email}],total,page,page_size}`. Literal escaped
  search; max page_size100. No password hashes, tokens or contact-only accounts.
- POST switch `{user_id}`: grant/current session cookies plus X-Dev-CSRF-Token;
  sets actual target session cookie; `{data:{actor,csrf_token,dev_tools:status}}`.
- POST end: same grant/current session/dev-CSRF checks; fresh original Admin cookie
  and `{data:{actor,csrf_token,dev_tools:{enabled,unlocked:false}}}`. Expired,
  revoked or disabled authority requires an allowed Origin, revokes the whole
  context, clears both cookies and returns401 DEV_SESSION_EXPIRED. It never
  restores an Admin session. Wrong developer CSRF on a valid grant remains403
  and preserves the context.
- Normal GET auth/session adds `data.dev_tools` for persistent impersonation banner.

Actor is `{id,name,role,customer_id}`. Dates are ISO8601 UTC. Browser must reload and
invalidate account-scoped state across tabs after switches; display operator,
target, expiry and persistent/live-email notice. A target session without its grant
cookie is rejected. Existing normal-role CSRF remains necessary for business writes.

Migration0003 is additive; existing sessions receive nullable dev_grant_id.
Downgrade revokes linked sessions before removing the grant relation. Health expects
0003; update coordinated readiness/performance fixtures before final source freeze.

## Verification

Eighteen focused real HTTP/PostgreSQL cases pass on a newly created disposable0003
PostgreSQL database: administrator/password/two-CSRF boundaries, actual customer
role and foreign404, audit, stale session revocation, administrator restoration,
expiry/disable/hash rotation/operator/original session invalidation, normal
login/logout termination, grant-only/session-only rejection bounded listing, startup disable/reenable revocation and all three audit failure
boundaries (pre-dispatch refusal, post-commit success preservation and unhandled
failure outcome).
No production enablement, credentials transfer or delivery tests were performed.

Identity control transactions lock involved operator/current/selected/login User
rows in sorted UUID order, then the grant, then refreshed original/target session
rows. End restoration serializes with password reset's User lock. Two real
PostgreSQL connections verified both winner orders: reset-first denies restoration;
end-first creates a session that the following reset revokes. Neither leaves a
valid restored Admin session after reset. Replacement unlock may preserve its
already validated ordinary Admin source while revoking the prior linked grant;
ordinary login/logout always revoke the old source.

The final logout adjustment uses revocation-only authentication: allowed Origin
and the actual current session cookie's normal CSRF are required, but a missing,
expired or disabled developer grant cannot prevent cleanup. It resolves the
session's persisted dev_grant_id, revokes its original source and linked context,
and clears both cookies. No business endpoint bypasses require_actor. After this
adjustment, three focused logout cases passed (including actual HTTP deletion of
the grant cookie); the preceding eighteen-case pass remains separately recorded.
