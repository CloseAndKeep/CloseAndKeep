import { PageHeader } from "@/components/ui/page-header";
import { GiftOrderWizard } from "@/components/orders/gift-order-wizard";

export default function NewOrderPage() {
  return (
    <>
      <PageHeader
        title="New cookie order"
        description="Pick prospect and cookie count (temporary $1/cookie), then delivery details."
      />
      <GiftOrderWizard />
    </>
  );
}
