(() => {
  "use strict";

  const canvas = document.getElementById("scene-canvas");
  const statusCard = document.getElementById("loading-card");
  const statusText = document.getElementById("status-text");
  const resetButton = document.getElementById("reset-view");
  const list = document.getElementById("asset-list");
  let renderer = null;

  fetch("/api/v1/assets/3d/cake-references", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`reference catalog returned ${response.status}`);
      return response.json();
    })
    .then(async (payload) => {
      const assets = payload.assets || [];
      document.getElementById("queue-summary").textContent = `${assets.length} verified`;
      if (!assets.length) throw new Error("No cake references are available.");
      const requested = new URLSearchParams(window.location.search).get("source");
      const selected = assets.find((asset) => asset.source_id === requested) || assets[0];
      for (const asset of assets) {
        const link = document.createElement("a");
        link.href = `?source=${encodeURIComponent(asset.source_id)}`;
        if (asset.source_id === selected.source_id) link.setAttribute("aria-current", "page");
        const title = document.createElement("strong");
        title.textContent = asset.source_id.replace(/^ph-/, "").replaceAll("-", " ");
        const meta = document.createElement("small");
        meta.textContent = `${asset.triangle_count.toLocaleString()} triangles`;
        link.append(title, meta);
        list.append(link);
      }
      renderDetails(selected);
      renderer = new window.BakeSmartProfessionalRenderer(canvas, { onSelection: () => {} });
      renderer.installControls();
      await renderer.loadModule({
        url: selected.glb_url,
        id: selected.source_id,
        label: selected.source_id,
        translation: [0, 0, 0],
        uniformScale: 1.0,
      });
      renderer.resetView();
      const stats = renderer.stats();
      statusCard.classList.add("ready");
      statusText.textContent = `Ready • ${stats.triangleCount.toLocaleString()} triangles • reference only`;
      resetButton.disabled = false;
    })
    .catch((error) => {
      statusCard.classList.add("error");
      statusText.textContent = error.message;
    });

  resetButton.addEventListener("click", () => renderer?.resetView());

  function renderDetails(asset) {
    const dimensions = asset.dimensions_m;
    document.getElementById("asset-name").textContent = asset.source_id.replace(/^ph-/, "").replaceAll("-", " ");
    document.getElementById("asset-size").textContent = `${dimensions.width.toFixed(3)} × ${dimensions.depth.toFixed(3)} × ${dimensions.height.toFixed(3)} m`;
    document.getElementById("asset-triangles").textContent = asset.triangle_count.toLocaleString();
    document.getElementById("asset-textures").textContent = `${asset.texture_count} embedded 1K maps`;
    document.getElementById("asset-license").textContent = asset.license;
  }
})();
