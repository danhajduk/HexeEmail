import { GmailSetupActionCard } from "./cards/GmailSetupActionCard";
import { GmailSetupHeroCard } from "./cards/GmailSetupHeroCard";
import { GmailSetupSettingsCard } from "./cards/GmailSetupSettingsCard";
import { GmailSetupStatusCard } from "./cards/GmailSetupStatusCard";

export function GmailSetupPage({
  bootstrap,
  providerConfig,
  providerStatus,
  gmailStatus,
  providerForm,
  providerLoading,
  providerSaving,
  providerValidating,
  providerConnecting,
  providerNotice,
  providerError,
  connectUrl,
  onProviderChange,
  onRefresh,
  onSave,
  onValidate,
  onConnect,
  onBack,
  ToggleField,
  Field,
  TextareaField,
  statusTone,
}) {
  const providerSummary = providerStatus?.provider_account_summaries?.gmail || {};
  const providerHealth = providerSummary?.health || null;
  const providerAccounts = providerSummary?.accounts || [];
  const primaryAccount = providerAccounts[0] || null;
  const primaryStatus = gmailStatus?.accounts?.[0] || null;
  const validation = providerConfig?.validation || null;
  const providerReadyReasons = [];
  if (bootstrap?.status?.trust_state !== "trusted") {
    providerReadyReasons.push("node trust is not active");
  }
  if (!providerSummary?.configured) {
    providerReadyReasons.push("Gmail config is not valid yet");
  }
  if (!providerForm.enabled) {
    providerReadyReasons.push("provider is disabled");
  }
  const canConnect = providerReadyReasons.length === 0 && !providerConnecting;

  return (
    <main className="app-frame">
      <GmailSetupHeroCard providerSummary={providerSummary} statusTone={statusTone} onRefresh={onRefresh} providerLoading={providerLoading} onBack={onBack} />

      <section className="grid provider-grid">
        <GmailSetupStatusCard
          bootstrap={bootstrap}
          providerSummary={providerSummary}
          providerConfig={providerConfig}
          primaryAccount={primaryAccount}
          providerHealth={providerHealth}
          primaryStatus={primaryStatus}
          providerNotice={providerNotice}
          providerError={providerError}
        />
        <GmailSetupSettingsCard
          providerSummary={providerSummary}
          statusTone={statusTone}
          ToggleField={ToggleField}
          providerForm={providerForm}
          onProviderChange={onProviderChange}
          Field={Field}
          TextareaField={TextareaField}
          onValidate={onValidate}
          providerValidating={providerValidating}
          onSave={onSave}
          providerSaving={providerSaving}
          validation={validation}
        />
        <GmailSetupActionCard
          canConnect={canConnect}
          providerReadyReasons={providerReadyReasons}
          onConnect={onConnect}
          providerConnecting={providerConnecting}
          connectUrl={connectUrl}
        />
      </section>
    </main>
  );
}
