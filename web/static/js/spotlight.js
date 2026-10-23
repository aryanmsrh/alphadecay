// Linear / Neural Engine card proximity border spotlight
(() => {
  const init = () => {
    let targets = [];
    const updateTargets = () => {
      targets = Array.from(document.querySelectorAll(".card, .metric-card, .data-grid-cell, .duel-column, nav.floating-pill, .interactive-card, .table-responsive"));
    };
    updateTargets();

    const observer = new MutationObserver(() => {
      updateTargets();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    let raf = null;
    window.addEventListener("pointermove", (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        const x = e.clientX;
        const y = e.clientY;
        for (let i = 0; i < targets.length; i++) {
          const r = targets[i].getBoundingClientRect();
          targets[i].style.setProperty("--mouse-x", `${(x - r.left).toFixed(1)}px`);
          targets[i].style.setProperty("--mouse-y", `${(y - r.top).toFixed(1)}px`);
        }
        raf = null;
      });
    }, { passive: true });

    document.addEventListener("mouseleave", () => {
      for (let i = 0; i < targets.length; i++) {
        targets[i].style.setProperty("--mouse-x", "-999px");
        targets[i].style.setProperty("--mouse-y", "-999px");
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
