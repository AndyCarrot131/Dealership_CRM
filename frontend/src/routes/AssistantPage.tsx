import { useState } from "react";
import AgentChat from "../components/AgentChat";
import {
  AgentKey,
  SimpleCustomer,
  AgentPicker,
  CustomerSearch,
  StylePanel,
  RulePanel,
  EmailPanel,
} from "../components/AgentPanels";

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        justifyContent: "center",
        background: "#f0f2f5",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 720,
          height: "100%",
          display: "flex",
          flexDirection: "column",
          borderLeft: "1px solid #e5e7eb",
          borderRight: "1px solid #e5e7eb",
          background: "#fafafa",
        }}
      >
        {children}
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentKey | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<SimpleCustomer | null>(null);

  function handleBack() {
    setSelectedAgent(null);
    setSelectedCustomer(null);
  }

  if (!selectedAgent) {
    return (
      <PageShell>
        <div
          style={{
            padding: "14px 16px",
            borderBottom: "1px solid #e5e7eb",
            fontWeight: 600,
            fontSize: 14,
            color: "#111",
            background: "#fff",
            flexShrink: 0,
          }}
        >
          ✦ AI Assistant
        </div>
        <AgentPicker onSelect={setSelectedAgent} />
      </PageShell>
    );
  }

  if (selectedAgent === "assistant") {
    return (
      <PageShell>
        <AgentChat mode="page" chatMode="assistant" onClose={handleBack} />
      </PageShell>
    );
  }

  if (selectedAgent === "intake") {
    return (
      <PageShell>
        <AgentChat mode="page" chatMode="intake" onClose={handleBack} />
      </PageShell>
    );
  }

  if (selectedAgent === "update") {
    if (!selectedCustomer) {
      return (
        <PageShell>
          <CustomerSearch onSelect={setSelectedCustomer} onBack={handleBack} />
        </PageShell>
      );
    }
    return (
      <PageShell>
        <AgentChat
          mode="page"
          chatMode="update"
          customerId={selectedCustomer.id}
          customerName={selectedCustomer.full_name}
          onClose={handleBack}
        />
      </PageShell>
    );
  }

  if (selectedAgent === "style") {
    return (
      <PageShell>
        <StylePanel onBack={handleBack} />
      </PageShell>
    );
  }

  if (selectedAgent === "rule") {
    return (
      <PageShell>
        <RulePanel onBack={handleBack} />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <EmailPanel onBack={handleBack} />
    </PageShell>
  );
}
