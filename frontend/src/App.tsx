import { useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AgentChat from "./components/AgentChat";
import {
  AgentKey,
  SimpleCustomer,
  AgentPicker,
  CustomerSearch,
  StylePanel,
  RulePanel,
  EmailPanel,
  PreVisitPanel,
} from "./components/AgentPanels";
import NavBar from "./components/NavBar";
import LoginPage from "./routes/LoginPage";
import CustomersPage from "./routes/CustomersPage";
import ContactsPage from "./routes/ContactsPage";
import DealsPage from "./routes/DealsPage";
import AssistantPage from "./routes/AssistantPage";
import InventoryPage from "./routes/InventoryPage";
import StylePage from "./routes/StylePage";
import OutreachPage from "./routes/OutreachPage";
import InboxPage from "./routes/InboxPage";
import SettingsPage from "./routes/SettingsPage";
import SupportInfoPage from "./routes/SupportInfoPage";

function ProtectedLayout() {
  const { token, mustChangePassword } = useAuth();
  const location = useLocation();
  const [showChat, setShowChat] = useState(false);
  const [sidebarAgent, setSidebarAgent] = useState<AgentKey | null>("assistant");
  const [sidebarCustomer, setSidebarCustomer] = useState<SimpleCustomer | null>(null);

  if (!token) return <Navigate to="/login" replace />;

  const onAssistantPage = location.pathname === "/assistant";
  const onSettingsPage = location.pathname === "/settings";

  function handleSidebarBack() {
    setSidebarAgent("assistant");
    setSidebarCustomer(null);
  }

  function handleSidebarClose() {
    setShowChat(false);
    setSidebarAgent("assistant");
    setSidebarCustomer(null);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <NavBar />
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {/* Main content */}
        <div style={{ flex: 1, overflow: "auto" }}>
          {mustChangePassword && !onSettingsPage ? (
            <Navigate to="/settings" replace />
          ) : (
            <Outlet />
          )}
        </div>

        {/* Sidebar */}
        <div
          className="sidebar-panel"
          style={{
            display: showChat && !onAssistantPage ? "flex" : "none",
            width: "25%",
            minWidth: 260,
            maxWidth: 380,
          }}
        >
          {sidebarAgent === null && (
            <>
              <div className="sidebar-header">
                <span style={{ flex: 1 }}>✦ AI Assistant</span>
                <button onClick={handleSidebarClose} title="Close" className="modal-close">
                  ×
                </button>
              </div>
              <AgentPicker onSelect={setSidebarAgent} compact />
            </>
          )}

          {sidebarAgent === "assistant" && (
            <AgentChat
              mode="page"
              chatMode="assistant"
              onClose={handleSidebarClose}
              onSwitchAgent={setSidebarAgent}
              currentAgent="assistant"
            />
          )}

          {sidebarAgent === "intake" && (
            <AgentChat
              mode="page"
              chatMode="intake"
              onClose={handleSidebarClose}
              onSwitchAgent={setSidebarAgent}
              currentAgent="intake"
            />
          )}

          {sidebarAgent === "update" && !sidebarCustomer && (
            <CustomerSearch
              onSelect={setSidebarCustomer}
              onBack={handleSidebarBack}
              onClose={handleSidebarClose}
            />
          )}

          {sidebarAgent === "update" && sidebarCustomer && (
            <AgentChat
              mode="page"
              chatMode="update"
              customerId={sidebarCustomer.id}
              customerName={sidebarCustomer.full_name}
              onClose={handleSidebarClose}
              onSwitchAgent={setSidebarAgent}
              currentAgent="update"
            />
          )}

          {sidebarAgent === "style" && (
            <StylePanel onBack={handleSidebarBack} onClose={handleSidebarClose} />
          )}

          {sidebarAgent === "rule" && (
            <RulePanel onBack={handleSidebarBack} onClose={handleSidebarClose} />
          )}

          {sidebarAgent === "email" && (
            <EmailPanel onBack={handleSidebarBack} onClose={handleSidebarClose} />
          )}

          {sidebarAgent === "pre_visit" && !sidebarCustomer && (
            <CustomerSearch
              onSelect={setSidebarCustomer}
              onBack={handleSidebarBack}
              onClose={handleSidebarClose}
            />
          )}

          {sidebarAgent === "pre_visit" && sidebarCustomer && (
            <PreVisitPanel
              customer={sidebarCustomer}
              onBack={handleSidebarBack}
              onClose={handleSidebarClose}
            />
          )}
        </div>
      </div>

      {!showChat && !onAssistantPage && (
        <button onClick={() => setShowChat(true)} title="Open AI Assistant" className="fab">
          ✦
        </button>
      )}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/contacts" element={<ContactsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/style" element={<StylePage />} />
          <Route path="/outreach" element={<OutreachPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/support-info" element={<SupportInfoPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/customers" replace />} />
      </Routes>
    </AuthProvider>
  );
}
