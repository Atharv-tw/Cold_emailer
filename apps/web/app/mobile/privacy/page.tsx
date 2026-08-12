import type { Metadata } from "next";

import PrivacyPolicyContent from "@/components/PrivacyPolicyContent";
import StaticPage from "@/components/StaticPage";

export const metadata: Metadata = { title: "Privacy policy" };

export default function PrivacyPage() {
  return (
    <StaticPage title="Privacy policy" updated="12 August 2026">
      <PrivacyPolicyContent />
    </StaticPage>
  );
}
