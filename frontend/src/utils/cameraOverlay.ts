/** Map source-image pixel edges through centered CSS object-fit: contain. */
export function cameraOverlayRect(
  bbox: [number, number, number, number],
  imageWidth: number, imageHeight: number,
  viewportWidth: number, viewportHeight: number,
) {
  const scale = Math.min(viewportWidth / imageWidth, viewportHeight / imageHeight);
  const offsetX = (viewportWidth - imageWidth * scale) / 2;
  const offsetY = (viewportHeight - imageHeight * scale) / 2;
  const [x1, y1, x2, y2] = bbox;
  return {
    left: x1 * scale + offsetX,
    top: y1 * scale + offsetY,
    width: (x2 - x1) * scale,
    height: (y2 - y1) * scale,
  };
}
