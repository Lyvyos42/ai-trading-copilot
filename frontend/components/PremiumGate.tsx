"use client";
import { useAuth, type UserTier } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";

interface PremiumGateProps {
  children: React.ReactNode;
  requiredTier: UserTier;
  feature: string;
  reason?: string;
}

/**
 * Wraps a page/section — shows UpgradeModal overlay if user tier is below `requiredTier`.
 * The gated content renders blurred behind the modal so users can see what they're missing.
 */
export function PremiumGate({ children, requiredTier, feature, reason }: PremiumGateProps) {
  const { isAtLeast, loading } = useAuth();

  if (loading) return <>{children}</>;

  const hasAccess = isAtLeast(requiredTier);

  if (hasAccess) return <>{children}</>;

  return (
    <>
      <div className="pointer-events-none select-none opacity-40 blur-[2px]">
        {children}
      </div>
      <UpgradeModal
        isOpen={true}
        onClose={() => {}} // Can't dismiss — must upgrade
        feature={feature}
        requiredTier={requiredTier === "retail" ? "retail" : requiredTier === "pro" ? "pro" : "retail"}
        reason={reason}
      />
    </>
  );
}
