import { useAuth } from "../context/AuthContext";

export default function CustomersPage() {
  const { logout } = useAuth();
  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h1>Customers</h1>
        <button onClick={logout}>Sign out</button>
      </div>
      <p>Customer list — Phase 3 implementation.</p>
    </div>
  );
}
