import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variants = {
  primary:
    "bg-wood text-white shadow-sm hover:bg-wood-dark border border-transparent",
  secondary:
    "bg-white text-espresso border border-stone-200/90 shadow-sm hover:bg-stone-50",
  ghost: "text-stone-600 hover:bg-stone-100/80 border border-transparent",
} as const;

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: keyof typeof variants;
  }
>(({ className, variant = "primary", type = "button", ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    className={cn(
      "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wood/40 focus-visible:ring-offset-2 focus-visible:ring-offset-cream",
      variants[variant],
      className
    )}
    {...props}
  />
));
Button.displayName = "Button";
