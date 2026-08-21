(() => {
  "use strict";

  const classButtons = document.getElementById("class-buttons");
  if (!classButtons) return;

  function markWalkwayDerived() {
    const button = classButtons.querySelector('[data-class-id="6"]');
    if (!button) return false;
    button.disabled = true;
    button.classList.add("derived-class");
    button.title = "Walkway candidate is generated automatically from Floor. Do not paint it manually.";
    const text = button.querySelector("span:last-child");
    if (text && !text.textContent.includes("auto")) {
      text.textContent = `${text.textContent} · auto`;
    }
    return true;
  }

  if (!markWalkwayDerived()) {
    const observer = new MutationObserver(() => {
      if (markWalkwayDerived()) observer.disconnect();
    });
    observer.observe(classButtons, { childList: true, subtree: true });
  }
})();
