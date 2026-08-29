(() => {
  "use strict";

  const canvas = document.getElementById("scene-canvas");
  const statusCard = document.getElementById("loading-card");
  const statusText = document.getElementById("status-text");
  const resetButton = document.getElementById("reset-view");
  const downloadLink = document.getElementById("download-glb");
  const photoFallback = document.getElementById("photo-fallback");
  const selectionCard = document.getElementById("selection-card");
  const selectionName = document.getElementById("selection-name");
  const designId = window.location.pathname.split("/").filter(Boolean).pop();
  const packageId = new URLSearchParams(window.location.search).get("package") || "balanced";

  if (!/^design-[0-9a-f]{20}$/.test(designId || "")) {
    showError("This BakeSmart scene link is invalid.");
    return;
  }

  const glbUrl = `/api/v1/designs/${encodeURIComponent(designId)}/scene.glb`;
  downloadLink.href = glbUrl;
  downloadLink.download = `${designId}.glb`;
  photoFallback.href = `/preview/${encodeURIComponent(designId)}/${encodeURIComponent(packageId)}`;

  let renderer;
  try {
    renderer = new window.BakeSmartProfessionalRenderer(canvas, {
      onSelection: (module) => {
        if (!module) {
          selectionCard.hidden = true;
          return;
        }
        selectionName.textContent = module.label;
        selectionCard.hidden = false;
      },
    });
    renderer.installControls();
  } catch (error) {
    showError(`The local 3D renderer could not start: ${error.message}`);
    return;
  }

  renderer.loadModule({
    url: glbUrl,
    id: designId,
    label: "Procedural combined planning scene",
    translation: [0, 0, 0],
    uniformScale: 1.0,
  }).then(() => {
    renderer.resetView();
    const stats = renderer.stats();
    statusCard.classList.add("ready");
    statusText.textContent =
      `Stage-7 renderer ready • ${stats.vertexCount.toLocaleString()} vertices • ` +
      `${stats.triangleCount.toLocaleString()} triangles`;
  }).catch((error) => {
    showError(`The 3D scene could not be opened. ${error.message}`);
  });

  resetButton.addEventListener("click", () => renderer.resetView());

  function showError(message) {
    statusCard.classList.add("error");
    statusText.textContent = message;
    photoFallback.hidden = false;
  }
})();
