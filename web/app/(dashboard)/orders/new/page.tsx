import { PageHeader } from "@/components/ui/page-header";
import { GiftOrderWizard } from "@/components/orders/gift-order-wizard";

export default function NewOrderPage() {
  return (
    <>
      <PageHeader
        title="New cookie order"
        description="Walk through prospect and delivery details for cookie sends."
      />
      <GiftOrderWizard />
    </>
  );
}
