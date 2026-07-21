import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

type BrandLogoProps = {
  href?: string;
  /** Full wordmark vs icon-only mark (for compact nav / favicon-style UI). */
  variant?: "full" | "mark";
  className?: string;
  priority?: boolean;
};

export function BrandLogo({
  href = "/",
  variant = "full",
  className,
  priority = false,
}: BrandLogoProps) {
  const image =
    variant === "mark" ? (
      <Image
        src="/brand/mark.png"
        alt="CloseAndKeep"
        width={40}
        height={52}
        className="h-8 w-auto"
        priority={priority}
      />
    ) : (
      <Image
        src="/brand/logo.png"
        alt="CloseAndKeep"
        width={220}
        height={58}
        className="h-8 w-auto sm:h-9"
        priority={priority}
      />
    );

  if (!href) {
    return <span className={cn("inline-flex items-center", className)}>{image}</span>;
  }

  return (
    <Link
      href={href}
      className={cn("inline-flex items-center", className)}
      aria-label="CloseAndKeep home"
    >
      {image}
    </Link>
  );
}
