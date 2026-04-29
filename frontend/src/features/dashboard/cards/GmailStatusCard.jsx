export function GmailStatusCard({
  gmailStatusError,
  gmailStatus,
  providerSummary,
  gmailPrimaryAccount,
  gmailPrimaryMailboxStatus,
  gmailStatusLoading,
  gmailPrimaryStore,
  gmailPrimaryClassification,
  gmailPrimarySpamhaus,
  gmailPrimaryQuotaUsage,
}) {
  return (
    <article className="card dashboard-primary-card">
      <div className="card-header">
        <h2>Gmail Status</h2>
        <p className="muted">Background Gmail inbox status and unread counts.</p>
      </div>
      {gmailStatusError ? <div className="callout callout-danger">{gmailStatusError}</div> : null}
      <dl className="facts">
        <div><dt>Provider State</dt><dd>{gmailStatus?.provider_state || providerSummary?.provider_state || "pending"}</dd></div>
        <div><dt>Account</dt><dd>{gmailPrimaryAccount?.email_address || gmailPrimaryAccount?.account_id || "Pending"}</dd></div>
        <div><dt>Unread Today</dt><dd>{gmailPrimaryMailboxStatus?.unread_today_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd></div>
        <div><dt>Unread Yesterday</dt><dd>{gmailPrimaryMailboxStatus?.unread_yesterday_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd></div>
        <div><dt>Stored Emails</dt><dd>{gmailPrimaryStore?.total_count ?? 0}</dd></div>
        <div><dt>Classified Emails</dt><dd>{gmailPrimaryClassification?.classified_count ?? 0}</dd></div>
        <div><dt>High Confidence</dt><dd>{gmailPrimaryClassification?.high_confidence_count ?? 0}</dd></div>
        <div><dt>Spamhaus Checked</dt><dd>{gmailPrimarySpamhaus?.checked_count ?? 0}</dd></div>
        <div><dt>Spamhaus Pending</dt><dd>{gmailPrimarySpamhaus?.pending_count ?? 0}</dd></div>
        <div><dt>Spamhaus Listed</dt><dd>{gmailPrimarySpamhaus?.listed_count ?? 0}</dd></div>
        <div><dt>Quota Used / Min</dt><dd>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : 0}</dd></div>
        <div><dt>Quota Remaining</dt><dd>{gmailPrimaryQuotaUsage?.remaining_last_minute ?? 15000}</dd></div>
      </dl>
    </article>
  );
}
