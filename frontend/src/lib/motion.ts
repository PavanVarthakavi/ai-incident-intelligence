/** "smooth", unless the user asked the system to reduce motion. */
export function scrollBehavior(): ScrollBehavior {
  return globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}
