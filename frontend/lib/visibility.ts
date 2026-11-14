/**
 * What the public app shows. Owner, 2026-11-14: "The research part should only stay on our side, nothing to be
 * accessed by public, only the module and access to evidence." Research surfaces (the Strategy Truth Lab, the crowd
 * positioning and prediction-market panels) are off unless NEXT_PUBLIC_RESEARCH_PUBLIC=1 (internal preview only).
 */
export const RESEARCH_PUBLIC = process.env.NEXT_PUBLIC_RESEARCH_PUBLIC === "1";
