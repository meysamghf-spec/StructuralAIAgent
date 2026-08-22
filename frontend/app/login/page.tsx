import { Suspense } from "react";
import LoginClient from "./LoginClient";

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="muted">Loading sign in…</p>}>
      <LoginClient />
    </Suspense>
  );
}
