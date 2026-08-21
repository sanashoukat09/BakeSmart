(() => {
  "use strict";

  const button = document.getElementById("suggest-mask");
  const maskCanvas = document.getElementById("mask-canvas");
  const diagnosticCanvas = document.getElementById("diagnostic-canvas");
  const datasetSelect = document.getElementById("dataset-select");
  const sceneName = document.getElementById("scene-name");
  const sceneSize = document.getElementById("scene-size");
  const annotatorId = document.getElementById("annotator-id");
  const statusPill = document.getElementById("status-pill");
  const message = document.getElementById("message");
  const missingPanel = document.getElementById("missing-panel");

  if (!button || !maskCanvas || !datasetSelect || !sceneName) return;

  function setMessage(text, kind = "") {
    if (!message) return;
    message.textContent = text;
    message.className = `message ${kind}`.trim();
  }

  function currentSceneId() {
    const value = (sceneName.textContent || "").trim();
    return value && value !== "No scene" ? value : null;
  }

  function hasPaintedPixels() {
    if (!maskCanvas.width || !maskCanvas.height) return false;
    const data = maskCanvas
      .getContext("2d")
      .getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
    for (let index = 3; index < data.length; index += 4) {
      if (data[index] >= 16) return true;
    }
    return false;
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Could not load the suggested mask overlay."));
      image.src = url;
    });
  }

  async function refreshMask(dataset, sceneId) {
    const image = await loadImage(
      `/api/scenes/${encodeURIComponent(dataset)}/${encodeURIComponent(sceneId)}/mask-overlay?t=${Date.now()}`,
    );
    const context = maskCanvas.getContext("2d");
    context.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    context.drawImage(image, 0, 0, maskCanvas.width, maskCanvas.height);
    if (diagnosticCanvas) {
      diagnosticCanvas
        .getContext("2d")
        .clearRect(0, 0, diagnosticCanvas.width, diagnosticCanvas.height);
    }
    if (missingPanel) missingPanel.hidden = true;
  }

  async function suggestMask() {
    const sceneId = currentSceneId();
    if (!sceneId) {
      setMessage("Open a venue image before requesting a suggested mask.", "error");
      return;
    }
    const replaceExisting = hasPaintedPixels();
    if (
      replaceExisting &&
      !window.confirm(
        "Replace the current mask with BakeSmart's machine suggestion? Any unsaved painting on this image will be replaced.",
      )
    ) {
      return;
    }

    button.disabled = true;
    const previousLabel = button.textContent;
    button.textContent = "Suggesting…";
    setMessage(
      "Running BakeSmart's local venue model. This may take a few seconds on the first image…",
    );
    try {
      const dataset = datasetSelect.value || "real_v2";
      const response = await fetch(
        `/api/scenes/${encodeURIComponent(dataset)}/${encodeURIComponent(sceneId)}/suggest`,
        {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            annotator_id: (annotatorId?.value || "").trim() || null,
            replace_existing: replaceExisting,
          }),
        },
      );
      if (!response.ok) {
        let detail = `Suggestion failed (${response.status})`;
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const result = await response.json();
      await refreshMask(dataset, sceneId);
      if (statusPill) {
        statusPill.textContent = "draft_in_progress";
        statusPill.classList.remove("complete");
      }
      if (sceneSize && sceneSize.textContent.includes("·")) {
        sceneSize.textContent = `${sceneSize.textContent.split("·")[0].trim()} · draft_in_progress`;
      }
      const version = result.suggestion_model_version || "local venue model";
      setMessage(
        `Suggested mask loaded from ${version}. Review every region, correct mistakes, then Validate mask before completion.`,
        "success",
      );
    } catch (error) {
      setMessage(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = previousLabel;
    }
  }

  button.addEventListener("click", suggestMask);
})();
