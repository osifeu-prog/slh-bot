# Human Intervention Controls

## Scope and safety boundary

This feature adds a persisted, fail-closed approval lifecycle for non-read-only system shell commands that reach core.exec_policy.run_gated. It does not change balances, perform settlements, open financial gates, merge code, or deploy services.

Existing domain-specific approval mechanisms (for example BNB settlement confirmation and agent-submission review) remain domain-specific. This module does not claim to replace or automatically intercept every business workflow or every typed command implemented outside run_gated; those routes must keep their own authorization and evidence checks and be mapped before release.

## Defaults

Both settings require approval by default:

- action_execution=on: an unclassified or potentially mutating command is recorded and is not executed until the owner approves that exact request.
- action_completion=on: after a successful approved command execution, the record remains executed_pending_completion until the owner explicitly marks it complete.

Missing or malformed settings default to approval required. A persistence error blocks execution. Approvals expire after 15 minutes and are one-use, bound to the exact command hash and owner. Completion approval expires after 24 hours. Requests to disable a setting expire after five minutes; the setting remains on until the owner confirms the exact disable request.

Completion approval is an audit sign-off on a command that has already run. Denying completion does not reverse its side effects; reconcile those effects separately. Failed commands do not enter the pending-completion state.

## Telegram commands

Commands are owner-only and must be sent in a private chat with the bot.

- /intervention or /intervention status — read-only policy and pending request status.
- /intervention show <ID> — inspect a request without executing it; command preview is redacted best-effort.
- /intervention approve <ID> — approve and execute the exact pending request once.
- /intervention deny <ID> — reject a pending execution, or reject completion for an action that already ran.
- /intervention complete <ID> — record owner-approved completion for a successfully executed action.
- /intervention set action_execution on — turn on execution approval and record the change.
- /intervention set action_completion on — turn on completion approval and record the change.
- /intervention set action_execution off — request disabling; does not disable it yet.
- /intervention set action_completion off — request disabling; does not disable it yet.
- /intervention confirm_disable <ID> — explicitly confirm the pending disable request.

To run an unclassified command from /e or /exec, the first request returns an ID and does not run the command while action_execution is on. Inspect it with show, then approve or deny it. On success, the command reports the separate completion ID if completion approval remains enabled.

The read-only classifier is intentionally conservative. Simple commands such as pwd, whoami, ls, source-code grep, and limited read-only git commands can proceed without an intervention request; shell chains, redirection, scripts, and unknown commands require explicit approval. The independent dangerous-command policy still blocks its protected patterns even after approval.

## Audit and testing

Policy settings, request creation, approvals, denials, execution results, completion decisions, expirations, and disable confirmations are recorded under state/db.json key human_intervention, through state_manager.atomic_update. Audit records include UTC timestamp, actor, action, request ID, decision and result. Raw command text is not copied into the policy audit log; the pending request retains it only until it runs or is denied/expired.

Run python -m unittest tests.test_human_intervention -v and the complete repository CI before review. The feature is not enabled in production merely by adding these files to a branch. Require independent review and explicit release authorization; do not merge/deploy as part of this change.
