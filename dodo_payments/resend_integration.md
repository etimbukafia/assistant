> ## Documentation Index
> Fetch the complete documentation index at: https://docs.dodopayments.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Resend

> Send transactional emails through Resend based on Dodo Payments events with high deliverability.

## Introduction

Send professional transactional emails automatically when payment events occur. Deliver payment confirmations, subscription updates, and important notifications with Resend's reliable email infrastructure and excellent deliverability rates.

<Info>
  This integration requires your Resend API Key for authentication.
</Info>

## Getting Started

<Steps>
  <Step title="Open the Webhook Section">
    In your Dodo Payments dashboard, navigate to <b>Webhooks → + Add Endpoint</b> and expand the integrations dropdown.

    <Frame>
      <img src="https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=80191f648ad4a4f4b5e8186668da0791" alt="Add Endpoint and integrations dropdown" data-og-width="1668" width="1668" data-og-height="946" height="946" data-path="images/integrations/resend.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=280&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=2dda0717d61a070938efd129abf25305 280w, https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=560&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=490ad04ecf8e27e166d08b6289c32a15 560w, https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=840&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=eb6464098afb7684710bdc272f753f3a 840w, https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=1100&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=f88091de0be2ec74a219fc7d037d5419 1100w, https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=1650&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=7a600f687799aae2e39e8c47d98d98c0 1650w, https://mintcdn.com/dodopayments/slbAEdrLLwKHfaRf/images/integrations/resend.png?w=2500&fit=max&auto=format&n=slbAEdrLLwKHfaRf&q=85&s=6fba6a2a5da2f3a550075e98955676da 2500w" />
    </Frame>
  </Step>

  <Step title="Select Resend">
    Choose the <b>Resend</b> integration card.
  </Step>

  <Step title="Enter API Key">
    Provide your Resend API Key in the configuration.
  </Step>

  <Step title="Configure Transformation">
    Edit the transformation code to format emails for Resend's API.
  </Step>

  <Step title="Test & Create">
    Test with sample payloads and click <b>Create</b> to activate the email sending.
  </Step>

  <Step title="Done!">
    🎉 Payment events will now automatically trigger transactional emails via Resend.
  </Step>
</Steps>

## Transformation Code Examples

### Payment Confirmation Email

```javascript payment_confirmation.js icon="js" expandable theme={null}
function handler(webhook) {
  if (webhook.eventType === "payment.succeeded") {
    const p = webhook.payload.data;
    webhook.url = "https://api.resend.com/emails";
    webhook.payload = {
      from: "payments@yourdomain.com",
      to: [p.customer.email],
      subject: "Payment Confirmation - $" + (p.total_amount / 100).toFixed(2),
      html: `
        <h2>Payment Successful!</h2>
        <p>Hi ${p.customer.name},</p>
        <p>Your payment of $${(p.total_amount / 100).toFixed(2)} has been processed successfully.</p>
        <ul>
          <li><strong>Payment ID:</strong> ${p.payment_id}</li>
          <li><strong>Amount:</strong> $${(p.total_amount / 100).toFixed(2)}</li>
          <li><strong>Date:</strong> ${new Date(webhook.payload.timestamp).toLocaleDateString()}</li>
          <li><strong>Method:</strong> ${p.payment_method || "Unknown"}</li>
        </ul>
        <p>Thank you for your business!</p>
      `,
      text: `Payment Successful! Your payment of $${(p.total_amount / 100).toFixed(2)} has been processed. Payment ID: ${p.payment_id}`
    };
  }
  return webhook;
}
```

### Subscription Welcome Email

```javascript subscription_welcome.js icon="js" expandable theme={null}
function handler(webhook) {
  if (webhook.eventType === "subscription.active") {
    const s = webhook.payload.data;
    webhook.url = "https://api.resend.com/emails";
    webhook.payload = {
      from: "welcome@yourdomain.com",
      to: [s.customer.email],
      subject: "Welcome to Your Subscription!",
      html: `
        <h2>Welcome to Your Subscription!</h2>
        <p>Hi ${s.customer.name},</p>
        <p>Your subscription has been activated successfully.</p>
        <ul>
          <li><strong>Subscription ID:</strong> ${s.subscription_id}</li>
          <li><strong>Product:</strong> ${s.product_id}</li>
          <li><strong>Amount:</strong> $${(s.recurring_pre_tax_amount / 100).toFixed(2)}/${s.payment_frequency_interval}</li>
          <li><strong>Next Billing:</strong> ${new Date(s.next_billing_date).toLocaleDateString()}</li>
        </ul>
        <p>You can manage your subscription anytime from your account dashboard.</p>
      `,
      text: `Welcome! Your subscription is now active. Amount: $${(s.recurring_pre_tax_amount / 100).toFixed(2)}/${s.payment_frequency_interval}`
    };
  }
  return webhook;
}
```

### Payment Failure Notification

```javascript payment_failure.js icon="js" expandable theme={null}
function handler(webhook) {
  if (webhook.eventType === "payment.failed") {
    const p = webhook.payload.data;
    webhook.url = "https://api.resend.com/emails";
    webhook.payload = {
      from: "support@yourdomain.com",
      to: [p.customer.email],
      subject: "Payment Failed - Action Required",
      html: `
        <h2>Payment Failed</h2>
        <p>Hi ${p.customer.name},</p>
        <p>We were unable to process your payment of $${(p.total_amount / 100).toFixed(2)}.</p>
        <ul>
          <li><strong>Payment ID:</strong> ${p.payment_id}</li>
          <li><strong>Amount:</strong> $${(p.total_amount / 100).toFixed(2)}</li>
          <li><strong>Error:</strong> ${p.error_message || "Payment processing failed"}</li>
        </ul>
        <p>Please update your payment method or contact support for assistance.</p>
        <a href="https://yourdomain.com/update-payment">Update Payment Method</a>
      `,
      text: `Payment Failed: We couldn't process your $${(p.total_amount / 100).toFixed(2)} payment. Please update your payment method.`
    };
  }
  return webhook;
}
```

## Tips

* Use verified sender domains for better deliverability
* Include both HTML and text versions of emails
* Personalize content with customer data
* Use clear, action-oriented subject lines
* Include unsubscribe links for compliance
* Test email templates before going live

## Troubleshooting

<AccordionGroup>
  <Accordion title="Emails not being sent">
    * Verify API Key is correct and active
    * Check that sender domain is verified in Resend
    * Ensure recipient email addresses are valid
    * Review Resend sending limits and quotas
  </Accordion>

  <Accordion title="Transformation errors">
    * Validate JSON structure matches Resend API format
    * Check that all required fields are present
    * Ensure HTML content is properly formatted
    * Verify from email address is verified
  </Accordion>
</AccordionGroup>
