/** Single source of truth for the product name.
 *  All user-visible text imports from here — never hardcodes the string.
 *  Rename: change this file only. (TDD D11)
 */
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Blunderstanding";
export const APP_TAGLINE = "Your games. Your habits. Your coach.";
