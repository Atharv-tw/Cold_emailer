import DesktopChrome from "@/components/DesktopChrome";
import PurchasePanel from "@/components/PurchasePanel";

// TEMPORARY - visual check only, deleted after the screenshot.
export default function UiPreview() {
  return (
    <DesktopChrome
      user={{
        id: "1",
        email: "schoolworkidisbekar@gmail.com",
        name: "Atharv Tiwari",
        avatar: "",
        connected: true,
        missing_scopes: [],
        profile_complete: true,
        calendar_connected: false,
        is_paid: false,
        is_admin: false,
      }}
      ops={null}
    >
      <div className="page-header">
        <div>
          <h1>Get the contact pool</h1>
          <p>Pay by UPI, send the screenshot, and we approve it by hand</p>
        </div>
      </div>
      <div className="max-w-4xl">
        <PurchasePanel
          billing={{
            available: true,
            price_inr: 99,
            upi_id: "9971185480@slc",
            payee_name: "Outreach",
            request_status: "",
            requested_at: null,
            is_paid: false,
          }}
        />
      </div>
    </DesktopChrome>
  );
}
