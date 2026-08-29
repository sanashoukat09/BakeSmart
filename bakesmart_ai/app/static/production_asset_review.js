(() => {
  "use strict";

  const listUrl = "/api/v1/assets/3d/production-review";
  const decisionUrl = "/api/v1/assets/3d/production-review/decision";
  const canvas = document.getElementById("scene-canvas");
  const statusCard = document.getElementById("loading-card");
  const statusText = document.getElementById("status-text");
  const resetButton = document.getElementById("reset-view");
  const queueSummary = document.getElementById("queue-summary");
  const assetList = document.getElementById("asset-list");
  const assetName = document.getElementById("asset-name");
  const assetCategory = document.getElementById("asset-category");
  const assetSize = document.getElementById("asset-size");
  const assetTriangles = document.getElementById("asset-triangles");
  const assetFileSize = document.getElementById("asset-file-size");
  const assetMaterial = document.getElementById("asset-material");
  const assetSources = document.getElementById("asset-sources");
  const assetValidation = document.getElementById("asset-validation");
  const decisionState = document.getElementById("decision-state");
  const reviewNotes = document.getElementById("review-notes");
  const decisionMessage = document.getElementById("decision-message");
  const nextAssetButton = document.getElementById("next-asset");
  const decisionButtons = [...document.querySelectorAll("[data-decision]")];

  let queue = [];
  let selected = null;
  let renderer = null;

  setDecisionDisabled(true);

  fetch(listUrl, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`review queue returned ${response.status}`);
      return response.json();
    })
    .then(async (payload) => {
      queue = payload.assets || [];
      queueSummary.textContent = `${payload.decided_count}/${payload.candidate_count} decided`;
      if (!queue.length) throw new Error("No eligible geometry-review GLBs were found.");
      const requested = new URLSearchParams(window.location.search).get("asset");
      selected = queue.find((asset) => asset.asset_id === requested) || queue[0];
      renderQueue();
      renderDetails();
      await loadSelectedAsset();
    })
    .catch((error) => showError(error.message));

  resetButton.addEventListener("click", () => renderer?.resetView());
  nextAssetButton.addEventListener("click", () => {
    if (!selected || !queue.length) return;
    const index = queue.findIndex((asset) => asset.asset_id === selected.asset_id);
    const next = queue[(index + 1) % queue.length];
    navigateTo(next.asset_id);
  });

  for (const button of decisionButtons) {
    button.addEventListener("click", () => submitDecision(button.dataset.decision));
  }

  function renderQueue() {
    assetList.replaceChildren();
    for (const asset of queue) {
      const link = document.createElement("a");
      link.href = `?asset=${encodeURIComponent(asset.asset_id)}`;
      if (asset.asset_id === selected.asset_id) link.setAttribute("aria-current", "page");
      const title = document.createElement("strong");
      title.textContent = asset.name;
      const meta = document.createElement("small");
      meta.textContent = `${formatDimensions(asset.dimensions)} • ${asset.category}`;
      const decision = document.createElement("small");
      decision.className = "queue-decision";
      decision.textContent = asset.decision ? humanDecision(asset.decision.decision) : "Pending review";
      link.append(title, meta, decision);
      assetList.append(link);
    }
  }

  function renderDetails() {
    assetName.textContent = selected.name;
    assetCategory.textContent = selected.category;
    assetSize.textContent = formatDimensions(selected.dimensions);
    assetTriangles.textContent = Number(selected.triangle_count).toLocaleString();
    assetFileSize.textContent = formatBytes(selected.file_size_bytes);
    assetMaterial.textContent = selected.material_profile_id;
    assetSources.textContent = selected.source_ids.join(" + ") || "Source metadata unavailable";
    assetValidation.textContent = selected.structurally_valid ? "Passed automated checks" : "Not valid";
    reviewNotes.value = selected.decision?.notes || "";
    if (selected.decision) {
      decisionState.textContent = `Saved: ${humanDecision(selected.decision.decision)} • ${new Date(selected.decision.reviewed_at).toLocaleString()}`;
    } else {
      decisionState.textContent = "No visual decision saved yet.";
    }
    decisionMessage.textContent = "";
  }

  async function loadSelectedAsset() {
    statusCard.classList.remove("error", "ready");
    statusText.textContent = `Loading ${selected.name}…`;
    try {
      renderer = new window.BakeSmartProfessionalRenderer(canvas, {
        onSelection: () => {},
      });
      renderer.installControls();
      await renderer.loadModule({
        url: selected.glb_url,
        id: selected.asset_id,
        label: selected.name,
        translation: [0, 0, 0],
        uniformScale: 1.0,
      });
      renderer.resetView();
      const stats = renderer.stats();
      statusCard.classList.add("ready");
      statusText.textContent = `${selected.name} ready • scale 1.0 • ${stats.triangleCount.toLocaleString()} triangles`;
      resetButton.disabled = false;
      setDecisionDisabled(false);
    } catch (error) {
      showError(`Asset renderer could not load this GLB: ${error.message}`);
    }
  }

  async function submitDecision(decision) {
    if (!selected) return;
    const notes = reviewNotes.value.trim();
    if ((decision === "reject" || decision === "needs_correction") && !notes) {
      decisionMessage.textContent = "Add a short note explaining the problem before saving this decision.";
      reviewNotes.focus();
      return;
    }
    setDecisionDisabled(true);
    decisionMessage.textContent = "Saving review decision…";
    try {
      const response = await fetch(decisionUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: selected.asset_id, decision, notes }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
        throw new Error(detail || `decision endpoint returned ${response.status}`);
      }
      selected.decision = body.record;
      decisionState.textContent = `Saved: ${humanDecision(body.record.decision)} • ${new Date(body.record.reviewed_at).toLocaleString()}`;
      decisionMessage.textContent = body.message;
      renderQueue();
      const decided = queue.filter((asset) => asset.decision).length;
      queueSummary.textContent = `${decided}/${queue.length} decided`;
    } catch (error) {
      decisionMessage.textContent = `Could not save review: ${error.message}`;
    } finally {
      setDecisionDisabled(false);
    }
  }

  function setDecisionDisabled(disabled) {
    for (const button of decisionButtons) button.disabled = disabled;
    nextAssetButton.disabled = disabled;
  }

  function navigateTo(assetId) {
    const url = new URL(window.location.href);
    url.searchParams.set("asset", assetId);
    window.location.href = url.pathname + url.search;
  }

  function formatDimensions(dimensions) {
    const depth = Number(dimensions.depth_m || 0);
    return `${Number(dimensions.width_m).toFixed(2)} × ${depth.toFixed(2)} × ${Number(dimensions.height_m).toFixed(2)} m`;
  }

  function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} B`;
  }

  function humanDecision(value) {
    if (value === "needs_correction") return "Needs correction";
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function showError(message) {
    statusCard.classList.add("error");
    statusText.textContent = message;
    resetButton.disabled = true;
    setDecisionDisabled(true);
  }
})();
