import { Suspense } from "react";
import RegisterClient from "./RegisterClient";

export default function RegisterPage() {
  return (
    <Suspense fallback={<p className="muted">Loading sign up…</p>}>
      <RegisterClient />
    </Suspense>
  );
}
