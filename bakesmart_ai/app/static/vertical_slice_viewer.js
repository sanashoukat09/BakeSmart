(() => {
  "use strict";

  const canvas = document.getElementById("scene-canvas");
  const statusCard = document.getElementById("loading-card");
  const statusText = document.getElementById("status-text");
  const resetButton = document.getElementById("reset-view");
  const selectionCard = document.getElementById("selection-card");
  const selectionName = document.getElementById("selection-name");
  const selectionMeta = document.getElementById("selection-meta");
  const manifestLink = document.getElementById("manifest-link");
  const title = document.getElementById("scene-title");
  const subtitle = document.getElementById("scene-subtitle");
  const celebration = window.location.pathname.split("/").filter(Boolean).pop();
  const allowed = new Set(["birthday", "wedding", "south_asian_mehndi"]);

  if (!allowed.has(celebration)) {
    showError("Unknown vertical-slice celebration.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const usable = numberParam(
    params.get("usable"),
    celebration === "south_asian_mehndi" ? 6.5 : 5.5,
  );
  const target = numberParam(
    params.get("target"),
    celebration === "south_asian_mehndi" ? 6.0 : 4.8,
  );
  const lighting = params.get("lighting") !== "false";
  const apiUrl = new URL("/api/v1/assets/3d/vertical-slice/scene", window.location.origin);
  apiUrl.searchParams.set("celebration", celebration);
  apiUrl.searchParams.set("usable_focal_width_m", usable.toFixed(3));
  apiUrl.searchParams.set("target_visual_width_m", target.toFixed(3));
  apiUrl.searchParams.set("include_lighting", lighting ? "true" : "false");
  manifestLink.href = apiUrl.pathname + apiUrl.search;

  const displayName = celebration === "south_asian_mehndi"
    ? "South Asian Mehndi"
    : celebration.charAt(0).toUpperCase() + celebration.slice(1);
  title.textContent = `${displayName} Modular 3D Review`;
  subtitle.textContent = `True-size review modules in a ${usable.toFixed(2)} m usable focal span`;

  let renderer;
  try {
    renderer = new window.BakeSmartProfessionalRenderer(canvas, {
      onSelection: (module) => {
        if (!module) {
          selectionCard.hidden = true;
          return;
        }
        selectionName.textContent = module.label;
        selectionMeta.textContent = "Independent GLB module • scale 1.0";
        selectionCard.hidden = false;
      },
    });
    renderer.installControls();
  } catch (error) {
    showError(`The local Stage-7 renderer could not start: ${error.message}`);
    return;
  }

  fetch(apiUrl, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`scene manifest returned ${response.status}`);
      }
      return response.json();
    })
    .then(async (manifest) => {
      if (!manifest.modules.length) {
        throw new Error(
          manifest.notes?.[0] || "The true-size primary structure does not fit this focal span.",
        );
      }
      for (const module of manifest.modules) {
        await renderer.loadModule({
          url: module.glb_url,
          id: `${module.asset_id}-${module.instance_index}`,
          label: `${humanize(module.catalog_id)} #${module.instance_index}`,
          translation: module.translation_m,
          uniformScale: module.uniform_scale,
        });
      }
      renderer.resetView();
      const stats = renderer.stats();
      statusCard.classList.add("ready");
      statusText.textContent =
        `${displayName} review ready • ${stats.moduleCount} modules • ` +
        `${manifest.achieved_visual_width_m.toFixed(2)} m visual span • ` +
        `${stats.triangleCount.toLocaleString()} triangles`;
    })
    .catch((error) => showError(error.message));

  resetButton.addEventListener("click", () => renderer.resetView());

  function numberParam(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }

  function humanize(value) {
    return value
      .split("-")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function showError(message) {
    statusCard.classList.add("error");
    statusText.textContent = message;
  }
})();
