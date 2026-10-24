import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useSignedIn } from "./auth";
import { Header } from "./components/Header";
import { Queue } from "./pages/Queue";
import { RequestPage } from "./pages/RequestPage";
import { SignIn } from "./pages/SignIn";

function SignedIn({ children }: Readonly<{ children: ReactNode }>) {
  const who = useSignedIn();
  if (!who) return <Navigate to="/sign-in" replace />;
  return (
    <>
      <Header user={who} />
      <main className="page">{children}</main>
    </>
  );
}

export function Pages() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route
        path="/"
        element={
          <SignedIn>
            <Queue />
          </SignedIn>
        }
      />
      <Route
        path="/requests/:id"
        element={
          <SignedIn>
            <RequestPage />
          </SignedIn>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Pages />
    </BrowserRouter>
  );
}
