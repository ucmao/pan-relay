(function () {
  "use strict";

  const toastEl = document.getElementById("auroraToast");
  const backdrop = document.getElementById("auroraRequestBackdrop");
  const modal = document.getElementById("auroraRequestModal");
  const form = document.getElementById("auroraRequestForm");
  const nameInput = document.getElementById("auroraReqName");
  const contactInput = document.getElementById("auroraReqContact");
  const noteInput = document.getElementById("auroraReqNote");
  const submitButton = document.getElementById("auroraRequestSubmitBtn");

  function showToast(message, duration = 2500) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.add("is-visible");
    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(() => {
      toastEl.classList.remove("is-visible");
    }, duration);
  }

  function closeRequestModal() {
    if (backdrop) backdrop.hidden = true;
    if (modal) modal.hidden = true;
  }

  window.openAuroraRequestModal = function () {
    if (!modal || !backdrop) return;
    backdrop.hidden = false;
    modal.hidden = false;
    const searchInput = document.getElementById("resultsSearchInput") || document.getElementById("searchInput");
    const currentKeyword = searchInput ? searchInput.value.trim() : "";
    if (nameInput && !nameInput.value && currentKeyword) nameInput.value = currentKeyword;
    window.setTimeout(() => nameInput && nameInput.focus(), 50);
  };
  window.showAuroraToast = showToast;

  document.querySelectorAll("#openRequestModalBtn, #sideRequestBtn").forEach((button) => {
    button.addEventListener("click", window.openAuroraRequestModal);
  });
  document.getElementById("auroraRequestCloseBtn")?.addEventListener("click", closeRequestModal);
  document.getElementById("auroraRequestCancelBtn")?.addEventListener("click", closeRequestModal);
  backdrop?.addEventListener("click", closeRequestModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) closeRequestModal();
  });

  if (form && submitButton) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const resourceName = nameInput ? nameInput.value.trim() : "";
      const contact = contactInput ? contactInput.value.trim() : "";
      const note = noteInput ? noteInput.value.trim() : "";

      if (!resourceName) {
        showToast("请输入要寻找的资源名称");
        nameInput?.focus();
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = "提交中...";
      try {
        const response = await fetch("/api/request_resource", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ resource_name: resourceName, contact, note }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "提交失败，请稍候再试");

        showToast("求片需求已提交，感谢您的反馈！", 3000);
        closeRequestModal();
        if (nameInput) nameInput.value = "";
        if (contactInput) contactInput.value = "";
        if (noteInput) noteInput.value = "";
      } catch (error) {
        showToast(error.message || "网络请求异常，请稍候重试", 3000);
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = "提交需求";
      }
    });
  }
})();
