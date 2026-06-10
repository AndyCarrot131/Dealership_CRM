import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { to: "/customers", label: "Customers" },
  { to: "/contacts", label: "Contacts" },
  { to: "/inventory", label: "Inventory" },
  { to: "/style", label: "Style" },
  { to: "/outreach", label: "Outreach" },
  { to: "/inbox", label: "Inbox" },
  { to: "/assistant", label: "✦ Assistant" },
  { to: "/settings", label: "Settings" },
];

export default function NavBar() {
  const { logout } = useAuth();
  return (
    <nav className="nav">
      <span className="nav-brand">Dealer CRM</span>
      {NAV_LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
        >
          {link.label}
        </NavLink>
      ))}
      <div className="nav-spacer" />
      <button onClick={logout} className="nav-signout">
        Sign out
      </button>
    </nav>
  );
}
