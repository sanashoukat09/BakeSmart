(() => {
  "use strict";

  const maskCanvas = document.getElementById("mask-canvas");
  const toolCanvas = document.getElementById("tool-canvas");
  const toolContext = toolCanvas.getContext("2d");
  const polygonButton = document.getElementById("polygon-tool");
  const smartObjectButton = document.getElementById("smart-object-tool");
  const finishPolygonButton = document.getElementById("finish-polygon");
  const cancelButton = document.getElementById("cancel-smart-tool");
  const hint = document.getElementById("smart-tool-hint");
  const message = document.getElementById("message");
  const datasetSelect = document.getElementById("dataset-select");
  const sceneName = document.getElementById("scene-name");

  if (!maskCanvas || !toolCanvas || !polygonButton || !smartObjectButton) return;

  const state = {
    mode: null,
    polygon: [],
    dragStart: null,
    dragCurrent: null,
    busy: false,
  };

  function setMessage(text, kind = "") {
    message.textContent = text;
    message.className = `message ${kind}`.trim();
  }

  function syncToolCanvas() {
    if (!maskCanvas.width || !maskCanvas.height) return;
    if (toolCanvas.width !== maskCanvas.width) toolCanvas.width = maskCanvas.width;
    if (toolCanvas.height !== maskCanvas.height) toolCanvas.height = maskCanvas.height;
    toolCanvas.style.width = maskCanvas.style.width || `${maskCanvas.width}px`;
    toolCanvas.style.height = maskCanvas.style.height || `${maskCanvas.height}px`;
  }

  function selectedClass() {
    const button = document.querySelector(".class-button.active:not(:disabled)");
    if (!button) return null;
    const classId = Number(button.dataset.classId);
    if (!Number.isInteger(classId) || classId < 0 || classId > 5) return null;
    const swatch = button.querySelector(".swatch");
    const color = swatch ? getComputedStyle(swatch).backgroundColor : null;
    return color ? { classId, color } : null;
  }

  function colorToRgb(color) {
    const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if (!match) throw new Error("Could not read selected class colour.");
    return [Number(match[1]), Number(match[2]), Number(match[3])];
  }

  function pointFromEvent(event) {
    const bounds = maskCanvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(maskCanvas.width, (event.clientX - bounds.left) * maskCanvas.width / bounds.width)),
      y: Math.max(0, Math.min(maskCanvas.height, (event.clientY - bounds.top) * maskCanvas.height / bounds.height)),
    };
  }

  function setMode(mode) {
    if (state.busy) return;
    if (mode && !selectedClass()) {
      setMessage("Select Wall, Floor, Door, Window, Furniture or Outlet first.", "error");
      return;
    }
    state.mode = state.mode === mode ? null : mode;
    state.polygon = [];
    state.dragStart = null;
    state.dragCurrent = null;
    polygonButton.classList.toggle("active", state.mode === "polygon");
    smartObjectButton.classList.toggle("active", state.mode === "smart-object");
    finishPolygonButton.disabled = state.mode !== "polygon" || state.polygon.length < 3;
    cancelButton.disabled = !state.mode;
    syncToolCanvas();
    drawGuide();
    if (state.mode === "polygon") {
      hint.textContent = "Polygon Fill active: click around the region, then press Finish polygon. Right-click removes the last point.";
    } else if (state.mode === "smart-object") {
      hint.textContent = "Smart Object active: drag a box slightly around one object. Leave a little background around it for cleaner edges.";
    } else {
      hint.textContent = "Polygon Fill: click around a large region. Smart Object: drag a rough box around one object.";
    }
  }

  function cancelTool() {
    state.mode = null;
    state.polygon = [];
    state.dragStart = null;
    state.dragCurrent = null;
    polygonButton.classList.remove("active");
    smartObjectButton.classList.remove("active");
    finishPolygonButton.disabled = true;
    cancelButton.disabled = true;
    hint.textContent = "Polygon Fill: click around a large region. Smart Object: drag a rough box around one object.";
    drawGuide();
  }

  function drawGuide() {
    syncToolCanvas();
    toolContext.clearRect(0, 0, toolCanvas.width, toolCanvas.height);
    toolContext.save();
    toolContext.lineWidth = Math.max(2, maskCanvas.width / 700);
    toolContext.strokeStyle = "rgba(255,255,255,0.95)";
    toolContext.fillStyle = "rgba(255,255,255,0.95)";
    toolContext.setLineDash([10, 6]);

    if (state.mode === "polygon" && state.polygon.length) {
      toolContext.beginPath();
      toolContext.moveTo(state.polygon[0].x, state.polygon[0].y);
      for (const point of state.polygon.slice(1)) toolContext.lineTo(point.x, point.y);
      toolContext.stroke();
      toolContext.setLineDash([]);
      for (const point of state.polygon) {
        toolContext.beginPath();
        toolContext.arc(point.x, point.y, Math.max(4, maskCanvas.width / 250), 0, Math.PI * 2);
        toolContext.fill();
      }
    }

    if (state.mode === "smart-object" && state.dragStart && state.dragCurrent) {
      const rectangle = rectangleFromPoints(state.dragStart, state.dragCurrent);
      toolContext.strokeRect(rectangle.x, rectangle.y, rectangle.width, rectangle.height);
    }
    toolContext.restore();
  }

  function rectangleFromPoints(a, b) {
    return {
      x: Math.round(Math.min(a.x, b.x)),
      y: Math.round(Math.min(a.y, b.y)),
      width: Math.round(Math.abs(a.x - b.x)),
      height: Math.round(Math.abs(a.y - b.y)),
    };
  }

  function notifyMaskChanged() {
    window.dispatchEvent(new CustomEvent("bakesmart:mask-changed"));
    window.dispatchEvent(new CustomEvent("bakesmart:diagnostics-clear"));
  }

  function finishPolygon() {
    if (state.mode !== "polygon" || state.polygon.length < 3) {
      setMessage("Polygon Fill needs at least 3 points.", "error");
      return;
    }
    const selected = selectedClass();
    if (!selected) {
      setMessage("Select a class before finishing the polygon.", "error");
      return;
    }
    const context = maskCanvas.getContext("2d");
    context.save();
    context.globalCompositeOperation = "source-over";
    context.fillStyle = selected.color;
    context.beginPath();
    context.moveTo(state.polygon[0].x, state.polygon[0].y);
    for (const point of state.polygon.slice(1)) context.lineTo(point.x, point.y);
    context.closePath();
    context.fill();
    context.restore();
    notifyMaskChanged();
    setMessage(`Polygon filled as class ${selected.classId}. Review the boundary, then continue.`, "success");
    state.polygon = [];
    finishPolygonButton.disabled = true;
    drawGuide();
  }

  async function applySmartObject(rectangle) {
    const selected = selectedClass();
    if (!selected) {
      setMessage("Select a class before using Smart Object.", "error");
      return;
    }
    if (rectangle.width < 5 || rectangle.height < 5) {
      setMessage("Draw a larger Smart Object box.", "error");
      return;
    }
    const dataset = datasetSelect.value || "real_v2";
    const sceneId = sceneName.textContent.trim();
    if (!sceneId || sceneId === "No scene") return;

    state.busy = true;
    smartObjectButton.disabled = true;
    polygonButton.disabled = true;
    setMessage("Finding the object boundary…");
    try {
      const response = await fetch(
        `/api/scenes/${encodeURIComponent(dataset)}/${encodeURIComponent(sceneId)}/smart-object`,
        {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(rectangle),
        },
      );
      if (!response.ok) {
        let detail = `Smart Object failed (${response.status})`;
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const selectedPixels = Number(response.headers.get("X-Selected-Pixels") || 0);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      try {
        const selectionImage = await loadImage(url);
        applyBinarySelection(selectionImage, selected.color);
      } finally {
        URL.revokeObjectURL(url);
      }
      notifyMaskChanged();
      setMessage(
        `Smart Object labelled ${selectedPixels.toLocaleString()} pixel(s) as class ${selected.classId}. Review the edge and use the brush only if needed.`,
        "success",
      );
    } catch (error) {
      setMessage(error.message, "error");
    } finally {
      state.busy = false;
      smartObjectButton.disabled = false;
      polygonButton.disabled = false;
      state.dragStart = null;
      state.dragCurrent = null;
      drawGuide();
    }
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Could not load Smart Object selection."));
      image.src = url;
    });
  }

  function applyBinarySelection(selectionImage, color) {
    const selectionCanvas = document.createElement("canvas");
    selectionCanvas.width = maskCanvas.width;
    selectionCanvas.height = maskCanvas.height;
    const selectionContext = selectionCanvas.getContext("2d");
    selectionContext.drawImage(selectionImage, 0, 0, selectionCanvas.width, selectionCanvas.height);
    const selection = selectionContext.getImageData(0, 0, selectionCanvas.width, selectionCanvas.height).data;
    const maskContext = maskCanvas.getContext("2d");
    const target = maskContext.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
    const rgb = colorToRgb(color);
    for (let index = 0; index < selection.length; index += 4) {
      if (selection[index] < 128) continue;
      target.data[index] = rgb[0];
      target.data[index + 1] = rgb[1];
      target.data[index + 2] = rgb[2];
      target.data[index + 3] = 255;
    }
    maskContext.putImageData(target, 0, 0);
  }

  maskCanvas.addEventListener("pointerdown", (event) => {
    if (!state.mode || state.busy) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    syncToolCanvas();
    const point = pointFromEvent(event);
    if (state.mode === "polygon") {
      if (event.button === 2) {
        state.polygon.pop();
      } else {
        state.polygon.push(point);
      }
      finishPolygonButton.disabled = state.polygon.length < 3;
      drawGuide();
      return;
    }
    if (state.mode === "smart-object" && event.button === 0) {
      state.dragStart = point;
      state.dragCurrent = point;
      try { maskCanvas.setPointerCapture(event.pointerId); } catch (_) {}
      drawGuide();
    }
  }, true);

  maskCanvas.addEventListener("pointermove", (event) => {
    if (state.mode !== "smart-object" || !state.dragStart || state.busy) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    state.dragCurrent = pointFromEvent(event);
    drawGuide();
  }, true);

  maskCanvas.addEventListener("pointerup", (event) => {
    if (state.mode !== "smart-object" || !state.dragStart || state.busy) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    state.dragCurrent = pointFromEvent(event);
    try { maskCanvas.releasePointerCapture(event.pointerId); } catch (_) {}
    const rectangle = rectangleFromPoints(state.dragStart, state.dragCurrent);
    applySmartObject(rectangle);
  }, true);

  maskCanvas.addEventListener("contextmenu", (event) => {
    if (state.mode === "polygon") event.preventDefault();
  });

  polygonButton.addEventListener("click", () => setMode("polygon"));
  smartObjectButton.addEventListener("click", () => setMode("smart-object"));
  finishPolygonButton.addEventListener("click", finishPolygon);
  cancelButton.addEventListener("click", cancelTool);
  document.getElementById("previous-scene").addEventListener("click", cancelTool, true);
  document.getElementById("next-scene").addEventListener("click", cancelTool, true);
  datasetSelect.addEventListener("change", cancelTool, true);
  window.addEventListener("resize", () => setTimeout(syncToolCanvas, 0));
  ["zoom-out", "zoom-fit", "zoom-in"].forEach((id) => {
    document.getElementById(id).addEventListener("click", () => setTimeout(syncToolCanvas, 0));
  });

  const sizeObserver = new ResizeObserver(syncToolCanvas);
  sizeObserver.observe(maskCanvas);
  syncToolCanvas();
})();
