(function () {
  "use strict";

  const backdrop = document.getElementById("cinemaRequestBackdrop");
  const modal = document.getElementById("cinemaRequestModal");
  const form = document.getElementById("cinemaRequestForm");
  const nameInput = document.getElementById("cinemaRequestName");
  const contactInput = document.getElementById("cinemaRequestContact");
  const noteInput = document.getElementById("cinemaRequestNote");
  const submitButton = document.getElementById("cinemaRequestSubmit");
  const toast = document.getElementById("cinemaRequestToast");

  function showToast(message, duration = 2600) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(() => toast.classList.remove("is-visible"), duration);
  }
  window.showCinemaToast = showToast;

  function closeModal() {
    if (backdrop) backdrop.hidden = true;
    if (modal) modal.hidden = true;
  }

  window.openCinemaRequestModal = function () {
    if (!modal || !backdrop) return;
    backdrop.hidden = false;
    modal.hidden = false;
    const searchInput = document.getElementById("resultsSearchInput");
    const keyword = searchInput ? searchInput.value.trim() : "";
    if (nameInput && !nameInput.value && keyword) nameInput.value = keyword;
    window.setTimeout(() => nameInput && nameInput.focus(), 50);
  };

  document.getElementById("sideRequestBtn")?.addEventListener("click", window.openCinemaRequestModal);
  document.getElementById("cinemaRequestClose")?.addEventListener("click", closeModal);
  document.getElementById("cinemaRequestCancel")?.addEventListener("click", closeModal);
  backdrop?.addEventListener("click", closeModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) closeModal();
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resourceName = nameInput ? nameInput.value.trim() : "";
    if (!resourceName) {
      showToast("请填写资源名称");
      nameInput?.focus();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "提交中…";
    try {
      const response = await fetch("/api/request_resource", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resource_name: resourceName,
          contact: contactInput ? contactInput.value.trim() : "",
          note: noteInput ? noteInput.value.trim() : "",
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || "提交失败，请稍候再试");

      closeModal();
      form.reset();
      showToast("资源需求已提交，感谢反馈！", 3000);
    } catch (error) {
      showToast(error.message || "网络请求异常，请稍候重试", 3000);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "提交资源";
    }
  });
})();
