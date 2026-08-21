(() => {
  "use strict";

  const mask = document.getElementById("mask-canvas");
  const diagnostic = document.getElementById("diagnostic-canvas");
  const viewport = document.getElementById("canvas-viewport");
  const panel = document.getElementById("missing-panel");
  const summary = document.getElementById("missing-summary");
  const locationText = document.getElementById("missing-location");
  const nextButton = document.getElementById("next-missing-area");
  const toggleButton = document.getElementById("toggle-missing-overlay");
  const validateButton = document.getElementById("validate-mask");
  const message = document.getElementById("message");
  const datasetSelect = document.getElementById("dataset-select");
  const sceneName = document.getElementById("scene-name");

  if (!mask || !diagnostic || !viewport || !panel || !validateButton) return;

  const state = {
    missing: null,
    total: 0,
    regions: [],
    index: 0,
    visible: false,
  };

  function setMessage(text, kind = "") {
    message.textContent = text;
    message.className = `message ${kind}`.trim();
  }

  function clearDiagnostics() {
    state.missing = null;
    state.total = 0;
    state.regions = [];
    state.index = 0;
    state.visible = false;
    panel.hidden = true;
    toggleButton.textContent = "Show unlabelled areas";
    if (diagnostic.width && diagnostic.height) {
      diagnostic.getContext("2d").clearRect(0, 0, diagnostic.width, diagnostic.height);
    }
  }

  function analyseMissing() {
    const width = mask.width;
    const height = mask.height;
    const rgba = mask.getContext("2d").getImageData(0, 0, width, height).data;
    const missing = new Uint8Array(width * height);
    const cellSize = 32;
    const gridWidth = Math.ceil(width / cellSize);
    const gridHeight = Math.ceil(height / cellSize);
    const counts = new Uint32Array(gridWidth * gridHeight);
    const firstX = new Int32Array(counts.length);
    const firstY = new Int32Array(counts.length);
    firstX.fill(-1);
    firstY.fill(-1);

    let total = 0;
    let firstPixel = null;
    for (let p = 0; p < width * height; p += 1) {
      if (rgba[p * 4 + 3] >= 16) continue;
      const x = p % width;
      const y = Math.floor(p / width);
      missing[p] = 1;
      total += 1;
      if (!firstPixel) firstPixel = { x, y };
      const cx = Math.floor(x / cellSize);
      const cy = Math.floor(y / cellSize);
      const c = cy * gridWidth + cx;
      counts[c] += 1;
      if (firstX[c] < 0) {
        firstX[c] = x;
        firstY[c] = y;
      }
    }

    const visited = new Uint8Array(counts.length);
    const regions = [];
    const neighbors = [
      [-1, -1], [0, -1], [1, -1],
      [-1, 0],            [1, 0],
      [-1, 1],  [0, 1],  [1, 1],
    ];

    for (let start = 0; start < counts.length; start += 1) {
      if (!counts[start] || visited[start]) continue;
      const queue = [start];
      visited[start] = 1;
      let cursor = 0;
      let count = 0;
      let minX = gridWidth;
      let minY = gridHeight;
      let maxX = 0;
      let maxY = 0;
      let representative = null;
      while (cursor < queue.length) {
        const cell = queue[cursor++];
        const cx = cell % gridWidth;
        const cy = Math.floor(cell / gridWidth);
        count += counts[cell];
        minX = Math.min(minX, cx);
        minY = Math.min(minY, cy);
        maxX = Math.max(maxX, cx);
        maxY = Math.max(maxY, cy);
        if (!representative) representative = { x: firstX[cell], y: firstY[cell] };
        for (const [dx, dy] of neighbors) {
          const nx = cx + dx;
          const ny = cy + dy;
          if (nx < 0 || ny < 0 || nx >= gridWidth || ny >= gridHeight) continue;
          const next = ny * gridWidth + nx;
          if (!counts[next] || visited[next]) continue;
          visited[next] = 1;
          queue.push(next);
        }
      }
      regions.push({
        count,
        x: representative.x,
        y: representative.y,
        left: minX * cellSize,
        top: minY * cellSize,
        right: Math.min(width - 1, (maxX + 1) * cellSize - 1),
        bottom: Math.min(height - 1, (maxY + 1) * cellSize - 1),
      });
    }
    regions.sort((a, b) => (a.y - b.y) || (a.x - b.x));
    return { total, firstPixel, missing, regions };
  }

  function renderOverlay() {
    diagnostic.width = mask.width;
    diagnostic.height = mask.height;
    diagnostic.style.width = mask.style.width;
    diagnostic.style.height = mask.style.height;
    const ctx = diagnostic.getContext("2d");
    ctx.clearRect(0, 0, diagnostic.width, diagnostic.height);
    if (!state.visible || !state.missing) return;

    const overlay = ctx.createImageData(diagnostic.width, diagnostic.height);
    for (let p = 0; p < state.missing.length; p += 1) {
      if (!state.missing[p]) continue;
      const x = p % diagnostic.width;
      const y = Math.floor(p / diagnostic.width);
      const i = p * 4;
      const alternate = (Math.floor(x / 4) + Math.floor(y / 4)) % 2 === 0;
      overlay.data[i] = 255;
      overlay.data[i + 1] = alternate ? 0 : 230;
      overlay.data[i + 2] = alternate ? 220 : 0;
      overlay.data[i + 3] = 210;
    }
    ctx.putImageData(overlay, 0, 0);

    const region = state.regions[state.index];
    if (!region) return;
    ctx.save();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 5;
    ctx.setLineDash([14, 9]);
    ctx.strokeRect(region.left, region.top, region.right - region.left + 1, region.bottom - region.top + 1);
    ctx.setLineDash([]);
    ctx.fillStyle = "#ff00dc";
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(region.x, region.y, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function updatePanel() {
    panel.hidden = state.total === 0;
    if (!state.total) return;
    summary.textContent = `${state.total.toLocaleString()} unlabelled pixel(s) in ${state.regions.length.toLocaleString()} nearby area(s).`;
    const region = state.regions[state.index];
    locationText.textContent = region
      ? `Area ${state.index + 1} of ${state.regions.length} · first pixel here: x=${region.x}, y=${region.y} · ${region.count.toLocaleString()} pixel(s) in this area.`
      : "No grouped missing area was found.";
    nextButton.disabled = state.regions.length <= 1;
    toggleButton.textContent = state.visible ? "Hide unlabelled areas" : "Show unlabelled areas";
  }

  function focusRegion(index) {
    const region = state.regions[index];
    if (!region) return;
    state.index = index;

    const currentScale = mask.getBoundingClientRect().width / Math.max(mask.width, 1);
    const regionWidth = Math.max(96, region.right - region.left + 141);
    const regionHeight = Math.max(96, region.bottom - region.top + 141);
    const targetScale = Math.min(
      4,
      Math.max(currentScale, (viewport.clientWidth - 80) / regionWidth),
      Math.max(currentScale, (viewport.clientHeight - 80) / regionHeight),
    );
    if (targetScale > currentScale) {
      const width = Math.round(mask.width * targetScale);
      const height = Math.round(mask.height * targetScale);
      document.getElementById("canvas-wrapper").style.width = `${width}px`;
      document.getElementById("canvas-wrapper").style.height = `${height}px`;
      for (const id of ["image-canvas", "mask-canvas", "diagnostic-canvas"]) {
        const canvas = document.getElementById(id);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
      }
    }
    renderOverlay();
    updatePanel();
    requestAnimationFrame(() => {
      const scale = mask.getBoundingClientRect().width / Math.max(mask.width, 1);
      const cx = (region.left + region.right + 1) * 0.5 * scale;
      const cy = (region.top + region.bottom + 1) * 0.5 * scale;
      viewport.scrollLeft = Math.max(0, cx - viewport.clientWidth / 2 + 16);
      viewport.scrollTop = Math.max(0, cy - viewport.clientHeight / 2 + 16);
    });
  }

  async function validateWithFinder(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const dataset = datasetSelect.value || "real_v2";
    const sceneId = (sceneName.textContent || "").trim();
    if (!sceneId || sceneId === "No scene") return;
    setMessage("Validating mask…");
    try {
      const response = await fetch(
        `/api/scenes/${encodeURIComponent(dataset)}/${encodeURIComponent(sceneId)}/validate`,
        {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mask_png_base64: mask.toDataURL("image/png"),
            annotator_id: document.getElementById("annotator-id").value.trim() || null,
          }),
        },
      );
      if (!response.ok) {
        let detail = `Validation failed (${response.status})`;
        try { detail = (await response.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const result = await response.json();
      if (result.complete) {
        clearDiagnostics();
        setMessage("Validation passed: all pixels are assigned to class 0-6.", "success");
        return;
      }

      const found = analyseMissing();
      state.missing = found.missing;
      state.total = found.total;
      state.regions = found.regions;
      state.index = 0;
      state.visible = true;
      updatePanel();
      renderOverlay();
      if (found.regions.length) focusRegion(0);

      const coverage = Math.round((result.coverage_fraction || 0) * 10000) / 100;
      if (found.total !== result.unlabelled_pixels) {
        setMessage(
          `Server found ${result.unlabelled_pixels.toLocaleString()} unlabelled pixel(s), while the browser located ${found.total.toLocaleString()}. Reload the scene and validate again.`,
          "error",
        );
        return;
      }
      setMessage(
        `Validation incomplete: ${result.unlabelled_pixels.toLocaleString()} pixel(s) remain unlabelled in ${found.regions.length.toLocaleString()} nearby area(s) (${coverage}% covered). First missing pixel: x=${found.firstPixel.x}, y=${found.firstPixel.y}. The first area is highlighted and centred.`,
        "error",
      );
    } catch (error) {
      setMessage(error.message, "error");
    }
  }

  validateButton.addEventListener("click", validateWithFinder, true);
  nextButton.addEventListener("click", () => {
    if (!state.regions.length) return;
    focusRegion((state.index + 1) % state.regions.length);
  });
  toggleButton.addEventListener("click", () => {
    if (!state.missing) return;
    state.visible = !state.visible;
    renderOverlay();
    updatePanel();
  });
  mask.addEventListener("pointerdown", clearDiagnostics, true);
  document.getElementById("undo-button").addEventListener("click", clearDiagnostics, true);
  document.getElementById("redo-button").addEventListener("click", clearDiagnostics, true);
  document.getElementById("fill-button").addEventListener("click", clearDiagnostics, true);
  document.getElementById("clear-button").addEventListener("click", clearDiagnostics, true);
})();
