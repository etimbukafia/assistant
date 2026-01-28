# Business Analysis: Code-to-Revenue Impact Assessment

> AI-powered executive assistant inbox management system
> **Business Model**: Freemium with 7-day trial → $X/month Pro subscription (Polar billing)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Revenue Model Analysis](#revenue-model-analysis)
3. [Critical Revenue Paths](#critical-revenue-paths)
4. [Silent Failures Causing Churn](#silent-failures-causing-churn)
5. [Bugs Leading to Revenue Loss](#bugs-leading-to-revenue-loss)
6. [Money-Optimized Recommendations](#money-optimized-recommendations)
7. [Critical Path Testing Plan](#critical-path-testing-plan)

---

## Executive Summary

### Business Model
- **Sandbox Mode**: Demo data (no Gmail connection required)
- **Trial**: 7 days, full feature access, requires explicit activation
- **Pro**: Paid subscription via Polar.sh
- **Grace Period**: 3 days after expiration (retention safety net)

### Revenue Levers Identified
| Lever | Code Location | Impact |
|-------|---------------|--------|
| Trial-to-Pro conversion | `/subscription/activate-trial` → `/billing/checkout` | Primary revenue |
| Feature value delivery | AI processing pipeline | Retention driver |
| Notification engagement | Push notifications, digests | DAU/MAU |
| Billing state accuracy | Webhook handlers | Revenue integrity |

### Critical Finding Summary
- **12 silent failures** identified that could cause users to leave without knowing why
- **5 revenue-blocking bugs** that prevent users from paying or receiving value
- **8 optimization opportunities** to increase conversion and reduce churn

---

## Revenue Model Analysis

### Subscription State Machine

```
NEW USER (sandbox)
    │
    ├── Never activates trial ───────────────────────► Lost opportunity
    │
    └── POST /subscription/activate-trial
        │
        ▼
    TRIAL (7 days)
        │
        ├── Converts before expiration ──► PRO (monthly) ──► Renewal loop
        │                                      │
        │                                      ├── Cancels ──► Access until period end
        │                                      │                    │
        │                                      │                    └── Revoked ──► EXPIRED
        │                                      │
        │                                      └── Payment fails ──► PAST_DUE ──► Grace (3 days)
        │
        └── Trial expires ──► GRACE PERIOD (3 days) ──► EXPIRED (read-only)
```

### Revenue Protection Mechanisms

| Mechanism | Code Location | Purpose |
|-----------|---------------|---------|
| Grace period | `feature_gating.py:22` (GRACE_PERIOD_DAYS=3) | Reduce involuntary churn |
| Deferred trial | Trial NOT auto-started | Qualify leads before timer starts |
| Webhook state sync | `webhook_handlers.py` | Accurate billing state |
| Feature gating | `require_feature()` decorator | Enforce payment wall |

### Revenue Risk: Trial Never Activates
**Problem**: Users can stay in sandbox mode forever without hitting the trial conversion funnel.

**Code Evidence**:
```python
# models.py:180-182
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    # Trial is NOT auto-started — user must explicitly activate
    # self.trial_ends_at is set by the /subscription/activate-trial endpoint
```

**Impact**: Users who never activate trial never convert. No data on true interest level.

**Recommendation**: Add trial activation prompt after N sandbox interactions or X days in sandbox.

---

## Critical Revenue Paths

### Path 1: Trial Activation → Gmail Sync → Value Delivery

**Success Criteria**: User sees their real emails summarized with tasks extracted

**Code Flow**:
```
1. POST /subscription/activate-trial
   └── Sets trial_ends_at = NOW + 7 days

2. POST /auth/gmail (OAuth flow)
   └── Stores encrypted credentials in GmailAccount

3. POST /messages/sync
   └── Requires: require_feature(Feature.EMAIL_SYNC)
   └── Calls: GmailClient.get_messages()
   └── Enqueues: process_email tasks

4. BatchWorker processes tasks
   └── AIProcessor.init_thread_state()
   └── Extracts: summary, tasks, dates, decisions

5. GET /messages (mobile fetches results)
   └── User sees value
```

**Failure Points**:
| Point | Risk | Revenue Impact |
|-------|------|----------------|
| OAuth token not saved | Gmail won't sync | User sees no value → churns |
| process_email task fails silently | No AI extraction | Core feature broken |
| LLM returns malformed JSON | Fallback loses data | Degraded experience |
| Body truncation at 3000 chars | Loses context | Incorrect summaries |

### Path 2: Trial Expiration → Upgrade Prompt → Payment

**Success Criteria**: User upgrades before or shortly after trial ends

**Code Flow**:
```
1. Mobile checks: GET /settings
   └── Returns: is_active, days_remaining, subscription_status

2. If days_remaining <= 3:
   └── Show upgrade CTA in UI

3. User clicks "Upgrade":
   └── POST /billing/checkout
   └── Polar creates checkout session
   └── User redirected to payment page

4. Payment succeeds:
   └── Polar sends webhook: subscription.created
   └── Backend updates: subscription_tier = "pro"

5. User confirmed as Pro subscriber
```

**Failure Points**:
| Point | Risk | Revenue Impact |
|-------|------|----------------|
| `/settings` returns stale data | Wrong days_remaining shown | User doesn't see urgency |
| Checkout URL creation fails | User can't pay | Direct revenue loss |
| Webhook signature validation fails | Subscription not activated | User paid but locked out |
| polar_customer_id not saved | Can't link subscription | Orphaned payment |

### Path 3: Pro Renewal → Continued Access

**Success Criteria**: Monthly renewals process without user action

**Code Flow**:
```
1. Polar auto-charges user monthly

2. Webhook: subscription.active
   └── Updates: subscription_expires_at = new period end
   └── User continues with access

3. If payment fails:
   └── Webhook: subscription.updated (status=past_due)
   └── Grace period starts (3 days)

4. If still not paid:
   └── Webhook: subscription.revoked
   └── User loses access
```

**Failure Points**:
| Point | Risk | Revenue Impact |
|-------|------|----------------|
| Webhook not received | State out of sync | User locked out despite paying |
| subscription_expires_at not updated | is_active returns false | Paying user blocked |
| Grace period calculation wrong | User loses access early | Involuntary churn |

---

## Silent Failures Causing Churn

### SF-1: LLM Processing Returns Empty Results Silently ✅ FIXED

**Location**: `backend/src/app/processors/ai.py:141-143, 334-340`

**Problem**: When LLM fails or returns malformed JSON, fallback returns empty/default data without any user notification.

**Resolution**: Added `ai_fallback` boolean column to Message model. Fallback functions return `_fallback: True`, saved to DB. UI can check this field to show "Unable to analyze" instead of empty state. Also changed fallback `needs_reply` from `True` to `None` to prevent notification spam.

```python
# ai.py fallback behavior
def _empty_process_result() -> Dict:
    return {
        "summary": "",
        "needs_reply": False,
        "tasks": [],
        "dates": [],
        "people": [],
        "decisions": [],
    }

def _fallback_init_thread_state() -> Dict:
    return {
        "summary": "Unable to process thread",
        "needs_reply": True,  # Default to TRUE - could cause notification spam
        # ...
    }
```

**Revenue Impact**: HIGH
- Users think AI isn't working
- No feedback that something went wrong
- Core value proposition undermined

**Metric to Track**: `ai_fallback_rate` - % of messages hitting fallback

---

### SF-2: Gmail Sync Webhook Failures Return 200 OK ✅ ALREADY ADDRESSED

**Location**: `backend/src/app/routes/v1/webhooks.py:47-52, 62-66`

**Problem**: Invalid webhook payloads return 200 to prevent retries, but failure is silent.

**Resolution**: Code already returns specific reason codes (`invalid_json`, `no_data`, `decode_failed`, `no_email`, `unknown_account`) in response body. Not silent.

```python
# Webhook swallows errors silently
try:
    data = json.loads(request_body)
except json.JSONDecodeError:
    logger.warning("Invalid JSON in Gmail webhook")
    return JSONResponse({"status": "ok"})  # Gmail won't retry, but user emails not syncing
```

**Revenue Impact**: CRITICAL
- Users' new emails stop syncing
- User thinks app is broken/useless
- No indication of what went wrong

**Metric to Track**: `gmail_webhook_error_rate`, `messages_synced_per_day_per_user`

---

### SF-3: Background Job Failures Not Visible to Users ✅ FIXED

**Location**: `backend/src/app/jobs/worker.py:91-93`

**Problem**: Task failures logged but user never notified. Task retries silently.

**Resolution**: Added `on_permanent_failure` callback to Worker and BatchWorker. When all retries exhausted, callback creates a system Notification for the user. Core queue remains generic; app-level callback handles notifications.

```python
except Exception as e:
    logger.error(f"Task processing failed: {task_type} (id={task_id}): {str(e)}", exc_info=True)
    self.queue_service.mark_failed(task_id, str(e), retry=True, db=db)
    # No user notification
```

**Revenue Impact**: HIGH
- Email processing fails without user knowing
- User waits indefinitely for results
- Appears as "loading" forever on mobile

**Metric to Track**: `task_failure_rate`, `task_retry_count`

---

### SF-4: Gmail Token Refresh Returns False Silently ✅ FIXED

**Location**: `backend/src/app/integrations/gmail.py:262-263`

**Problem**: Token refresh failures return `False` with console print, no structured handling.

**Resolution**: Changed `print()` to `logger.error()` with email context for proper log aggregation.

```python
# Token refresh failure - silent degradation
except Exception as e:
    print(f"Token refresh failed: {e}")  # Not even proper logging
    return False  # Caller may not check this
```

**Revenue Impact**: HIGH
- All Gmail operations start failing ~1 hour after auth
- User's sync stops working
- No automatic re-auth prompt

**Metric to Track**: `token_refresh_failures`, `sync_errors_per_user`

---

### SF-5: Attachment Processing Silently Skipped

**Location**: `backend/src/app/handlers/message_handlers.py:203-226`

**Problem**: Failed attachment downloads/processing just continue without user notification.

```python
# Unsupported attachment types silently skipped
if mime_type not in SUPPORTED_TYPES:
    logger.info(f"Skipping unsupported attachment type: {mime_type}")
    continue  # User never knows their PDF wasn't processed
```

**Revenue Impact**: MEDIUM
- Users expect document analysis
- Important contract/agreement details missed
- User doesn't know to check attachments manually

---

### SF-6: Notification Delivery Failures Unmarked

**Location**: `backend/src/app/services/notification.py:180-210`

**Problem**: Push notification failures logged but notification status not updated.

```python
except Exception as e:
    logger.error(f"Push notification failed: {e}")
    # notification.push_sent stays False
    # notification.delivery_error not set
    # No retry logic
```

**Revenue Impact**: MEDIUM
- Users miss urgent task notifications
- Digests not delivered
- Engagement drops

---

### SF-7: Unknown Task Types Marked as Completed ✅ FIXED

**Location**: `backend/src/core/queue/worker.py:75-83`

**Problem**: Tasks with unrecognized types are marked "completed" instead of "failed".

**Resolution**: Changed to `logger.error()` and `mark_failed(..., retry=False)` to surface issues without retry loops.

```python
if handler is None:
    handler = self.handlers.get("_default")
    if handler is None:
        logger.warning(f"No handler for task type: {task_type}")
        # Mark as completed so it doesn't retry forever
        self.queue_service.mark_completed(task_id, db=db)  # DATA LOSS
        return
```

**Revenue Impact**: HIGH
- Typos in task types cause silent data loss
- No alerting on unknown task types
- Critical work silently dropped

---

### SF-8: Digest Timezone Calculation Assumes UTC

**Location**: `backend/src/app/services/digest.py`

**Problem**: "Today's tasks" calculated without user timezone consideration.

**Revenue Impact**: MEDIUM
- Digests show wrong day's tasks
- Users in non-UTC timezones get incorrect briefings
- Reduces trust in AI assistant

---

### SF-9: Mobile Settings Fetch Failure Defaults to Sandbox ✅ FIXED

**Location**: `mobile/src/context/AuthContext.tsx:79`

**Problem**: If `/settings` API fails, mobile assumes sandbox mode.

**Resolution**: Added `settingsError` state to context. On error, preserves previous values instead of resetting to sandbox. UI can check `settingsError` to show "Connection issue" instead of demo data.

```typescript
// Silent failure defaults to sandbox
try {
    const settings = await fetchSettings();
    setIsSandbox(settings.trial_ends_at === null);
} catch {
    setIsSandbox(true);  // User locked into demo mode
}
```

**Revenue Impact**: CRITICAL
- Paying users see demo data instead of their emails
- Users think app is broken
- No indication of actual subscription status

---

### SF-10: RLS Context Missing Silently Continues

**Location**: `backend/src/app/handlers/message_handlers.py:44-47`

**Problem**: Missing user_id in payload logs error but returns silently.

```python
if not user_id:
    logger.error("No user_id in payload...")
    return  # No exception, no user notification
```

**Revenue Impact**: HIGH (also security risk)
- User's messages not processed
- Potential cross-user data access without RLS
- Silent data isolation failure

---

### SF-11: Polar Webhook User Not Found ✅ FIXED

**Location**: `backend/src/app/handlers/webhook_handlers.py:91-97`

**Problem**: If customer_id doesn't match any user, webhook is silently ignored.

**Resolution**: `subscription.created` now logs as `logger.error("REVENUE CRITICAL: ...")`. Other webhook handlers log as `logger.warning()` with customer_id for investigation.

**Revenue Impact**: CRITICAL
- User pays but subscription not activated
- User locked out despite payment
- Requires manual intervention to fix

---

### SF-12: Chat Processing Stuck in "Processing" State

**Location**: `backend/src/app/jobs/worker.py:1158-1177`

**Problem**: Missing fields or session-not-found leaves message in processing state forever.

**Revenue Impact**: MEDIUM
- Chat appears to hang
- User thinks AI is slow/broken
- Reduces engagement with chat feature

---

## Bugs Leading to Revenue Loss

### BUG-1: is_active Property Has Clock Skew Vulnerability ✅ FIXED

**Location**: `backend/src/app/data/models.py:184-196`

**Problem**: `is_active` compares server time to database time. Clock drift between app server and database can cause incorrect access decisions.

**Resolution**: Added 30-second `CLOCK_SKEW_TOLERANCE` constant to time comparisons in `models.py` and `feature_gating.py`.

```python
@property
def is_active(self) -> bool:
    now = datetime.now(timezone.utc)  # App server time

    if self.trial_ends_at and self.trial_ends_at > now:  # DB time
        return True  # What if clocks differ by minutes?
```

**Revenue Impact**: HIGH
- Users might get free access beyond trial
- Or paying users locked out early
- Edge case but high impact when it hits

**Fix**: Use database NOW() for time comparisons, or add buffer tolerance.

---

### BUG-2: Grace Period Not Checked for Pro Users ✅ FIXED

**Location**: `backend/src/app/security/feature_gating.py:45-61`

**Problem**: Grace period checks `subscription_expires_at` but Pro users with status="active" bypass the check entirely.

**Resolution**: `is_active` now checks both `subscription_status` AND `subscription_expires_at` for Pro users.

```python
def is_feature_enabled(feature: Feature, settings) -> bool:
    if settings.is_active:  # Pro with status=active returns True here
        return True

    # Grace period only checked if is_active is False
    if _is_in_grace_period(settings):
        return True
```

**Scenario**: Pro user's subscription_expires_at is in the past, but status is still "active" due to webhook delay. They get access they shouldn't have.

**Revenue Impact**: LOW (edge case)
- Small window of extra free access
- Webhook usually arrives quickly

---

### BUG-3: Checkout Creates Customer But Doesn't Save on Failure

**Location**: `backend/src/app/routes/v1/billing.py`

**Problem**: If checkout URL creation fails after customer creation, polar_customer_id is saved but checkout failed.

```python
# Get or create Polar customer
if not user.polar_customer_id:
    customer_id = polar_service.get_or_create_customer(user.user_email)
    if not customer_id:
        raise HTTPException(status_code=500, detail="Failed to create billing customer")
    user.polar_customer_id = customer_id
    db.commit()  # Saved customer_id

# Create checkout session
checkout_url = polar_service.create_checkout_session(...)
if not checkout_url:
    raise HTTPException(status_code=500, detail="Failed to create checkout session")
    # But polar_customer_id already saved
```

**Revenue Impact**: LOW
- Not actually a bug - customer exists, just retry checkout
- But could be confusing if debugging

---

### BUG-4: Trial Reactivation Blocked Forever After Expiration ✅ FIXED

**Location**: `backend/src/app/routes/v1/subscription.py`

**Problem**: Users who let trial expire cannot restart trial (intentional) but also can't easily upgrade.

**Resolution**: Returns `{status: "trial_expired", action: "checkout", checkout_endpoint: "/billing/checkout"}` instead of HTTP 400.

```python
if settings.trial_ends_at:
    if settings.trial_ends_at > datetime.now(timezone.utc):
        return {"status": "active", ...}
    else:
        raise HTTPException(status_code=400, detail="Trial already expired")
```

**Revenue Impact**: MEDIUM
- Expired trial users need to find checkout flow separately
- Friction in conversion path
- Should redirect to checkout instead of error

**Fix**: Return checkout URL instead of error for expired trials.

---

### BUG-5: Webhook Signature Validation Fails Without Secret ✅ FIXED

**Location**: `backend/src/app/handlers/webhook_handlers.py`

**Problem**: Missing POLAR_WEBHOOK_SECRET returns 500, causing Polar to retry forever.

**Resolution**: Returns 200 with `{handled: false, reason: "webhook_secret_not_configured"}` to stop retries. Logs error for ops visibility.

```python
def validate_webhook_signature(payload, headers):
    settings = get_settings()

    if not settings.POLAR_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
        # Polar will retry, creating a webhook storm
```

**Revenue Impact**: CRITICAL
- All subscription events fail
- No one can upgrade
- Potential webhook backlog at Polar

**Fix**: Return 200 with logged warning if secret not configured (dev environment), or ensure secret is always set in production.

---

## Money-Optimized Recommendations

### REC-1: Add Trial Expiration Warning Notifications

**Current State**: No proactive notification when trial is about to expire.

**Recommendation**: Send push notifications at:
- 3 days remaining
- 1 day remaining
- Expired (grace period started)
- Grace period ending

**Implementation**:
```python
# Add to worker.py scheduled tasks
async def check_trial_expirations():
    expiring_soon = db.query(UserSettings).filter(
        UserSettings.trial_ends_at.between(now, now + timedelta(days=3))
    ).all()

    for user in expiring_soon:
        send_notification(
            user_id=user.user_id,
            title="Your trial expires soon",
            body=f"{user.days_remaining} days left. Upgrade to keep your AI assistant.",
            category="system",
            target_type="settings"
        )
```

**Revenue Impact**: +15-25% trial conversion (industry benchmark)

**Pros**:
- Direct path to conversion
- Reduces "forgot to upgrade" churn
- Clear call-to-action

**Cons**:
- Could feel pushy
- Need to balance frequency
- Must respect notification preferences

---

### REC-2: Add Processing Status Indicator in Mobile

**Current State**: Users have no visibility into background processing status.

**Recommendation**: Add real-time processing status to mobile UI.

**Implementation**:
- Add `GET /queue/status/{user_id}` endpoint returning pending task count
- Mobile polls status when sync in progress
- Show "Processing 5 emails..." indicator

**Revenue Impact**: Reduces perceived broken state → +5-10% retention

**Pros**:
- Transparent processing state
- Users know system is working
- Reduces support tickets

**Cons**:
- Additional API calls
- Polling overhead
- Need graceful handling of long processing

---

### REC-3: Implement Webhook Delivery Confirmation

**Current State**: No verification that Polar webhooks are being received.

**Recommendation**: Add webhook health monitoring.

**Implementation**:
```python
# Add webhook tracking table
class WebhookLog(Base):
    event_type = Column(String)
    received_at = Column(DateTime)
    processed = Column(Boolean)
    error = Column(Text)

# Alert if no webhooks received in 24 hours
async def check_webhook_health():
    last_webhook = db.query(WebhookLog).order_by(WebhookLog.received_at.desc()).first()
    if not last_webhook or last_webhook.received_at < now - timedelta(hours=24):
        alert_ops("No Polar webhooks received in 24 hours!")
```

**Revenue Impact**: Prevents revenue loss from missed webhooks

**Pros**:
- Proactive alerting
- Audit trail for billing
- Debug capability

**Cons**:
- Additional table/storage
- Need ops alerting infrastructure

---

### REC-4: Add Retry Logic with Exponential Backoff

**Current State**: Failed tasks retry immediately with no backoff.

**Recommendation**: Implement exponential backoff for retries.

**Implementation**:
```python
# In mark_failed()
retry_delay = min(300, 2 ** task.retry_count)  # Max 5 minutes
task.scheduled_at = now + timedelta(seconds=retry_delay)
task.retry_count += 1
```

**Revenue Impact**: Prevents API hammering → saves money, improves reliability

**Pros**:
- Protects external API rate limits
- Reduces failed task noise
- Standard industry practice

**Cons**:
- Delayed processing during outages
- More complex retry logic

---

### REC-5: Add LLM Fallback Quality Tracking

**Current State**: LLM failures silently use fallback data.

**Recommendation**: Track and alert on fallback rate.

**Implementation**:
```python
# In ai.py
def _fallback_init_thread_state(...):
    metrics.increment("ai.fallback.init_thread_state")

    if metrics.get_rate("ai.fallback.init_thread_state", window="1h") > 0.1:
        alert_ops("LLM fallback rate >10% in last hour")
```

**Revenue Impact**: Early detection of degraded AI quality

**Pros**:
- Proactive quality monitoring
- Can A/B test LLM changes
- Supports SLA guarantees

**Cons**:
- Need metrics infrastructure
- Alert fatigue if thresholds wrong

---

### REC-6: Redirect Expired Trial to Checkout (Not Error)

**Current State**: Expired trial returns HTTP 400 error.

**Recommendation**: Return checkout URL for expired trials.

**Implementation**:
```python
@router.post("/subscription/activate-trial")
def activate_trial(...):
    if settings.trial_ends_at and settings.trial_ends_at <= now:
        # Instead of error, guide to upgrade
        checkout_url = polar_service.create_checkout_session(...)
        return {
            "status": "trial_expired",
            "message": "Your trial has ended. Upgrade to continue.",
            "checkout_url": checkout_url
        }
```

**Revenue Impact**: +10-20% conversion from expired trial users

**Pros**:
- Removes friction from conversion
- Better UX than error
- Clear upgrade path

**Cons**:
- Slightly more complex logic
- Need to handle checkout creation failure

---

### REC-7: Add "Win-Back" Campaign for Churned Users

**Current State**: No re-engagement for users who churned.

**Recommendation**: Identify and target churned users.

**Implementation**:
```python
# Weekly job to find churned users
async def identify_win_back_candidates():
    churned = db.query(UserSettings).filter(
        UserSettings.subscription_status == "expired",
        UserSettings.trial_ends_at < now - timedelta(days=7),
        UserSettings.subscription_tier == "trial"  # Never paid
    ).all()

    for user in churned:
        # Could offer discount code, feature highlight, etc.
        enqueue_task("send_win_back_email", {"user_id": user.user_id})
```

**Revenue Impact**: +5-15% recovery of churned users (with discount)

**Pros**:
- Recover otherwise lost revenue
- Learn why users churned
- Test different offers

**Cons**:
- Email deliverability concerns
- Need discount code system
- Privacy considerations

---

### REC-8: Implement "Freemium Forever" Tier

**Current State**: Expired users have read-only access, no value.

**Recommendation**: Keep limited functionality free to maintain engagement.

**Implementation**:
- Free tier: Last 7 days of emails, no digests, no chat
- Trial: Full access, 7 days
- Pro: Full access, unlimited

**Revenue Impact**: Higher conversion from engaged free users

**Pros**:
- Maintains user engagement
- Demonstrates ongoing value
- Easier word-of-mouth

**Cons**:
- Server costs for free users
- Feature gating complexity
- May reduce urgency to upgrade

---

## Critical Path Testing Plan

### Overview

Tests organized by revenue impact. Run high-priority tests before every deployment.

### Priority 1: Revenue-Blocking (Run Every Deploy)

#### P1-1: Subscription Activation Flow
```
Test: Full trial → checkout → pro upgrade flow

Steps:
1. Create new user (sandbox state)
2. POST /subscription/activate-trial
   - Assert: trial_ends_at = now + 7 days
   - Assert: subscription_status = "trialing"
3. POST /billing/checkout
   - Assert: Returns valid checkout_url
   - Assert: polar_customer_id saved
4. Simulate webhook: subscription.created
   - Assert: subscription_tier = "pro"
   - Assert: subscription_status = "active"
5. GET /settings
   - Assert: is_active = true
   - Assert: Features accessible

Pass Criteria: User can access all features after payment
```

#### P1-2: Webhook Signature Validation
```
Test: Valid and invalid webhook signatures

Steps:
1. POST /webhooks/polar with valid signature
   - Assert: Returns 200
   - Assert: Event processed
2. POST /webhooks/polar with invalid signature
   - Assert: Returns 400
   - Assert: Event NOT processed
3. POST /webhooks/polar with missing signature
   - Assert: Returns 400

Pass Criteria: Only valid webhooks processed
```

#### P1-3: Grace Period Access
```
Test: Access during grace period

Steps:
1. Set trial_ends_at = now - 1 day
2. GET /settings
   - Assert: is_active = false
   - Assert: in_grace_period = true
3. POST /messages/sync
   - Assert: Returns 200 (grace period access)
4. Set trial_ends_at = now - 4 days
5. POST /messages/sync
   - Assert: Returns 402 (grace expired)

Pass Criteria: Grace period provides 3-day buffer
```

#### P1-4: Feature Gating Enforcement
```
Test: Features blocked after subscription expires

Steps:
1. Set subscription_status = "expired"
2. Set trial_ends_at = now - 10 days
3. POST /messages/sync
   - Assert: Returns 402
4. GET /digests
   - Assert: Returns 402
5. Set subscription_tier = "pro", status = "active"
6. POST /messages/sync
   - Assert: Returns 200

Pass Criteria: Only paid users access features
```

### Priority 2: Core Value Delivery (Run Daily)

#### P2-1: Email Sync Pipeline
```
Test: Full email sync flow

Steps:
1. Setup: User with valid Gmail credentials
2. POST /messages/sync
   - Assert: Returns messages
   - Assert: Tasks enqueued
3. Wait for worker processing (max 30s)
4. GET /messages
   - Assert: Messages have summaries
   - Assert: Messages have extracted_tasks (if any)

Pass Criteria: Emails synced and processed
```

#### P2-2: AI Processing Quality
```
Test: AI extraction produces valid output

Steps:
1. Enqueue process_email task with known email content
2. Wait for processing
3. Query message
   - Assert: summary is non-empty
   - Assert: summary is not "Unable to process"
   - Assert: If email has task language, extracted_tasks > 0

Pass Criteria: AI produces meaningful extractions
```

#### P2-3: LLM Fallback Handling
```
Test: System degrades gracefully on LLM failure

Steps:
1. Mock LLM to return invalid JSON
2. Process email
3. Query message
   - Assert: Message processed (no crash)
   - Assert: summary contains fallback text
   - Assert: Metric ai.fallback.* incremented

Pass Criteria: Fallback used, no crash
```

### Priority 3: Engagement Features (Run Weekly)

#### P3-1: Digest Generation
```
Test: Digest generates with correct content

Steps:
1. Create tasks due today
2. Create thread with needs_reply=true
3. Trigger digest generation
4. Query digest
   - Assert: Contains due tasks
   - Assert: Contains needs_reply threads
   - Assert: Timezone matches user preference

Pass Criteria: Digest reflects current state
```

#### P3-2: Push Notification Delivery
```
Test: Push notifications sent to devices

Steps:
1. Register device token
2. Create urgent task
3. Trigger notification
4. Check notification record
   - Assert: push_sent = true
   - Assert: push_ticket_id present

Pass Criteria: Notifications reach devices
```

#### P3-3: Chat Tool Execution
```
Test: Chat tools execute correctly

Steps:
1. Create chat session
2. Send message triggering tool (e.g., "show my tasks")
3. Check response
   - Assert: Tool executed
   - Assert: Response contains task data
   - Assert: No pending_action if tool is safe

Pass Criteria: Chat provides useful responses
```

### Priority 4: Error Handling (Run Before Major Releases)

#### P4-1: Gmail Token Expiration
```
Test: System handles expired Gmail tokens

Steps:
1. Set token_expiry to past
2. Attempt sync
   - Assert: Token refresh attempted
   - If refresh fails:
     - Assert: Error logged
     - Assert: User notified (if implemented)

Pass Criteria: Graceful token expiration handling
```

#### P4-2: Webhook Retry Behavior
```
Test: System handles webhook retries correctly

Steps:
1. Process subscription.created webhook
2. Process same webhook again (duplicate)
   - Assert: Idempotent (no double activation)
   - Assert: Returns 200

Pass Criteria: Webhook idempotency maintained
```

#### P4-3: RLS Context Enforcement
```
Test: RLS prevents cross-user data access

Steps:
1. Create message for user_a
2. Set RLS context to user_b
3. Query messages
   - Assert: user_a message NOT returned
4. Set RLS context to user_a
5. Query messages
   - Assert: user_a message returned

Pass Criteria: User data isolation enforced
```

### Test Execution Schedule

| Priority | When to Run | Estimated Time |
|----------|-------------|----------------|
| P1 | Every deploy | 5 minutes |
| P2 | Daily CI | 10 minutes |
| P3 | Weekly | 15 minutes |
| P4 | Major releases | 20 minutes |

### Monitoring Dashboards

Create dashboards for:
1. **Revenue Health**
   - Trial activations per day
   - Trial → Pro conversion rate
   - Churn rate (expired subscriptions)
   - MRR (Monthly Recurring Revenue)

2. **Processing Health**
   - Task queue depth
   - Task failure rate
   - LLM fallback rate
   - Avg processing time per email

3. **Engagement Health**
   - DAU/MAU ratio
   - Push notification delivery rate
   - Digest open rate (if tracking)
   - Chat sessions per user

4. **Error Health**
   - Gmail token refresh failures
   - Webhook validation failures
   - 5xx error rate
   - Background job crash rate

---

## Summary: Top 5 Actions by Revenue Impact

| Priority | Action | Expected Impact | Effort |
|----------|--------|-----------------|--------|
| 1 | Add trial expiration notifications | +15-25% conversion | Medium |
| 2 | Redirect expired trial to checkout | +10-20% conversion | Low |
| 3 | Add processing status to mobile | +5-10% retention | Medium |
| 4 | Implement webhook health monitoring | Prevent revenue loss | Medium |
| 5 | Track LLM fallback rate with alerts | Detect degradation | Low |

---

*Document generated: 2026-01-28*
*Review quarterly or after major architecture changes*
