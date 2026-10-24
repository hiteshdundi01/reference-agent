import { LogOut, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { forget } from "../auth";
import type { User } from "../types";

export function Header({ user }: Readonly<{ user: User }>) {
  const navigate = useNavigate();
  return (
    <header className="header">
      <Link to="/" className="brand">
        <ShieldCheck size={20} aria-hidden="true" />
        Acme refund desk
      </Link>
      <div className="who">
        <span>
          {user.name} <span className="muted-on-dark">· {user.role}</span>
        </span>
        <button
          type="button"
          className="quiet"
          onClick={() => {
            forget();
            void navigate("/sign-in");
          }}
        >
          <LogOut size={16} aria-hidden="true" /> Sign out
        </button>
      </div>
    </header>
  );
}
