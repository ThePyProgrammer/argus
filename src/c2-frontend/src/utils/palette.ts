/** Okabe-Ito colorblind-safe 8-color palette (hex). */
export const OKABE_ITO: [string, string, string, string, string, string, string, string] = [
  '#0072B2', // Blue
  '#E69F00', // Orange
  '#56B4E9', // Sky Blue
  '#009E73', // Bluish Green
  '#F0E442', // Yellow
  '#D55E00', // Vermillion
  '#CC79A7', // Reddish Purple
  '#000000', // Black
];

/** Okabe-Ito palette as RGB tuples [0-255]. */
export const OKABE_ITO_RGB: [number, number, number][] = [
  [0, 114, 178],
  [230, 159, 0],
  [86, 180, 233],
  [0, 158, 115],
  [240, 228, 66],
  [213, 94, 0],
  [204, 121, 167],
  [0, 0, 0],
];

/** Get hex color for a robot by index (wraps around at 8). */
export function robotColor(index: number): string {
  return OKABE_ITO[index % 8];
}
