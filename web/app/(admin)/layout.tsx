import { AdminShell } from "@/components/layout/admin-shell";
import { AdminGuard } from "@/components/auth/admin-guard";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AdminShell>
      <AdminGuard>{children}</AdminGuard>
    </AdminShell>
  );
}
