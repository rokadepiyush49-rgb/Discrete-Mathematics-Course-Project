export const int = (value: number) => Math.round(value).toLocaleString("en-US");

export const pct = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

export const fixed = (value: number, digits = 3) => value.toFixed(digits);

export function duration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return minutes ? `${minutes} min ${rest} s` : `${rest} s`;
}

export const km = (metres: number) => `${(metres / 1000).toFixed(2)} km`;

/** Exact integers that exceed the safe range arrive as strings. */
export function bigInt(value: string) {
  return BigInt(value).toLocaleString("en-US");
}

export function ordinal(value: number) {
  const tens = value % 100;
  const suffix =
    tens >= 11 && tens <= 13 ? "th" : (["th", "st", "nd", "rd"][value % 10] ?? "th");
  return `${value.toLocaleString("en-US")}${suffix}`;
}
