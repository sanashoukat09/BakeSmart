(() => {
  "use strict";

  const state = {
    classes: [],
    datasets: [],
    scenes: [],
    sceneIndex: 0,
    currentClass: 0,
    erasing: false,
    brushSize: 48,
    opacity: 0.55,
    zoom: 1,
    fitScale: 1,
    drawing: false,
    lastPoint: null,
    changedDuringStroke: false,
    history: [],
    redo: [],
    dirty: false,
  };

  const imageCanvas = document.getElementById("image-canvas");
  const maskCanvas = document.getElementById("mask-canvas");
  const imageContext = imageCanvas.getContext("2d", { alpha: false });
  const maskContext = maskCanvas.getContext("2d");
  const viewport = document.getElementById("canvas-viewport");
  const wrapper = document.getElementById("canvas-wrapper");
  const datasetSelect = document.getElementById("dataset-select");
  const classButtons = document.getElementById("class-buttons");
  const statusPill = document.getElementById("status-pill");
  const message = document.getElementById("message");
  const sceneName = document.getElementById("scene-name");
  const sceneSize = document.getElementById("scene-size");
  const sceneCounter = document.getElementById("scene-counter");
  const annotatorId = document.getElementById("annotator-id");

  async function request(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response;
  }

  function setMessage(text, kind = "") {
    message.textContent = text;
    message.className = `message ${kind}`.trim();
  }

  function setStatus(text, complete = false) {
    statusPill.textContent = text;
    statusPill.classList.toggle("complete", complete);
  }

  function currentScene() {
    return state.scenes[state.sceneIndex] || null;
  }

  function currentDataset() {
    return datasetSelect.value || "real_v2";
  }

  async function bootstrap() {
    try {
      const [classResponse, datasetResponse] = await Promise.all([
        request("/api/label-classes"),
        request("/api/datasets"),
      ]);
      const classPayload = await classResponse.json();
      const datasetPayload = await datasetResponse.json();
      state.classes = classPayload.classes;
      state.datasets = datasetPayload.datasets;
      renderClasses();
      renderDatasets();
      await loadScenes();
    } catch (error) {
      setMessage(error.message, "error");
      setStatus("Could not start");
    }
  }

  function renderClasses() {
    classButtons.innerHTML = "";
    state.classes.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "class-button";
      button.dataset.classId = String(item.id);
      button.innerHTML = `<span class="swatch" style="background:${item.color}"></span><span>${item.id}. ${item.name}</span>`;
      button.addEventListener("click", () => {
        state.currentClass = item.id;
        state.erasing = false;
        updateToolState();
      });
      classButtons.appendChild(button);
    });
    updateToolState();
  }

  function renderDatasets() {
    datasetSelect.innerHTML = "";
    state.datasets.forEach((dataset) => {
      const option = document.createElement("option");
      option.value = dataset.key;
      option.textContent = `${dataset.label} (${dataset.image_count})`;
      datasetSelect.appendChild(option);
    });
    if (state.datasets.some((dataset) => dataset.key === "real_v2")) {
      datasetSelect.value = "real_v2";
    }
  }

  async function loadScenes() {
    setMessage("Loading scenes…");
    const response = await request(`/api/scenes?dataset=${encodeURIComponent(currentDataset())}`);
    const payload = await response.json();
    state.scenes = payload.scenes;
    state.sceneIndex = 0;
    if (!state.scenes.length) {
      clearCanvases();
      setStatus("No local images");
      setMessage("No images were found in this dataset's local raw/images folder.");
      updateSceneMeta();
      return;
    }
    await loadScene(0);
  }

  async function loadScene(index) {
    if (!state.scenes.length) return;
    state.sceneIndex = Math.max(0, Math.min(index, state.scenes.length - 1));
    const scene = currentScene();
    setStatus("Loading…");
    setMessage(`Loading ${scene.scene_id}…`);
    const imageUrl = `/api/scenes/${encodeURIComponent(currentDataset())}/${encodeURIComponent(scene.scene_id)}/image`;
    const maskUrl = `/api/scenes/${encodeURIComponent(currentDataset())}/${encodeURIComponent(scene.scene_id)}/mask-overlay?t=${Date.now()}`;
    try {
      const [image, mask] = await Promise.all([loadImage(imageUrl), loadImage(maskUrl)]);
      imageCanvas.width = image.naturalWidth;
      imageCanvas.height = image.naturalHeight;
      maskCanvas.width = image.naturalWidth;
      maskCanvas.height = image.naturalHeight;
      imageContext.clearRect(0, 0, imageCanvas.width, imageCanvas.height);
      imageContext.drawImage(image, 0, 0);
      maskContext.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
      maskContext.drawImage(mask, 0, 0);
      maskCanvas.style.opacity = String(state.opacity);
      state.zoom = 1;
      state.history = [maskCanvas.toDataURL("image/png")];
      state.redo = [];
      state.dirty = false;
      if (scene.annotator_id && !annotatorId.value.trim()) {
        annotatorId.value = scene.annotator_id;
      }
      updateFitScale();
      updateSceneMeta();
      setStatus(scene.status, scene.status === "annotation_complete_pending_review");
      setMessage("Scene ready. Paint directly on the photo overlay.");
    } catch (error) {
      setStatus("Load failed");
      setMessage(error.message, "error");
    }
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`Could not load image: ${url}`));
      image.src = url;
    });
  }

  function clearCanvases() {
    imageCanvas.width = 1;
    imageCanvas.height = 1;
    maskCanvas.width = 1;
    maskCanvas.height = 1;
    wrapper.style.width = "1px";
    wrapper.style.height = "1px";
  }

  function updateSceneMeta() {
    const scene = currentScene();
    if (!scene) {
      sceneName.textContent = "No scene";
      sceneSize.textContent = "—";
      sceneCounter.textContent = "0 / 0";
      return;
    }
    sceneName.textContent = scene.scene_id;
    sceneSize.textContent = `${scene.pixel_width} × ${scene.pixel_height}px · ${scene.status}`;
    sceneCounter.textContent = `${state.sceneIndex + 1} / ${state.scenes.length}`;
    document.getElementById("previous-scene").disabled = state.sceneIndex === 0;
    document.getElementById("next-scene").disabled = state.sceneIndex >= state.scenes.length - 1;
  }

  function updateToolState() {
    document.querySelectorAll(".class-button").forEach((button) => {
      button.classList.toggle(
        "active",
        !state.erasing && Number(button.dataset.classId) === state.currentClass,
      );
    });
    document.getElementById("eraser-button").classList.toggle("active", state.erasing);
  }

  function updateFitScale() {
    if (!imageCanvas.width || imageCanvas.width === 1) return;
    const availableWidth = Math.max(160, viewport.clientWidth - 34);
    const availableHeight = Math.max(160, viewport.clientHeight - 34);
    state.fitScale = Math.min(
      availableWidth / imageCanvas.width,
      availableHeight / imageCanvas.height,
      1,
    );
    applyCanvasScale();
  }

  function applyCanvasScale() {
    const scale = state.fitScale * state.zoom;
    const width = Math.max(1, Math.round(imageCanvas.width * scale));
    const height = Math.max(1, Math.round(imageCanvas.height * scale));
    wrapper.style.width = `${width}px`;
    wrapper.style.height = `${height}px`;
    imageCanvas.style.width = `${width}px`;
    imageCanvas.style.height = `${height}px`;
    maskCanvas.style.width = `${width}px`;
    maskCanvas.style.height = `${height}px`;
  }

  function pointerToImage(event) {
    const bounds = maskCanvas.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) * maskCanvas.width / bounds.width,
      y: (event.clientY - bounds.top) * maskCanvas.height / bounds.height,
    };
  }

  function drawPoint(point) {
    maskContext.save();
    if (state.erasing) {
      maskContext.globalCompositeOperation = "destination-out";
      maskContext.fillStyle = "rgba(0,0,0,1)";
    } else {
      maskContext.globalCompositeOperation = "source-over";
      const selected = state.classes.find((item) => item.id === state.currentClass);
      maskContext.fillStyle = selected?.color || "#E57373";
    }
    maskContext.beginPath();
    maskContext.arc(point.x, point.y, state.brushSize / 2, 0, Math.PI * 2);
    maskContext.fill();
    maskContext.restore();
  }

  function drawLine(from, to) {
    maskContext.save();
    if (state.erasing) {
      maskContext.globalCompositeOperation = "destination-out";
      maskContext.strokeStyle = "rgba(0,0,0,1)";
    } else {
      maskContext.globalCompositeOperation = "source-over";
      const selected = state.classes.find((item) => item.id === state.currentClass);
      maskContext.strokeStyle = selected?.color || "#E57373";
    }
    maskContext.lineWidth = state.brushSize;
    maskContext.lineCap = "round";
    maskContext.lineJoin = "round";
    maskContext.beginPath();
    maskContext.moveTo(from.x, from.y);
    maskContext.lineTo(to.x, to.y);
    maskContext.stroke();
    maskContext.restore();
  }

  function pushHistory() {
    const snapshot = maskCanvas.toDataURL("image/png");
    if (state.history[state.history.length - 1] !== snapshot) {
      state.history.push(snapshot);
      if (state.history.length > 12) state.history.shift();
      state.redo = [];
      state.dirty = true;
    }
  }

  async function restoreSnapshot(snapshot) {
    const image = await loadImage(snapshot);
    maskContext.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    maskContext.drawImage(image, 0, 0);
  }

  async function undo() {
    if (state.history.length <= 1) return;
    const current = state.history.pop();
    state.redo.push(current);
    await restoreSnapshot(state.history[state.history.length - 1]);
    state.dirty = true;
  }

  async function redo() {
    const snapshot = state.redo.pop();
    if (!snapshot) return;
    state.history.push(snapshot);
    await restoreSnapshot(snapshot);
    state.dirty = true;
  }

  function fillCanvas() {
    const selected = state.classes.find((item) => item.id === state.currentClass);
    if (!selected) return;
    maskContext.save();
    maskContext.globalCompositeOperation = "source-over";
    maskContext.fillStyle = selected.color;
    maskContext.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
    maskContext.restore();
    state.erasing = false;
    updateToolState();
    pushHistory();
  }

  function clearMask() {
    maskContext.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    pushHistory();
  }

  async function submit(action) {
    const scene = currentScene();
    if (!scene) return;
    const body = {
      mask_png_base64: maskCanvas.toDataURL("image/png"),
      annotator_id: annotatorId.value.trim() || null,
    };
    if (action === "complete" && !body.annotator_id) {
      setMessage("Enter an annotator ID before marking this mask complete.", "error");
      return;
    }
    const label = {
      draft: "Saving draft…",
      validate: "Validating mask…",
      complete: "Completing annotation…",
    }[action];
    setMessage(label);
    try {
      const response = await request(
        `/api/scenes/${encodeURIComponent(currentDataset())}/${encodeURIComponent(scene.scene_id)}/${action}`,
        { method: "POST", body: JSON.stringify(body) },
      );
      const result = await response.json();
      const coverage = Math.round((result.coverage_fraction || 0) * 10000) / 100;
      if (action === "validate") {
        setMessage(
          result.complete
            ? "Validation passed: all pixels are assigned to class 0-6."
            : `Validation incomplete: ${result.unlabelled_pixels.toLocaleString()} pixel(s) remain unlabelled (${coverage}% covered).`,
          result.complete ? "success" : "error",
        );
        return;
      }
      scene.status = result.status;
      scene.has_mask = true;
      scene.annotator_id = result.record?.annotator_id || scene.annotator_id;
      updateSceneMeta();
      state.dirty = false;
      setStatus(result.status, result.status === "annotation_complete_pending_review");
      setMessage(
        action === "complete"
          ? "Annotation completed and locked as pending independent review. It is still not training data."
          : `Draft saved locally (${coverage}% covered).`,
        "success",
      );
    } catch (error) {
      setMessage(error.message, "error");
    }
  }

  maskCanvas.addEventListener("pointerdown", (event) => {
    if (!currentScene()) return;
    event.preventDefault();
    maskCanvas.setPointerCapture(event.pointerId);
    state.drawing = true;
    state.changedDuringStroke = true;
    const point = pointerToImage(event);
    state.lastPoint = point;
    drawPoint(point);
  });

  maskCanvas.addEventListener("pointermove", (event) => {
    if (!state.drawing || !state.lastPoint) return;
    event.preventDefault();
    const point = pointerToImage(event);
    drawLine(state.lastPoint, point);
    state.lastPoint = point;
  });

  function finishStroke(event) {
    if (!state.drawing) return;
    state.drawing = false;
    state.lastPoint = null;
    try { maskCanvas.releasePointerCapture(event.pointerId); } catch (_) {}
    if (state.changedDuringStroke) pushHistory();
    state.changedDuringStroke = false;
  }

  maskCanvas.addEventListener("pointerup", finishStroke);
  maskCanvas.addEventListener("pointercancel", finishStroke);

  datasetSelect.addEventListener("change", loadScenes);
  document.getElementById("previous-scene").addEventListener("click", () => loadScene(state.sceneIndex - 1));
  document.getElementById("next-scene").addEventListener("click", () => loadScene(state.sceneIndex + 1));
  document.getElementById("eraser-button").addEventListener("click", () => {
    state.erasing = !state.erasing;
    updateToolState();
  });
  document.getElementById("brush-size").addEventListener("input", (event) => {
    state.brushSize = Number(event.target.value);
    document.getElementById("brush-value").textContent = String(state.brushSize);
  });
  document.getElementById("opacity").addEventListener("input", (event) => {
    state.opacity = Number(event.target.value) / 100;
    maskCanvas.style.opacity = String(state.opacity);
    document.getElementById("opacity-value").textContent = event.target.value;
  });
  document.getElementById("undo-button").addEventListener("click", undo);
  document.getElementById("redo-button").addEventListener("click", redo);
  document.getElementById("fill-button").addEventListener("click", fillCanvas);
  document.getElementById("clear-button").addEventListener("click", clearMask);
  document.getElementById("zoom-out").addEventListener("click", () => {
    state.zoom = Math.max(0.5, state.zoom / 1.25);
    applyCanvasScale();
  });
  document.getElementById("zoom-in").addEventListener("click", () => {
    state.zoom = Math.min(6, state.zoom * 1.25);
    applyCanvasScale();
  });
  document.getElementById("zoom-fit").addEventListener("click", () => {
    state.zoom = 1;
    updateFitScale();
  });
  document.getElementById("save-draft").addEventListener("click", () => submit("draft"));
  document.getElementById("validate-mask").addEventListener("click", () => submit("validate"));
  document.getElementById("complete-mask").addEventListener("click", () => submit("complete"));
  window.addEventListener("resize", updateFitScale);
  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  bootstrap();
})();
