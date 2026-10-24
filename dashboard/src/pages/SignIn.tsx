import { LogIn } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { signIn } from "../api";
import { remember } from "../auth";
import { useAction } from "../useAction";

export function SignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const signingIn = useAction(async () => {
    remember(await signIn(email, password));
    await navigate("/");
  });

  return (
    <main className="sign-in">
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          void signingIn.run();
        }}
      >
        <h1>Acme refund desk</h1>
        <label className="field">
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
            required
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
            required
          />
        </label>
        <button type="submit" className="primary" disabled={signingIn.busy}>
          <LogIn size={16} aria-hidden="true" /> Sign in
        </button>
        {signingIn.error && (
          <p className="note tone-danger" role="alert">
            {signingIn.error}
          </p>
        )}
      </form>
    </main>
  );
}
