(() => {
  "use strict";

  const state = {
    scenes: [],
    index: 0,
    dataset: "real_v2",
    summary: null,
  };

  const sceneName = document.getElementById("scene-name");
  const sceneMeta = document.getElementById("scene-meta");
  const sourceImage = document.getElementById("source-image");
  const maskImage = document.getElementById("mask-image");
  const reviewerId = document.getElementById("reviewer-id");
  const reviewNotes = document.getElementById("review-notes");
  const annotatorId = document.getElementById("annotator-id");
  const reviewStatus = document.getElementById("review-status");
  const summary = document.getElementById("summary");
  const message = document.getElementById("message");
  const previous = document.getElementById("previous");
  const next = document.getElementById("next");
  const approve = document.getElementById("approve");
  const correct = document.getElementById("correct");
  const reject = document.getElementById("reject");

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

  function currentScene() {
    return state.scenes[state.index] || null;
  }

  function renderSummary() {
    const value = state.summary || { total: 0, pending: 0, approved: 0, needs_correction: 0, rejected: 0 };
    summary.textContent = `Approved ${value.approved} · Correction ${value.needs_correction} · Rejected ${value.rejected} · Pending ${value.pending}`;
  }

  function renderScene() {
    const scene = currentScene();
    if (!scene) {
      sceneName.textContent = "No scene";
      sceneMeta.textContent = "—";
      sourceImage.removeAttribute("src");
      maskImage.removeAttribute("src");
      return;
    }

    sceneName.textContent = scene.scene_id;
    sceneMeta.textContent = `${state.index + 1} / ${state.scenes.length} · ${scene.pixel_width} × ${scene.pixel_height}px`;
    annotatorId.textContent = scene.annotator_id || "missing";
    reviewStatus.textContent = scene.review_status || "pending_independent_review";
    reviewNotes.value = scene.review_notes || "";
    previous.disabled = state.index === 0;
    next.disabled = state.index >= state.scenes.length - 1;

    const base = `/api/scenes/${encodeURIComponent(state.dataset)}/${encodeURIComponent(scene.scene_id)}`;
    sourceImage.src = `${base}/image?t=${Date.now()}`;
    maskImage.src = `${base}/mask-overlay?t=${Date.now()}`;

    const disabled = !scene.reviewable;
    approve.disabled = disabled;
    correct.disabled = disabled;
    reject.disabled = disabled;
    if (disabled) {
      setMessage("This scene is not a completed annotation ready for review.", "error");
    } else {
      setMessage("Inspect the original photo and completed mask, then choose a review decision.");
    }
  }

  async function loadScenes(preferredSceneId = null) {
    const response = await request(`/api/scenes?dataset=${encodeURIComponent(state.dataset)}`);
    const payload = await response.json();
    state.scenes = payload.scenes;
    state.summary = payload.summary;
    if (preferredSceneId) {
      const found = state.scenes.findIndex((scene) => scene.scene_id === preferredSceneId);
      state.index = found >= 0 ? found : Math.min(state.index, Math.max(state.scenes.length - 1, 0));
    } else {
      const firstPending = state.scenes.findIndex((scene) => !["approved", "needs_correction", "rejected"].includes(scene.review_status));
      state.index = firstPending >= 0 ? firstPending : 0;
    }
    renderSummary();
    renderScene();
  }

  async function submit(decision) {
    const scene = currentScene();
    if (!scene) return;
    const reviewer = reviewerId.value.trim();
    const notes = reviewNotes.value.trim();
    if (!reviewer) {
      setMessage("Enter the second reviewer's ID first.", "error");
      reviewerId.focus();
      return;
    }
    if ((decision === "needs_correction" || decision === "rejected") && !notes) {
      setMessage("Add a short note explaining the correction or rejection.", "error");
      reviewNotes.focus();
      return;
    }

    setMessage("Saving review…");
    try {
      const response = await request(
        `/api/scenes/${encodeURIComponent(state.dataset)}/${encodeURIComponent(scene.scene_id)}/review`,
        {
          method: "POST",
          body: JSON.stringify({ reviewer_id: reviewer, decision, notes }),
        },
      );
      const result = await response.json();
      state.summary = result.summary;
      const currentId = scene.scene_id;
      await loadScenes(currentId);
      const refreshed = currentScene();
      if (refreshed) {
        refreshed.review_status = result.review_status;
        refreshed.reviewer_id = result.reviewer_id;
        refreshed.review_notes = result.review_notes;
      }
      renderSummary();
      renderScene();
      setMessage(`Saved: ${result.review_status.replaceAll("_", " ")}.`, "success");

      if (state.index < state.scenes.length - 1) {
        setTimeout(() => {
          state.index += 1;
          renderScene();
        }, 350);
      }
    } catch (error) {
      setMessage(error.message, "error");
    }
  }

  previous.addEventListener("click", () => {
    if (state.index > 0) {
      state.index -= 1;
      renderScene();
    }
  });
  next.addEventListener("click", () => {
    if (state.index < state.scenes.length - 1) {
      state.index += 1;
      renderScene();
    }
  });
  approve.addEventListener("click", () => submit("approved"));
  correct.addEventListener("click", () => submit("needs_correction"));
  reject.addEventListener("click", () => submit("rejected"));

  loadScenes().catch((error) => setMessage(error.message, "error"));
})();
