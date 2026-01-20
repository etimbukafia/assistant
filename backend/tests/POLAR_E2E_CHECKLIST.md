# Polar Payment E2E Testing Checklist

Use this checklist to manually verify the complete payment flow in sandbox environment. **No real money is charged** - sandbox uses Stripe test cards.

## Prerequisites

- [ ] Sandbox account created at [sandbox.polar.sh](https://sandbox.polar.sh)
- [ ] Test product created in sandbox organization
- [ ] Webhook endpoint configured pointing to your staging server
- [ ] Environment variables set:
  - `POLAR_SANDBOX_ACCESS_TOKEN`
  - `POLAR_SANDBOX_PRODUCT_ID`
  - `POLAR_SANDBOX_WEBHOOK_SECRET`

---

## Test Card Information

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 0002` | Card declined |
| `4000 0000 0000 3220` | 3D Secure authentication |

**Expiry**: Any future date (e.g., 12/30)  
**CVC**: Any 3 digits (e.g., 123)

---

## E2E Test Scenarios

### Scenario 1: New User Subscription Flow

1. **Create new test user**
   - [ ] Log in with a fresh test account
   - [ ] Verify `subscription_tier` = `trial`
   - [ ] Verify `subscription_status` = `trialing`

2. **Initiate checkout**
   - [ ] Call `POST /billing/checkout` with success/cancel URLs
   - [ ] Verify response contains `checkout_url`
   - [ ] Verify `polar_customer_id` is set in user_settings

3. **Complete payment**
   - [ ] Open checkout URL in browser
   - [ ] Enter test card `4242 4242 4242 4242`
   - [ ] Complete payment
   - [ ] Verify redirect to success URL

4. **Verify webhook received**
   - [ ] Check server logs for `subscription.created` event
   - [ ] Verify user's `subscription_tier` = `pro`
   - [ ] Verify user's `subscription_status` = `active`
   - [ ] Verify `polar_subscription_id` is set
   - [ ] Verify `subscription_expires_at` is set

### Scenario 2: Subscription Renewal

1. **Wait for renewal** (or simulate via Polar dashboard)
   - [ ] Verify `subscription.active` webhook received
   - [ ] Verify `subscription_expires_at` updated to new period

### Scenario 3: Subscription Cancellation

1. **Cancel subscription**
   - [ ] Call `POST /billing/cancel`
   - [ ] Verify response `success: true`

2. **Verify webhook received**
   - [ ] Check server logs for `subscription.canceled` event
   - [ ] Verify user's `subscription_status` = `canceled`
   - [ ] Verify user's `subscription_tier` still = `pro` (access until period end)

### Scenario 4: Subscription Revocation (Expired/Failed Payment)

1. **Simulate via Polar dashboard** (or wait for period end)
   - [ ] Trigger `subscription.revoked` event

2. **Verify access revoked**
   - [ ] Verify user's `subscription_tier` = `trial`
   - [ ] Verify user's `subscription_status` = `expired`
   - [ ] Verify `polar_subscription_id` = `null`

### Scenario 5: Declined Card

1. **Initiate checkout with declined card**
   - [ ] Use card `4000 0000 0000 0002`
   - [ ] Verify payment fails
   - [ ] Verify user remains on trial tier
   - [ ] Verify no webhook events fired

### Scenario 6: Customer Portal Access

1. **Get portal URL**
   - [ ] Call `GET /billing/portal-url`
   - [ ] Verify response contains `portal_url`

2. **Access portal**
   - [ ] Open portal URL in browser
   - [ ] Verify can view subscription details
   - [ ] Verify can update payment method

---

## Verification Queries

```sql
-- Check user subscription status
SELECT 
    user_email,
    subscription_tier,
    subscription_status,
    polar_customer_id,
    polar_subscription_id,
    subscription_expires_at,
    trial_ends_at
FROM user_settings
WHERE user_email = 'test@example.com';
```

---

## Sign-Off

| Scenario | Tester | Date | Pass/Fail | Notes |
|----------|--------|------|-----------|-------|
| New subscription | | | | |
| Renewal | | | | |
| Cancellation | | | | |
| Revocation | | | | |
| Declined card | | | | |
| Portal access | | | | |

**Overall Status**: [ ] Ready for Production / [ ] Issues Found
