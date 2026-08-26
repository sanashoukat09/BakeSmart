(() => {
  const parts = window.location.pathname.split('/').filter(Boolean);
  if (parts.length !== 3 || parts[0] !== 'preview') return;
  const designId = parts[1];
  const packageId = parts[2];
  if (!/^design-[a-f0-9]{20}$/.test(designId)) return;
  if (!['essential', 'balanced', 'statement'].includes(packageId)) return;
  document.getElementById('preview-image').src =
    `/api/v1/designs/${designId}/previews/${packageId}.png`;
  document.getElementById('package-title').textContent =
    `${packageId[0].toUpperCase()}${packageId.slice(1)} package`;
})();
