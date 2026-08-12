import type { Metadata } from "next";

import StaticPage from "@/components/StaticPage";
import TermsOfServiceContent from "@/components/TermsOfServiceContent";

export const metadata: Metadata = { title: "Terms of service" };

export default function TermsPage() {
  return (
    <StaticPage title="Terms of service" updated="12 August 2026">
      <TermsOfServiceContent />
    </StaticPage>
  );
}
