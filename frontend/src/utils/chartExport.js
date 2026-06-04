export const exportChartAsPNG = (containerSelector, filename) => {
  const container = document.querySelector(containerSelector);
  if (!container) return;

  const svgElement = container.querySelector('svg');
  if (!svgElement) return;

  // Clone the SVG element so we can safely mutate it for export
  const clonedSvgElement = svgElement.cloneNode(true);

  // Set absolute width and height on the clone instead of percentages
  const { width, height } = svgElement.getBoundingClientRect();
  clonedSvgElement.setAttribute('width', width);
  clonedSvgElement.setAttribute('height', height);

  // Create a canvas to draw the SVG onto
  const canvas = document.createElement('canvas');
  // High-res export
  const scale = 2;
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');

  // Fill background
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-elevated') || '#1e1e24';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);

  // Serialize the SVG to a string
  const serializer = new XMLSerializer();
  let svgString = serializer.serializeToString(clonedSvgElement);

  // Recharts often relies on CSS variables for colors, we must inline them
  // A robust way without html2canvas is tricky, but let's try replacing common vars
  const style = getComputedStyle(document.body);
  const varsToReplace = ['--text-muted', '--text-secondary', '--text-primary', '--border-subtle', '--border-default', '--bg-elevated', '--accent-teal', '--accent-amber', '--color-danger'];
  varsToReplace.forEach(v => {
    const val = style.getPropertyValue(v).trim();
    if (val) {
      svgString = svgString.replaceAll(`var(${v})`, val);
    }
  });

  // Convert SVG string to data URL
  const img = new Image();
  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  img.onload = () => {
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(url);
    
    // Download the image
    const pngDataUrl = canvas.toDataURL('image/png');
    const downloadLink = document.createElement('a');
    downloadLink.href = pngDataUrl;
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };
  
  img.src = url;
};
