(() => {
  "use strict";

  const maskCanvas = document.getElementById("mask-canvas");
  const walkwayCanvas = document.getElementById("walkway-canvas");
  const button = document.getElementById("toggle-walkway-overlay");
  const datasetSelect = document.getElementById("dataset-select");
  const sceneName = document.getElementById("scene-name");
  const message = document.getElementById("message");
  if (!maskCanvas || !walkwayCanvas || !button || !datasetSelect || !sceneName) return;

  const context = walkwayCanvas.getContext("2d");
  let visible = false;
  let loadToken = 0;

  function syncGeometry() {
    walkwayCanvas.width = maskCanvas.width;
    walkwayCanvas.height = maskCanvas.height;
    walkwayCanvas.style.width = maskCanvas.style.width || `${maskCanvas.width}px`;
    walkwayCanvas.style.height = maskCanvas.style.height || `${maskCanvas.height}px`;
  }

  function currentSceneId() {
    const value = sceneName.textContent.trim();
    return value === "No scene" ? "" : value;
  }

  async function reload() {
    syncGeometry();
    context.clearRect(0, 0, walkwayCanvas.width, walkwayCanvas.height);
    const sceneId = currentSceneId();
    if (!sceneId) return;
    const token = ++loadToken;
    const url = `/api/scenes/${encodeURIComponent(datasetSelect.value || "real_v2")}/${encodeURIComponent(sceneId)}/walkway-overlay?t=${Date.now()}`;
    const image = new Image();
    image.onload = () => {
      if (token !== loadToken) return;
      syncGeometry();
      context.clearRect(0, 0, walkwayCanvas.width, walkwayCanvas.height);
      context.drawImage(image, 0, 0, walkwayCanvas.width, walkwayCanvas.height);
    };
    image.onerror = () => {
      if (token !== loadToken) return;
      context.clearRect(0, 0, walkwayCanvas.width, walkwayCanvas.height);
    };
    image.src = url;
  }

  function setVisible(next) {
    visible = Boolean(next);
    walkwayCanvas.style.display = visible ? "block" : "none";
    button.classList.toggle("active", visible);
    button.textContent = visible ? "Hide Walkway overlay" : "Show Walkway overlay";
    if (visible) reload();
  }

  button.addEventListener("click", () => setVisible(!visible));
  datasetSelect.addEventListener("change", () => {
    if (visible) setTimeout(reload, 50);
  });

  const sceneObserver = new MutationObserver(() => {
    if (visible) setTimeout(reload, 30);
  });
  sceneObserver.observe(sceneName, { childList: true, characterData: true, subtree: true });

  const maskObserver = new MutationObserver(() => syncGeometry());
  maskObserver.observe(maskCanvas, {
    attributes: true,
    attributeFilter: ["width", "height", "style"],
  });

  if (message) {
    const copyObserver = new MutationObserver(() => {
      if (message.textContent.includes("class 0-6")) {
        message.textContent = message.textContent.replace("class 0-6", "classes 0-5");
      }
    });
    copyObserver.observe(message, { childList: true, characterData: true, subtree: true });
  }

  document.getElementById("save-draft")?.addEventListener("click", () => {
    if (visible) setTimeout(reload, 350);
  });
  document.getElementById("complete-mask")?.addEventListener("click", () => {
    if (visible) setTimeout(reload, 350);
  });

  syncGeometry();
  setVisible(false);
})();
