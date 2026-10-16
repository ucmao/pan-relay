/**
 * themes/aurora/static/js/theme_aurora.js
 * 专为 aurora (极光双模流式主题) 打造的流式搜索与转存交互引擎 (v1.0.1 修正版)
 */

(function () {
  "use strict";

  // 全局变量与 DOM 引用
  let allItems = [];
  let currentDriveFilter = "";
  let sseSource = null;
  let searchGeneration = 0;
  const itemsPerPage = 10;
  let currentPage = 1;

  const resultsList = document.getElementById("resultsList");
  const serpPagination = document.getElementById("serpPagination");
  const resultSummaryText = document.getElementById("resultSummaryText");
  const countStatsValid = document.getElementById("countStatsValid");
  const countStatsFailed = document.getElementById("countStatsFailed");
  const searchInput = document.getElementById("resultsSearchInput");
  const searchForm = document.getElementById("resultsSearchForm");
  const sourceChips = document.querySelectorAll(".source-chip");
  const themeToggle = document.getElementById("themeToggle");
  const toastEl = document.getElementById("auroraToast");

  // 转存弹窗 DOM
  const modalBackdrop = document.getElementById("auroraModalBackdrop");
  const modalShell = document.getElementById("auroraModalShell");
  const modalTitle = document.getElementById("auroraModalTitle");
  const modalLink = document.getElementById("auroraModalLink");
  const modalQrImg = document.getElementById("auroraModalQrImg");
  const modalQrContainer = document.getElementById("auroraModalQrContainer");
  const modalLoading = document.getElementById("auroraModalLoading");
  const modalContent = document.getElementById("auroraModalContent");
  const modalCopyBtn = document.getElementById("auroraModalCopyBtn");
  const modalOpenBtn = document.getElementById("auroraModalOpenBtn");
  let currentFinalUrl = "";

  // 网盘图标映射表
  const DRIVE_ICONS = {
    quark: "/themes/aurora/assets/kuake-dark.svg",
    baidu: "/themes/aurora/assets/icon_baiduwangpan-dark.svg",
    ali: "/themes/aurora/assets/ali-dark.svg",
    xunlei: "/themes/aurora/assets/xunlei1-dark.svg",
    uc: "/themes/aurora/assets/changyonglogo31-dark.svg",
    guangya: "/themes/aurora/assets/guangya-dark.svg",
    wukong: "/themes/aurora/assets/wukong-dark.svg",
    yidong: "/themes/aurora/assets/yidong-dark.svg",
    seed: "/themes/aurora/assets/zhongzi-dark.svg",
    all: "/themes/aurora/assets/all-source-dark.svg",
  };

  // 1. 夜间模式初始化与切换
  function initTheme() {
    const saved = localStorage.getItem("theme_mode") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    if (themeToggle) {
      themeToggle.setAttribute("aria-pressed", String(saved === "dark"));
      themeToggle.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        const next = cur === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("theme_mode", next);
        themeToggle.setAttribute("aria-pressed", String(next === "dark"));
      });
    }
  }

  // 2. 页面浮动轻量 Toast 提示
  function showToast(msg, duration = 2000) {
    if (window.showAuroraToast) {
      window.showAuroraToast(msg, duration);
      return;
    }
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    setTimeout(() => {
      toastEl.classList.remove("is-visible");
    }, duration);
  }

  // 3. 数据统一归一化 (兼容各种数据格式)
  function normalizeItem(raw) {
    if (!raw) return null;
    if (Array.isArray(raw)) {
      const source = raw[0] || "other";
      return {
        source,
        title: raw[1] || "",
        share_link: raw[2] || "",
        cloud_name: raw[3] || "其他",
        drive_type: detectDriveType(raw[3], raw[2]),
        datetime: raw[4] || "",
        description: raw[5] || "",
        cover_url: raw[6] || "",
        source_type: raw[7] || "",
        source_id: raw[8] || "",
        source_name: raw[9] || "",
        metadata: raw[10] && typeof raw[10] === "object" ? raw[10] : {},
        password: "",
        status: "",
      };
    }
    if (typeof raw === "object") {
      const dt = raw.drive_type || detectDriveType(raw.cloud_name, raw.share_link || raw.url);
      return {
        source: raw.source || "other",
        title: raw.title || raw.name || "",
        share_link: raw.share_link || raw.url || "",
        cloud_name: raw.cloud_name || "其他",
        drive_type: dt,
        datetime: raw.datetime || raw.created_at || raw.time || "",
        description: raw.description || raw.desc || raw.content || "",
        cover_url: raw.cover_url || raw.cover || raw.image || raw.poster || raw.pic || "",
        source_type: raw.source_type || raw.sourceType || "",
        source_display: raw.source_display || raw.sourceDisplay || "",
        source_id: raw.source_id || raw.sourceId || "",
        source_name: raw.source_name || raw.sourceName || "",
        metadata: raw.metadata && typeof raw.metadata === "object" ? raw.metadata : {},
        password: raw.password || raw.pwd || "",
        status: raw.link_status || raw.status || (raw.is_valid === true ? "valid" : raw.is_valid === false ? "invalid" : ""),
      };
    }
    return null;
  }

  function detectDriveType(cloudName, link) {
    const c = (cloudName || "").toLowerCase();
    const l = (link || "").toLowerCase();
    if (c.includes("夸克") || l.includes("quark.cn")) return "quark";
    if (c.includes("百度") || l.includes("baidu.com")) return "baidu";
    if (c.includes("阿里") || l.includes("alipan.com") || l.includes("aliyundrive.com")) return "ali";
    if (c.includes("迅雷") || l.includes("xunlei.com")) return "xunlei";
    if (c.includes("uc") || l.includes("uc.cn")) return "uc";
    if (c.includes("光鸭") || l.includes("guangyapan")) return "guangya";
    if (c.includes("悟空") || l.includes("wkbrowser")) return "wukong";
    if (c.includes("移动") || c.includes("彩云") || l.includes("139.com") || l.includes("10086.cn")) return "yidong";
    if (c.includes("磁力") || l.startsWith("magnet:") || l.startsWith("ed2k:")) return "seed";
    return "other";
  }

  // 4. Tab 切换与过滤
  function bindTabs() {
    sourceChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        sourceChips.forEach((c) => c.classList.remove("is-active"));
        chip.classList.add("is-active");
        currentDriveFilter = chip.dataset.drive || "";
        currentPage = 1;
        renderResults();
      });
    });
  }

  // 5. 分页组件渲染 (10条/页)
  function renderPagination(totalCount) {
    if (!serpPagination) return;
    const totalPages = Math.ceil(totalCount / itemsPerPage) || 1;
    if (totalCount === 0 || totalPages <= 1) {
      serpPagination.classList.add("is-hidden");
      serpPagination.innerHTML = "";
      return;
    }

    serpPagination.classList.remove("is-hidden");

    let pages = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      if (currentPage <= 4) {
        pages = [1, 2, 3, 4, 5, "...", totalPages];
      } else if (currentPage >= totalPages - 3) {
        pages = [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
      } else {
        pages = [1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages];
      }
    }

    let html = `
      <button type="button" class="pager-nav" data-page="${currentPage - 1}" ${currentPage <= 1 ? "disabled" : ""}>
        上一页
      </button>
    `;

    pages.forEach((p) => {
      if (p === "...") {
        html += `<span>...</span>`;
      } else {
        const isActive = p === currentPage ? "is-active" : "";
        html += `
          <button type="button" class="pager-page ${isActive}" data-page="${p}">
            ${p}
          </button>
        `;
      }
    });

    html += `
      <button type="button" class="pager-nav" data-page="${currentPage + 1}" ${currentPage >= totalPages ? "disabled" : ""}>
        下一页
      </button>
    `;

    serpPagination.innerHTML = html;

    serpPagination.querySelectorAll("button[data-page]:not(:disabled)").forEach((btn) => {
      btn.addEventListener("click", () => {
        const page = parseInt(btn.dataset.page, 10);
        if (page && page !== currentPage && page >= 1 && page <= totalPages) {
          currentPage = page;
          renderResults();
          const target = resultsList.closest(".serp-layout") || resultsList;
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  // 6. 渲染搜索卡片 (严格采用原版 .serp-item 样式体系 + 10条分页与图文混排)
  function renderResults() {
    if (!resultsList) return;

    let filtered = allItems;
    if (currentDriveFilter) {
      if (currentDriveFilter === "seed" || ["磁力链接", "迅雷链接", "电驴链接"].includes(currentDriveFilter)) {
        filtered = allItems.filter(
          (it) => it.drive_type === "seed" || it.share_link.startsWith("magnet:") || it.share_link.startsWith("ed2k:")
        );
      } else {
        filtered = allItems.filter((it) => it.cloud_name === currentDriveFilter || it.drive_type === currentDriveFilter);
      }
    }

    if (filtered.length === 0) {
      renderPagination(0);
      const currentKw = searchInput ? searchInput.value.trim() : "";
      if (allItems.length === 0) {
        const canRequest = window.ENABLE_RESOURCE_REQUEST !== false;
        resultsList.innerHTML = `
          <div class="empty-state" style="padding: 48px 20px; text-align: center; color: var(--text-muted, #94a3b8);">
            <div style="font-size: 36px; margin-bottom: 12px;">🔍</div>
            <p style="font-size: 15px; font-weight: 500; color: var(--text-main, #334155); margin-bottom: 8px;">未找到与「${escapeHtml(currentKw)}」相关的公开网盘资源</p>
            ${canRequest ? `
            <p style="font-size: 13px; color: var(--muted, #64748b); margin-bottom: 18px;">您可以更换搜索词，或者直接向站长提交求片需求。</p>
            <button type="button" class="serp-btn serp-btn-get" id="emptyStateRequestBtn" style="padding: 8px 20px; font-size: 13.5px; margin: 0 auto; display: inline-flex; cursor: pointer;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 5px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
              提交求片需求
            </button>` : `
            <p style="font-size: 13px; color: var(--muted, #64748b); margin-bottom: 0;">您可以更换搜索词尝试重新搜索。</p>`}
          </div>
        `;
        const emptyBtn = document.getElementById("emptyStateRequestBtn");
        if (emptyBtn && window.openAuroraRequestModal) {
          emptyBtn.addEventListener("click", window.openAuroraRequestModal);
        }
      } else {
        resultsList.innerHTML = `
          <div class="empty-state" style="padding: 40px 0; text-align: center; color: var(--text-muted, #94a3b8);">
            <p>当前网盘分类下暂无结果，请点击上方「全部」或切换其它网盘 Tab 查看</p>
          </div>
        `;
      }
      return;
    }

    const totalPages = Math.ceil(filtered.length / itemsPerPage) || 1;
    if (currentPage > totalPages) {
      currentPage = totalPages;
    }
    if (currentPage < 1) {
      currentPage = 1;
    }

    const startIndex = (currentPage - 1) * itemsPerPage;
    const currentBatch = filtered.slice(startIndex, startIndex + itemsPerPage);

    let html = "";
    currentBatch.forEach((item, idx) => {
      const iconUrl = DRIVE_ICONS[item.drive_type] || DRIVE_ICONS.all;
      const pwdBadge = item.password
        ? `<span class="res-badge-pwd" title="提取码: ${escapeHtml(item.password)}">提取码: ${escapeHtml(item.password)}</span>`
        : "";
      const sourceBadge = item.source === "hot"
        ? `<span class="res-badge-hot">站长自建</span>`
        : "";
      const description = item.description && item.description.trim() && item.description.trim() !== item.title.trim()
        ? item.description.trim()
        : "本站不产生、不存储任何资源内容，亦未参与录制或上传。若相关结果侵犯您的合法权益，请联系我们，我们将在核实后尽快处理。";
      const rawTimestamp = item.datetime && String(item.datetime).trim() ? String(item.datetime).trim() : "";
      const timestamp = rawTimestamp ? formatTimestamp(rawTimestamp) : "未知时间";
      const freshnessLabel = getFreshnessLabel(rawTimestamp);
      const freshnessBadge = freshnessLabel
        ? `<span class="serp-time-badge">${freshnessLabel}</span>`
        : "";
      const sourceName = getSourceDisplayName(item.source, item.source_type, item.source_display);
      const status = getStatusDisplay(item.status);
      const linkMode = window.SEARCH_LINK_MODE || "view";
      const directProtocol = /^(magnet:|ed2k:|thunder:)/i.test(item.share_link);
      const actionLabel = linkMode === "view" && !directProtocol ? "动态转存" : "打开资源";

      html += `
        <article class="serp-item has-poster" data-index="${startIndex + idx}">
          <div class="serp-item__content">
            <div class="serp-item__source">
              <img src="${iconUrl}" alt="${escapeHtml(item.cloud_name)}">
              <strong class="serp-item__cloud-name">${escapeHtml(item.cloud_name)}</strong>
              <span class="serp-item__timestamp">· ${escapeHtml(timestamp)}</span>
              ${sourceBadge}
              ${pwdBadge}
            </div>
            <h2>
              ${freshnessBadge}
              <a href="javascript:void(0)" class="action-btn-get" data-title="${escapeHtml(item.title)}" data-url="${escapeHtml(item.share_link)}" data-cloud="${escapeHtml(item.cloud_name)}">
                ${escapeHtml(item.title)}
              </a>
            </h2>
            <p class="serp-item__description" title="${escapeHtml(description)}">${escapeHtml(description)}</p>
            <div class="serp-meta serp-item__actions">
              <span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"></path></svg>
                资源来自 ${escapeHtml(sourceName)}
              </span>
              <a class="serp-action-pill action-btn-get" href="javascript:void(0)" data-title="${escapeHtml(item.title)}" data-url="${escapeHtml(item.share_link)}" data-cloud="${escapeHtml(item.cloud_name)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M14 3h7v7M10 14 21 3"></path><path d="M19 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6"></path></svg>
                ${actionLabel}
              </a>
              <span class="${status.className}">
                ${status.className === "is-checking" ? "" : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m13 2-3 8h7l-6 12 2-9H6l7-11Z"></path></svg>'}
                ${status.prefix ? `${escapeHtml(status.prefix)} ` : ""}${escapeHtml(status.label)}
              </span>
            </div>
          </div>
          <div class="serp-item__poster ${item.cover_url ? '' : 'is-broken'}">
            ${item.cover_url ? `<img src="${escapeHtml(item.cover_url)}" alt="${escapeHtml(item.title)}" loading="lazy" onerror="this.parentElement.classList.add('is-broken'); this.remove();">` : ''}
          </div>
        </article>
      `;
    });

    resultsList.innerHTML = html;
    bindActionButtons();
    renderPagination(filtered.length);
    startVisibleLinkChecks(currentBatch, searchGeneration);
  }

  function startVisibleLinkChecks(items, generation) {
    if (window.ENABLE_LINK_CHECK !== true) return;
    const enabledPans = Array.isArray(window.ENABLED_CHECK_PANS) ? window.ENABLED_CHECK_PANS : [];
    const pending = items.filter((item) =>
      !item.checkStarted &&
      enabledPans.includes(item.cloud_name) &&
      /^https?:\/\//i.test(item.share_link)
    );
    if (!pending.length) return;

    pending.forEach((item) => {
      item.checkStarted = true;
      item.status = "checking";
    });
    renderResults();

    fetch("/api/check/links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: pending.map((item) => ({
          url: item.share_link,
          password: item.password,
          disk_type: item.cloud_name,
        })),
      }),
    })
      .then((response) => response.json())
      .then((payload) => {
        if (generation !== searchGeneration || !Array.isArray(payload.results)) return;
        payload.results.forEach((result, index) => {
          if (pending[index]) pending[index].status = result.state || "uncertain";
        });
        updateStats();
        renderResults();
      })
      .catch(() => {
        if (generation !== searchGeneration) return;
        pending.forEach((item) => { item.status = "uncertain"; });
        updateStats();
        renderResults();
      });
  }

  function getSourceDisplayName(source, sourceType, sourceDisplay) {
    const normalizedType = String(sourceType || "").trim().toLowerCase();
    if (["api", "other"].includes(normalizedType) || normalizedType.startsWith("api:")) return "API";
    if (["telegram", "tg"].includes(normalizedType) || /^(telegram|tg):/.test(normalizedType)) return "TG";
    if (normalizedType === "plugin" || normalizedType.startsWith("plugin:")) return "插件";
    if (["internal", "hot"].includes(normalizedType)) return "站长自建";

    const display = String(sourceDisplay || "").trim();
    if (["API", "TG", "插件", "站长自建"].includes(display)) return display;

    const value = String(source || "").trim();
    if (!value || /^(other|api)$/i.test(value) || /^api:/i.test(value)) return "API";
    if (/^(hot|internal)$/i.test(value)) return "站长自建";
    if (/telegram|\btg\b|电报/i.test(value)) return "TG";
    if (/^plugin(?::|$)/i.test(value)) return "插件";
    return "API";
  }

  function getStatusDisplay(status) {
    const value = String(status || "").toLowerCase();
    if (["checking", "pending", "检测中"].includes(value)) return { label: "检测中", prefix: "", className: "is-checking" };
    if (["valid", "active", "ok", "有效", "可用", "true"].includes(value)) return { label: "资源有效", prefix: "状态", className: "is-valid" };
    if (["invalid", "expired", "dead", "bad", "失效", "无效", "false"].includes(value)) return { label: "资源失效", prefix: "状态", className: "is-invalid" };
    if (["locked", "需要提取码"].includes(value)) return { label: "需要提取码", prefix: "状态", className: "is-error" };
    if (["uncertain", "unsupported"].includes(value)) return { label: "暂无法确认", prefix: "状态", className: "is-unknown" };
    return { label: "未知", prefix: "状态", className: "is-unknown" };
  }

  function getFreshnessLabel(value) {
    if (!value || value === "未知时间") return "";
    let date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      const shortDate = value.match(/^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
      if (shortDate) {
        const year = new Date().getFullYear();
        date = new Date(year, Number(shortDate[1]) - 1, Number(shortDate[2]), Number(shortDate[3]), Number(shortDate[4]));
      }
    }
    if (Number.isNaN(date.getTime())) return "";
    const age = Date.now() - date.getTime();
    if (age < 0) return "24小时内";
    if (age <= 24 * 60 * 60 * 1000) return "24小时内";
    if (age <= 72 * 60 * 60 * 1000) return "72小时内";
    return "更早时间";
  }

  function formatTimestamp(value) {
    const shortValue = value.match(/^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
    if (shortValue) {
      return `${shortValue[1].padStart(2, "0")}-${shortValue[2].padStart(2, "0")} ${shortValue[3].padStart(2, "0")}:${shortValue[4]}`;
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  }

  // 6. 按钮点击事件绑定
  function bindActionButtons() {
    // 复制按钮
    resultsList.querySelectorAll(".action-btn-copy").forEach((btn) => {
      btn.addEventListener("click", () => {
        const url = btn.dataset.url;
        const pwd = btn.dataset.pwd;
        const textToCopy = pwd ? `${url} 提取码: ${pwd}` : url;
        copyToClipboard(textToCopy);
      });
    });

    // 获取资源 (动态转存与扫码保存)
    resultsList.querySelectorAll(".action-btn-get").forEach((btn) => {
      btn.addEventListener("click", () => {
        const title = btn.dataset.title;
        const url = btn.dataset.url;
        const cloud = btn.dataset.cloud;
        handleGetResource(title, url, cloud);
      });
    });
  }

  // 7. 处理获取资源与变现弹窗
  async function handleGetResource(title, url, cloudName) {
    const linkMode = window.SEARCH_LINK_MODE || "view";

    // 如果为复制模式或磁力链接，直接复制并跳转
    if (linkMode === "copy" || url.startsWith("magnet:") || url.startsWith("ed2k:")) {
      copyToClipboard(url);
      window.open(url, "_blank");
      return;
    }

    // 打开转存弹窗
    openModal(title, url, cloudName);

    try {
      // 请求转存 API
      const resp = await fetch("/api/view-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title,
          url: url,
          netdisk_name: cloudName,
        }),
      });

      let finalUrl = url;
      if (resp.ok) {
        const data = await resp.json();
        finalUrl = data.url || url;
      }
      showModalContent(title, finalUrl, cloudName);
    } catch (e) {
      console.warn("转存失败，回退原始链接:", e);
      showModalContent(title, url, cloudName);
    }
  }

  function openModal(title, url, cloudName) {
    if (!modalBackdrop || !modalShell) return;
    currentFinalUrl = url;
    modalTitle.textContent = title;
    modalLink.textContent = url;
    modalLink.href = url;
    modalLoading.style.display = "block";
    modalContent.style.display = "none";
    modalBackdrop.hidden = false;
    modalShell.hidden = false;
  }

  function showModalContent(title, finalUrl, cloudName) {
    currentFinalUrl = finalUrl;
    modalLoading.style.display = "none";
    modalContent.style.display = "block";
    modalTitle.textContent = title;
    modalLink.textContent = finalUrl;
    modalLink.href = finalUrl;

    const enablePcQr = window.ENABLE_PC_QR_CODE !== false;
    const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

    if (enablePcQr && !isMobile && modalQrImg) {
      modalQrContainer.style.display = "block";
      const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=8&data=${encodeURIComponent(finalUrl)}`;
      modalQrImg.src = qrApiUrl;
    } else {
      modalQrContainer.style.display = "none";
    }
  }

  function closeModal() {
    if (modalBackdrop && modalShell) {
      modalBackdrop.hidden = true;
      modalShell.hidden = true;
    }
  }

  if (modalBackdrop) modalBackdrop.addEventListener("click", closeModal);
  const closeBtns = document.querySelectorAll("[data-aurora-modal-close]");
  closeBtns.forEach((b) => b.addEventListener("click", closeModal));

  if (modalCopyBtn) {
    modalCopyBtn.addEventListener("click", () => {
      if (currentFinalUrl) copyToClipboard(currentFinalUrl);
    });
  }
  if (modalOpenBtn) {
    modalOpenBtn.addEventListener("click", () => {
      if (currentFinalUrl) window.open(currentFinalUrl, "_blank");
    });
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        showToast("已成功复制链接到剪贴板！");
      }).catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      showToast("已成功复制链接到剪贴板！");
    } catch (e) {
      showToast("复制失败，请手动长按复制");
    }
    document.body.removeChild(ta);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 8. 启动 SSE 流式搜索 (修复接收数据格式：支持 results 与 items)
  function startSearch(kw) {
    kw = (kw || "").trim();
    if (!kw) return;

    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }

    searchGeneration += 1;
    allItems = [];
    currentPage = 1;
    resultsList.innerHTML = `
      <div class="loading-state" style="padding: 40px 0; text-align: center;">
        <div class="aurora-spinner"></div>
        <p style="color: var(--text-muted, #94a3b8); font-size: 14px;">正在跨网盘并发检索「${escapeHtml(kw)}」公开资源，请稍等...</p>
      </div>
    `;
    if (resultSummaryText) resultSummaryText.textContent = `正在搜索「${kw}」...`;
    if (countStatsValid) countStatsValid.textContent = "有效资源 0 条";
    if (countStatsFailed) countStatsFailed.textContent = "已失效 0 条";

    const sseUrl = `/api/search_stream?keyword=${encodeURIComponent(kw)}`;
    sseSource = new EventSource(sseUrl);

    sseSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const incomingList = data.results || data.items || [];

        if (Array.isArray(incomingList) && incomingList.length > 0) {
          const newNormalized = incomingList.map(normalizeItem).filter(Boolean);
          dedupeAndAppend(newNormalized);
          updateStats();
          renderResults();
        }

        if (data.type === "complete") {
          finishSearch(kw);
        } else if (data.type === "error") {
          resultsList.innerHTML = `<div class="empty-state"><p style="color:#ef4444;">${escapeHtml(data.message || "搜索失败")}</p></div>`;
          if (sseSource) sseSource.close();
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    };

    sseSource.onerror = (err) => {
      console.warn("SSE error or finished", err);
      finishSearch(kw);
    };
  }

  function dedupeAndAppend(newItems) {
    const seen = new Set(allItems.map((it) => it.share_link || it.title));
    newItems.forEach((it) => {
      const key = it.share_link || it.title;
      if (!seen.has(key)) {
        seen.add(key);
        allItems.push(it);
      }
    });
  }

  function updateStats() {
    const failedCount = allItems.filter((i) => ["invalid", "expired", "dead", "bad", "失效", "无效", "false"].includes(String(i.status || "").toLowerCase())).length;
    const validCount = Math.max(0, allItems.length - failedCount);
    if (countStatsValid) countStatsValid.textContent = `有效资源 ${validCount} 条`;
    if (countStatsFailed) countStatsFailed.textContent = `已失效 ${failedCount} 条`;
    if (resultSummaryText && searchInput) {
      resultSummaryText.textContent = `正在搜索「${searchInput.value.trim()}」，已获取 ${allItems.length} 条资源...`;
    }
  }

  function finishSearch(kw) {
    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }
    updateStats();
    if (resultSummaryText) {
      resultSummaryText.textContent = `已完成「${kw}」搜索，共检索到 ${allItems.length} 个结果`;
    }
  }

  // 9. 3D 热词轨道球 (采用 3D 动态轨道球投影算法)
  function initHotTags() {
    const container = document.getElementById("hotSearchList");
    if (!container) return;

    if (window.ENABLE_HOT_SEARCHES === false) {
      const parentCard = container.closest(".related-card");
      if (parentCard) parentCard.style.display = "none";
      return;
    }

    const defaultWords = [
      "兰香如故", "现在就出发", "凡人修仙传", "余红旧事", "希望",
      "我不是大师", "无可替代", "仙逆", "我是证人"
    ];
    const words = (Array.isArray(window.HOT_SEARCH_WORDS) && window.HOT_SEARCH_WORDS.length > 0)
      ? window.HOT_SEARCH_WORDS
      : defaultWords;

    const focusPositions = [
      [178, 72, 1.03, -4],
      [246, 98, 0.96, 3],
      [284, 166, 0.92, 5],
      [258, 238, 1.02, -3],
      [184, 284, 0.98, 2],
      [108, 246, 0.96, -5],
      [76, 176, 0.94, 4],
      [112, 106, 0.98, -3],
      [222, 70, 0.9, 4],
      [92, 218, 0.88, 2]
    ];

    let html = "";
    words.forEach((w, idx) => {
      const isFront = idx < focusPositions.length;
      let x, y, scale, rotate, blur, opacity, z;

      if (isFront) {
        [x, y, scale, rotate] = focusPositions[idx];
        blur = 0;
        opacity = 1;
        z = 80 - idx;
      } else {
        const ring = idx % 3;
        const angle = (idx * 37 + 15) * Math.PI / 180;
        const radius = [88, 112, 136][ring];
        x = Math.round(180 + Math.cos(angle) * radius);
        y = Math.round(188 + Math.sin(angle) * radius * 0.92);
        scale = [0.65, 0.72, 0.8][ring];
        blur = [1.2, 2.2, 3.4][ring];
        opacity = [0.65, 0.5, 0.35][ring];
        rotate = Math.round((idx % 5) * 4 - 8);
        z = 20 - ring;
      }

      const toneClass = idx % 3 === 0 ? "hot-tag--tone-1" : "";
      html += `<a href="javascript:void(0)" class="hot-tag ${toneClass}" style="--hot-x:${x}px;--hot-y:${y}px;--hot-scale:${scale};--hot-rotate:${rotate}deg;--hot-blur:${blur}px;--hot-opacity:${opacity};--hot-z:${z};">${escapeHtml(w)}</a>`;
    });

    container.innerHTML = html;

    container.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        const word = a.textContent.trim();
        if (word && searchInput) {
          searchInput.value = word;
          document.title = `${word} - 搜索结果`;
          startSearch(word);
          history.replaceState(null, "", `/search?q=${encodeURIComponent(word)}`);
        }
      });
    });
  }

  // 11. 初始化入口
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    bindTabs();
    initHotTags();

    if (searchForm && searchInput) {
      searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const kw = searchInput.value.trim();
        if (kw) {
          document.title = `${kw} - 搜索结果`;
          startSearch(kw);
          history.replaceState(null, "", `/search?q=${encodeURIComponent(kw)}`);
        }
      });
    }

    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q") || params.get("keyword") || "";
    const initialDrive = params.get("drive") || "";

    if (initialDrive) {
      currentDriveFilter = initialDrive;
      sourceChips.forEach((chip) => {
        if (chip.dataset.drive === initialDrive) {
          sourceChips.forEach((c) => c.classList.remove("is-active"));
          chip.classList.add("is-active");
        }
      });
    }

    if (initialQuery && searchInput) {
      searchInput.value = initialQuery;
      document.title = `${initialQuery} - 搜索结果`;
      startSearch(initialQuery);
    }
  });
})();
