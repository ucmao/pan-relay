function getFrontendDisplayNetdiskCheckboxes() {
    return Array.from(document.querySelectorAll('.frontend-display-netdisk-checkbox'));
}

function updateDynamicTransferStatusVisibility() {
    const netdisksWrapper = document.getElementById('dynamicTransferNetdisksWrapper');
    const rawLinkWrapper = document.getElementById('rawLinkSettingsWrapper');
    const select = document.getElementById('frontendLinkModeSelect');
    const badge = document.getElementById('frontendLinkModeBadge');
    const kpiEl = document.getElementById('kpiDeliveryMode');

    const mode = select ? select.value : 'copy';
    const isView = mode === 'view';

    if (kpiEl) {
        kpiEl.textContent = isView ? '动态转存' : '原始链接';
    }
    if (badge) {
        badge.textContent = isView ? '动态转存模式' : '原始链接模式';
        badge.className = `badge ${isView ? 'badge-warning' : 'badge-info'} text-xs`;
    }
    if (netdisksWrapper) {
        netdisksWrapper.classList.toggle('hidden', !isView);
    }
    if (rawLinkWrapper) {
        rawLinkWrapper.classList.toggle('hidden', isView);
    }
    updateEnabledDynamicTransferPansCount();
}

function updateFrontendConfigPanelsState(enabled) {
    const strategyContainer = document.getElementById('frontendLinkStrategyContainer');
    if (strategyContainer) {
        strategyContainer.classList.toggle('hidden', !enabled);
    }
    const grayPanels = [
        document.getElementById('linkCheckPanel'),
        document.getElementById('frontendDisplayNetdisksPanel'),
        document.getElementById('frontendBrandPanel')
    ];
    grayPanels.forEach(panel => {
        if (!panel) return;
        if (enabled) {
            panel.classList.remove('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = false;
            });
        } else {
            panel.classList.add('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = true;
            });
        }
    });
}

function bindFrontendLinkModeEvents() {
    const select = document.getElementById('frontendLinkModeSelect');
    if (select) {
        select.addEventListener('change', updateDynamicTransferStatusVisibility);
    }
}

// 旧版 Tab 标识兼容：广告管理已并入转存管理，网盘账号池已独立为单独页面
const LEGACY_SYSTEM_TAB_MAP = { ads: 'storage' };
const CLOUD_ACCOUNTS_PAGE_URL = '/admin/cloud-accounts';

function switchSystemTab(target, updateHash = true) {
    // 本文件也被前台 Web / 开放 API 配置页加载，只在系统配置页处理 Tab
    if (!document.querySelector('[data-system-tab-target]')) return;
    if (target === 'accounts') {
        window.location.replace(CLOUD_ACCOUNTS_PAGE_URL);
        return;
    }
    const validTabs = ['storage', 'security'];
    const mapped = LEGACY_SYSTEM_TAB_MAP[target] || target;
    const normalized = validTabs.includes(mapped) ? mapped : 'storage';
    try {
        localStorage.setItem('panrelay_system_tab', normalized);
    } catch (e) { }

    const tabBtns = document.querySelectorAll('[data-system-tab-target]');
    if (tabBtns.length === 0) return;

    tabBtns.forEach((b) => {
        b.classList.toggle('is-active', b.getAttribute('data-system-tab-target') === normalized);
    });
    document.querySelectorAll('.system-tab-pane').forEach((pane) => {
        pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
    });

    if (updateHash && window.history?.replaceState) {
        window.history.replaceState(null, '', `#${normalized}`);
    }
}

function bindSystemTabEvents() {
    document.querySelectorAll('[data-system-tab-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-system-tab-target');
            switchSystemTab(target, true);
        });
    });

    const queryTab = new URLSearchParams(window.location.search).get('tab');
    const hash = (window.location.hash || '').replace('#', '').trim();
    let savedTab = null;
    try {
        savedTab = localStorage.getItem('panrelay_system_tab');
    } catch (e) { }
    if (savedTab === 'accounts') savedTab = null;
    switchSystemTab(queryTab || hash || savedTab || 'storage', false);
}

function renderDynamicTransferStatuses(statuses, summary) {
    const summaryEl = document.getElementById('dynamicTransferStatusSummary');
    const manageLink = document.getElementById('dynamicTransferManageLink');

    const safeStatuses = Array.isArray(statuses) ? statuses : [];
    const enabledCount = Number(summary?.enabled_count || 0);
    const totalCount = Number(summary?.total_count || safeStatuses.length || 8);

    if (summaryEl) {
        summaryEl.textContent = `${enabledCount}/${totalCount} 凭证就绪`;
    }

    if (manageLink) {
        manageLink.onclick = (e) => {
            const accMainTabBtn = document.querySelector('[data-system-tab-target="accounts"]');
            if (accMainTabBtn) {
                e.preventDefault();
                accMainTabBtn.click();
            }
        };
    }

    safeStatuses.forEach((item) => {
        const badgeEl = document.querySelector(`.dynamic-card-status-badge[data-cloud-badge="${item.cloud_name}"]`);
        if (!badgeEl) return;

        const statusClass = item.status || 'missing';
        const badgeText = item.title || (statusClass === 'enabled' ? '已就绪' : (statusClass === 'invalid' ? '异常' : '未配置'));
        const isEnabled = statusClass === 'enabled';
        const isInvalid = statusClass === 'invalid';

        badgeEl.className = 'dynamic-card-status-badge';
        if (isEnabled) {
            badgeEl.classList.add('status-ok');
        } else if (isInvalid) {
            badgeEl.classList.add('status-invalid');
        } else {
            badgeEl.classList.add('status-missing');
        }

        badgeEl.setAttribute('title', `${item.cloud_name}: ${item.description || badgeText}`);
        badgeEl.innerHTML = `
            <span class="status-dot"></span>
            <span class="status-text">${badgeText}</span>
        `;
    });
}

function updateFrontendNetdiskSelectionUI() {
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
    const selectedCountEl = document.getElementById('frontendNetdiskSelectedCount');
    const toggleAllButton = document.getElementById('toggleAllFrontendNetdisksButton');

    if (selectedCountEl) {
        selectedCountEl.textContent = String(selectedCount);
    }

    if (toggleAllButton) {
        toggleAllButton.textContent = selectedCount === checkboxes.length ? '取消全选' : '全选';
    }
}

function bindFrontendNetdiskCheckboxEvents() {
    getFrontendDisplayNetdiskCheckboxes().forEach((checkbox) => {
        checkbox.addEventListener('change', async () => {
            updateFrontendNetdiskSelectionUI();
            await saveFrontendDisplayNetdisks();
        });
    });
}

function updateApiConfigPanelsState(enabled) {
    const panels = [
        document.getElementById('apiDefaultStrategyPanel'),
        document.getElementById('transferAuthPanel')
    ];
    panels.forEach(panel => {
        if (!panel) return;
        if (enabled) {
            panel.classList.remove('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = false;
            });
        } else {
            panel.classList.add('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = true;
            });
        }
    });
}

async function loadPublicSearchApiConfig() {
    try {
        const response = await fetch('/admin/api/public-search-api-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const toggle = document.getElementById('publicSearchApiToggle');
        const badge = document.getElementById('publicSearchApiBadge');
        if (toggle) {
            toggle.checked = Boolean(data.enabled);
        }
        updateApiConfigPanelsState(Boolean(data.enabled));

        if (badge) {
            badge.textContent = data.enabled ? '已开启' : '已关闭';
            badge.className = data.enabled ? 'badge badge-success text-xs' : 'badge badge-secondary text-xs';
        }

        const kpiPublicApiStatus = document.getElementById('kpiPublicApiStatus');
        if (kpiPublicApiStatus) {
            kpiPublicApiStatus.textContent = data.enabled ? '已开启' : '已关闭';
            kpiPublicApiStatus.style.color = data.enabled ? 'var(--admin-success-text)' : 'var(--admin-text-muted)';
        }
    } catch (error) {
        console.error('加载公开聚合接口配置失败:', error);
        showToast('加载公开聚合接口配置失败，请检查后端日志。', 'danger');
    }
}

async function savePublicSearchApiConfig() {
    const toggle = document.getElementById('publicSearchApiToggle');
    const enabled = toggle ? toggle.checked : true;
    updateApiConfigPanelsState(enabled);

    try {
        const response = await fetch('/admin/api/public-search-api-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message, 'success');
        await loadPublicSearchApiConfig();
    } catch (error) {
        console.error('保存公开聚合接口配置失败:', error);
        showToast(`保存公开聚合接口配置失败: ${error.message}`, 'danger');
        await loadPublicSearchApiConfig();
    }
}

async function loadAllowExcelDownloadConfig() {
    try {
        const response = await fetch('/admin/api/allow-excel-download-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const toggle = document.getElementById('allowExcelDownloadToggle');
        const badge = document.getElementById('allowExcelDownloadBadge');
        if (toggle) {
            toggle.checked = Boolean(data.enabled);
        }
        if (badge) {
            badge.textContent = data.enabled ? '允许下载' : '禁止下载';
            badge.className = data.enabled ? 'badge badge-success text-xs' : 'badge badge-secondary text-xs';
        }
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('加载 Excel 下载配置失败:', error);
        showToast('加载 Excel 下载配置失败，请检查后端日志。', 'danger');
    }
}

async function saveAllowExcelDownloadConfig() {
    const toggle = document.getElementById('allowExcelDownloadToggle');
    const enabled = toggle ? toggle.checked : true;

    try {
        const response = await fetch('/admin/api/allow-excel-download-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message, 'success');
        await loadAllowExcelDownloadConfig();
    } catch (error) {
        console.error('保存 Excel 下载配置失败:', error);
        showToast(`保存 Excel 下载配置失败: ${error.message}`, 'danger');
        await loadAllowExcelDownloadConfig();
    }
}

async function loadPcQrCodeConfig() {
    try {
        const response = await fetch('/admin/api/pc-qr-code-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const toggle = document.getElementById('enablePcQrCodeToggle');
        if (toggle) {
            toggle.checked = Boolean(data.enabled);
        }
    } catch (error) {
        console.error('加载 PC 转存二维码引导配置失败:', error);
    }
}

async function savePcQrCodeConfig() {
    const toggle = document.getElementById('enablePcQrCodeToggle');
    const enabled = toggle ? toggle.checked : true;

    try {
        const response = await fetch('/admin/api/pc-qr-code-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '配置已保存', 'success');
    } catch (error) {
        console.error('保存 PC 转存二维码引导配置失败:', error);
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadPcQrCodeConfig();
    }
}

async function loadFrontendGithubConfig() {
    try {
        const response = await fetch('/admin/api/frontend-github-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const toggle = document.getElementById('enableFrontendGithubToggle');
        if (toggle) {
            toggle.checked = Boolean(data.enabled);
        }
        const footerInput = document.getElementById('frontendFooterTextInput');
        if (footerInput) {
            footerInput.value = data.footer_text || '';
        }
        const footerToggle = document.getElementById('enableFrontendFooterTextToggle');
        if (footerToggle) {
            footerToggle.checked = data.footer_enabled !== false;
            updateFrontendFooterTextState(footerToggle.checked);
        }
    } catch (error) {
        console.error('加载前台 GitHub 标识配置失败:', error);
    }
}

function updateFrontendFooterTextState(enabled) {
    const input = document.getElementById('frontendFooterTextInput');
    if (input) {
        input.disabled = !enabled;
        input.classList.toggle('opacity-50', !enabled);
    }
}

async function toggleFrontendFooterTextState() {
    const toggle = document.getElementById('enableFrontendFooterTextToggle');
    const enabled = toggle ? toggle.checked : true;
    updateFrontendFooterTextState(enabled);
    try {
        const response = await fetch('/admin/api/frontend-github-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ footer_enabled: enabled })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        showToast(data.message || (enabled ? '页脚文字已启用' : '页脚文字已停用'), 'success');
    } catch (error) {
        console.error('保存页脚文字开关失败:', error);
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendGithubConfig();
    }
}

async function saveFrontendGithubConfig() {
    const toggle = document.getElementById('enableFrontendGithubToggle');
    const enabled = toggle ? toggle.checked : true;

    try {
        const response = await fetch('/admin/api/frontend-github-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '配置已保存', 'success');
    } catch (error) {
        console.error('保存前台 GitHub 标识配置失败:', error);
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendGithubConfig();
    }
}

let footerTextSaveTimer = null;
function scheduleFrontendFooterTextSave(delay = 600) {
    clearTimeout(footerTextSaveTimer);
    if (delay === 0) {
        saveFrontendFooterText(true);
        return;
    }
    footerTextSaveTimer = setTimeout(() => saveFrontendFooterText(true), delay);
}

async function saveFrontendFooterText(isSilent = false) {
    const input = document.getElementById('frontendFooterTextInput');
    const footer_text = input ? input.value : '';
    const statusEl = document.getElementById('footerTextSaveStatus');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i>保存中...';
    }
    try {
        const response = await fetch('/admin/api/frontend-github-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ footer_text })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-check text-emerald-500 mr-1"></i>已保存';
            setTimeout(() => {
                if (statusEl && statusEl.innerHTML.includes('已保存')) {
                    statusEl.innerHTML = '';
                }
            }, 2500);
        }
        if (!isSilent) {
            showToast(data.message || '页脚文字已保存', 'success');
        }
    } catch (error) {
        console.error('保存前台页脚文字失败:', error);
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-exclamation-circle text-rose-500 mr-1"></i>保存失败';
        }
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendGithubConfig();
    }
}

async function loadFrontendCopyrightText() {
    try {
        const response = await fetch('/admin/api/frontend-copyright-config');
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        const input = document.getElementById('frontendCopyrightTextInput');
        if (input) input.value = data.copyright_text || '';
        const toggle = document.getElementById('enableFrontendCopyrightToggle');
        if (toggle) {
            toggle.checked = data.enabled !== false;
            updateFrontendCopyrightState(toggle.checked);
        }
    } catch (error) {
        console.error('加载版权信息失败:', error);
    }
}

function updateFrontendCopyrightState(enabled) {
    const input = document.getElementById('frontendCopyrightTextInput');
    if (input) {
        input.disabled = !enabled;
        input.classList.toggle('opacity-50', !enabled);
    }
}

async function toggleFrontendCopyrightState() {
    const toggle = document.getElementById('enableFrontendCopyrightToggle');
    const enabled = toggle ? toggle.checked : true;
    updateFrontendCopyrightState(enabled);
    try {
        const response = await fetch('/admin/api/frontend-copyright-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        showToast(data.message || (enabled ? '版权信息已启用' : '版权信息已停用'), 'success');
    } catch (error) {
        console.error('保存版权开关失败:', error);
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendCopyrightText();
    }
}

let copyrightTextSaveTimer = null;
function scheduleFrontendCopyrightTextSave(delay = 600) {
    clearTimeout(copyrightTextSaveTimer);
    if (delay === 0) {
        saveFrontendCopyrightText(true);
        return;
    }
    copyrightTextSaveTimer = setTimeout(() => saveFrontendCopyrightText(true), delay);
}

async function saveFrontendCopyrightText(isSilent = false) {
    const input = document.getElementById('frontendCopyrightTextInput');
    const copyright_text = input ? input.value : '';
    const statusEl = document.getElementById('copyrightTextSaveStatus');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i>保存中...';
    }
    try {
        const response = await fetch('/admin/api/frontend-copyright-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ copyright_text })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-check text-emerald-500 mr-1"></i>已保存';
            setTimeout(() => {
                if (statusEl && statusEl.innerHTML.includes('已保存')) {
                    statusEl.innerHTML = '';
                }
            }, 2500);
        }
        if (!isSilent) {
            showToast(data.message || '版权信息已保存', 'success');
        }
    } catch (error) {
        console.error('保存版权信息失败:', error);
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-exclamation-circle text-rose-500 mr-1"></i>保存失败';
        }
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendCopyrightText();
    }
}

async function loadFrontendDisclaimerText() {
    try {
        const response = await fetch('/admin/api/frontend-disclaimer-config');
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        const input = document.getElementById('frontendDisclaimerTextInput');
        if (input) input.value = data.disclaimer_text || '';
    } catch (error) {
        console.error('加载免责声明失败:', error);
    }
}

let disclaimerTextSaveTimer = null;
function scheduleFrontendDisclaimerTextSave(delay = 600) {
    clearTimeout(disclaimerTextSaveTimer);
    if (delay === 0) {
        saveFrontendDisclaimerText(true);
        return;
    }
    disclaimerTextSaveTimer = setTimeout(() => saveFrontendDisclaimerText(true), delay);
}

async function saveFrontendDisclaimerText(isSilent = false) {
    const input = document.getElementById('frontendDisclaimerTextInput');
    const disclaimer_text = input ? input.value : '';
    const statusEl = document.getElementById('disclaimerTextSaveStatus');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i>保存中...';
    }
    try {
        const response = await fetch('/admin/api/frontend-disclaimer-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ disclaimer_text })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-check text-emerald-500 mr-1"></i>已保存';
            setTimeout(() => {
                if (statusEl && statusEl.innerHTML.includes('已保存')) {
                    statusEl.innerHTML = '';
                }
            }, 2500);
        }
        if (!isSilent) {
            showToast(data.message || '免责声明已保存', 'success');
        }
    } catch (error) {
        console.error('保存前台免责声明失败:', error);
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-exclamation-circle text-rose-500 mr-1"></i>保存失败';
        }
        showToast(`保存配置失败: ${error.message}`, 'danger');
        await loadFrontendDisclaimerText();
    }
}

async function loadFrontendSeoConfig() {
    try {
        const response = await fetch('/admin/api/frontend-seo-config');
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        const config = data.config || {};
        const home = config.home || {};
        const search = config.search || {};
        const friendLinks = config.friend_links || {};
        const detail = config.detail || {};
        const announcement = config.announcement || {};
        const fields = {
            seoHomeTitle: home.title,
            seoHomeDescription: home.description,
            seoHomeKeywords: home.keywords,
            seoSearchTitle: search.title,
            seoSearchDescription: search.description,
            seoSearchKeywords: search.keywords,
            seoDetailTitle: detail.title,
            seoDetailDescription: detail.description,
            seoDetailKeywords: detail.keywords,
            seoDetailSiteUrl: detail.site_url,
        };
        Object.entries(fields).forEach(([id, value]) => {
            const input = document.getElementById(id);
            if (input && typeof value === 'string') input.value = value;
        });
        const detailEnabled = document.getElementById('seoDetailEnabled');
        if (detailEnabled) {
            detailEnabled.checked = detail.enabled === true;
            updateDetailPageState(detailEnabled.checked);
        }
        const friendLinksEnabled = document.getElementById('seoFriendLinksEnabled');
        if (friendLinksEnabled) {
            friendLinksEnabled.checked = friendLinks.enabled === true;
            updateFriendLinksState(friendLinksEnabled.checked);
        }
        const friendLinksItems = document.getElementById('seoFriendLinksItems');
        if (friendLinksItems && Array.isArray(friendLinks.items)) {
            friendLinksItems.value = friendLinks.items
                .filter((item) => item && typeof item.name === 'string' && typeof item.url === 'string')
                .map((item) => `${item.name} | ${item.url}`)
                .join('\n');
        }
        const announcementEnabled = document.getElementById('seoAnnouncementEnabled');
        if (announcementEnabled) {
            announcementEnabled.checked = announcement.enabled !== false;
            updateAnnouncementState(announcementEnabled.checked);
        }
        const announcementText = document.getElementById('seoAnnouncementText');
        if (announcementText && typeof announcement.text === 'string') announcementText.value = announcement.text;
    } catch (error) {
        console.error('加载前台 SEO 配置失败:', error);
    }
}

function updateAnnouncementState(enabled) {
    const text = document.getElementById('seoAnnouncementText');
    if (text) {
        text.disabled = !enabled;
        text.classList.toggle('opacity-50', !enabled);
    }
}

function toggleAnnouncementState() {
    const toggle = document.getElementById('seoAnnouncementEnabled');
    const enabled = toggle ? toggle.checked : true;
    updateAnnouncementState(enabled);
    saveFrontendSeoConfig(true);
    showToast(enabled ? '站点公告已启用' : '站点公告已停用', 'success');
}

function updateDetailPageState(enabled) {
    const fields = document.getElementById('seoDetailFields');
    if (fields) fields.classList.toggle('opacity-50', !enabled);
}

function toggleDetailPageState() {
    const toggle = document.getElementById('seoDetailEnabled');
    const enabled = toggle ? toggle.checked : false;
    updateDetailPageState(enabled);
    saveFrontendSeoConfig(true);
    showToast(enabled ? '资源详情页与站点地图已启用' : '资源详情页与站点地图已停用', 'success');
}

function updateFriendLinksState(enabled) {
    const items = document.getElementById('seoFriendLinksItems');
    if (items) {
        items.disabled = !enabled;
        items.classList.toggle('opacity-50', !enabled);
    }
}

function toggleFriendLinksState() {
    const toggle = document.getElementById('seoFriendLinksEnabled');
    const enabled = toggle ? toggle.checked : false;
    updateFriendLinksState(enabled);
    saveFrontendSeoConfig(true);
    showToast(enabled ? '友情链接已启用' : '友情链接已停用', 'success');
}

let seoSaveTimer = null;
let isSeoConfigSaving = false;

function scheduleSeoConfigSave(delay = 600) {
    clearTimeout(seoSaveTimer);
    if (delay === 0) {
        saveFrontendSeoConfig(true);
        return;
    }
    seoSaveTimer = setTimeout(() => {
        saveFrontendSeoConfig(true);
    }, delay);
}

async function saveFrontendSeoConfig(isSilent = false) {
    if (isSeoConfigSaving) return;
    const value = (id) => document.getElementById(id)?.value || '';
    const payload = {
        home: {
            title: value('seoHomeTitle'),
            description: value('seoHomeDescription'),
            keywords: value('seoHomeKeywords'),
        },
        search: {
            title: value('seoSearchTitle'),
            description: value('seoSearchDescription'),
            keywords: value('seoSearchKeywords'),
        },
        detail: {
            enabled: Boolean(document.getElementById('seoDetailEnabled')?.checked),
            title: value('seoDetailTitle'),
            description: value('seoDetailDescription'),
            keywords: value('seoDetailKeywords'),
            site_url: value('seoDetailSiteUrl'),
        },
        friend_links: {
            enabled: Boolean(document.getElementById('seoFriendLinksEnabled')?.checked),
            items: (document.getElementById('seoFriendLinksItems')?.value || '')
                .split(/\r?\n/)
                .map((line) => {
                    const separator = line.indexOf('|');
                    if (separator < 0) return null;
                    return { name: line.slice(0, separator).trim(), url: line.slice(separator + 1).trim() };
                })
                .filter((item) => item && (item.name || item.url)),
        },
        announcement: {
            enabled: Boolean(document.getElementById('seoAnnouncementEnabled')?.checked),
            text: value('seoAnnouncementText'),
        },
    };

    const statusEl = document.getElementById('seoSaveStatus');
    const saveBtn = document.getElementById('saveFrontendSeoBtn');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i>保存中...';
    }
    if (!isSilent && saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>保存中...';
    }

    isSeoConfigSaving = true;
    try {
        const response = await fetch('/admin/api/frontend-seo-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-check text-emerald-500 mr-1"></i>已自动保存';
            setTimeout(() => {
                if (statusEl && statusEl.innerHTML.includes('已自动保存')) {
                    statusEl.innerHTML = '';
                }
            }, 2500);
        }
        if (!isSilent) {
            showToast(data.message || '配置已成功保存', 'success');
        }
    } catch (error) {
        console.error('保存前台 SEO 配置失败:', error);
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-exclamation-circle text-rose-500 mr-1"></i>保存失败';
        }
        showToast(`保存配置失败: ${error.message}`, 'danger');
    } finally {
        isSeoConfigSaving = false;
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save mr-1"></i> 保存设置';
        }
    }
}


async function loadFrontendLinkCheckConfig() {
    try {
        const response = await fetch('/admin/api/frontend-link-check-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
        if (checkToggle) {
            checkToggle.checked = Boolean(data.enable_link_check !== false);
        }

        const enabledPans = Array.isArray(data.enabled_check_pans) ? data.enabled_check_pans : [];
        const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
        checkBoxes.forEach(cb => {
            cb.checked = enabledPans.includes(cb.value);
        });
        updateEnabledCheckPansCount();
    } catch (error) {
        console.error('加载前台测活配置失败:', error);
        showToast('加载前台测活配置失败，请检查后端日志。', 'danger');
    }
}

async function loadLinkCheckProxyConfig() {
    const input = document.getElementById('linkCheckProxyInput');
    if (!input) return;
    try {
        const response = await fetch('/admin/api/link-check-proxy-config');
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        input.value = data.proxy || '';
    } catch (error) {
        console.error('加载测活代理配置失败:', error);
        showToast(`加载测活代理配置失败: ${error.message}`, 'danger');
    }
}

async function saveLinkCheckProxyConfig() {
    const input = document.getElementById('linkCheckProxyInput');
    if (!input) return;
    try {
        const response = await fetch('/admin/api/link-check-proxy-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ proxy: input.value.trim() })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        input.value = data.proxy || '';
        showToast(data.message || '测活代理配置已保存', 'success');
    } catch (error) {
        console.error('保存测活代理配置失败:', error);
        showToast(`保存测活代理配置失败: ${error.message}`, 'danger');
    }
}

function updateLinkCheckPanelState() {
    const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
    const wrapper = document.getElementById('linkCheckNetdisksWrapper');
    if (!wrapper || !checkToggle) return;

    if (checkToggle.checked) {
        wrapper.classList.remove('hidden');
    } else {
        wrapper.classList.add('hidden');
    }
}

function updateEnabledCheckPansCount() {
    const countEl = document.getElementById('enabledCheckPansCount');
    const toggleBtn = document.getElementById('toggleAllLinkCheckNetdisksButton');
    const checkBoxes = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox'));
    const checkedCount = checkBoxes.filter(cb => cb.checked).length;

    if (countEl) {
        countEl.textContent = checkedCount;
    }
    if (toggleBtn) {
        toggleBtn.textContent = (checkBoxes.length > 0 && checkedCount === checkBoxes.length) ? '取消全选' : '全选';
    }
    updateLinkCheckPanelState();
}

async function selectMainstreamLinkCheckNetdisks() {
    const mainstreamList = ['百度网盘', '夸克网盘', '阿里云盘', 'UC网盘', '迅雷网盘', '光鸭云盘', '悟空网盘', '移动云盘'];
    const mainstreamSet = new Set(mainstreamList);
    const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
    checkBoxes.forEach(cb => {
        cb.checked = mainstreamSet.has(cb.value);
    });
    await saveFrontendLinkCheckConfig();
}

async function toggleAllLinkCheckNetdisks() {
    const checkBoxes = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox'));
    if (!checkBoxes.length) return;
    const allChecked = checkBoxes.every(cb => cb.checked);
    checkBoxes.forEach(cb => {
        cb.checked = !allChecked;
    });
    await saveFrontendLinkCheckConfig();
}

async function saveFrontendLinkCheckConfig() {
    const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
    const enable_link_check = checkToggle ? checkToggle.checked : true;

    const enabled_check_pans = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox:checked')).map(cb => cb.value);
    updateEnabledCheckPansCount();

    try {
        const response = await fetch('/admin/api/frontend-link-check-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enable_link_check,
                enabled_check_pans,
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '前台测活与过滤配置保存成功', 'success');
        if (data.data && Array.isArray(data.data.enabled_check_pans)) {
            const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
            checkBoxes.forEach(cb => {
                cb.checked = data.data.enabled_check_pans.includes(cb.value);
            });
            updateEnabledCheckPansCount();
        }
    } catch (error) {
        console.error('保存前台测活配置失败:', error);
        showToast(`保存前台测活配置失败: ${error.message}`, 'danger');
        await loadFrontendLinkCheckConfig();
    }
}

function updateEnabledDynamicTransferPansCount() {
    const checkBoxes = document.querySelectorAll('.dynamic-transfer-netdisk-checkbox');
    const countEl = document.getElementById('enabledDynamicTransferPansCount');
    const toggleBtn = document.getElementById('toggleAllDynamicTransferNetdisksButton');
    const checkedCount = Array.from(checkBoxes).filter(cb => cb.checked).length;
    if (countEl) {
        countEl.textContent = String(checkedCount);
    }
    if (toggleBtn) {
        toggleBtn.textContent = (checkBoxes.length > 0 && checkedCount === checkBoxes.length) ? '取消全选' : '全选';
    }
}

async function toggleAllDynamicTransferNetdisks() {
    const checkBoxes = Array.from(document.querySelectorAll('.dynamic-transfer-netdisk-checkbox'));
    if (!checkBoxes.length) return;
    const allChecked = checkBoxes.every(cb => cb.checked);
    checkBoxes.forEach(cb => {
        cb.checked = !allChecked;
    });
    await saveDynamicTransferNetdisksConfig();
}

async function saveDynamicTransferNetdisksConfig() {
    const enabled_netdisks = Array.from(document.querySelectorAll('.dynamic-transfer-netdisk-checkbox:checked')).map(cb => cb.value);
    updateEnabledDynamicTransferPansCount();

    try {
        const response = await fetch('/admin/api/dynamic-transfer-netdisks', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled_netdisks })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '动态转存生效网盘配置保存成功', 'success');
        if (data.data && Array.isArray(data.data.enabled_netdisks)) {
            const checkBoxes = document.querySelectorAll('.dynamic-transfer-netdisk-checkbox');
            checkBoxes.forEach(cb => {
                cb.checked = data.data.enabled_netdisks.includes(cb.value);
            });
            updateEnabledDynamicTransferPansCount();
        }
    } catch (error) {
        console.error('保存动态转存生效网盘配置失败:', error);
        showToast(`保存动态转存生效网盘配置失败: ${error.message}`, 'danger');
        await loadDynamicTransferNetdisksConfig();
    }
}

async function loadDynamicTransferNetdisksConfig() {
    try {
        const response = await fetch('/admin/api/dynamic-transfer-netdisks');
        if (!response.ok) return;
        const data = await response.json();
        if (data.success && Array.isArray(data.enabled_netdisks)) {
            const checkBoxes = document.querySelectorAll('.dynamic-transfer-netdisk-checkbox');
            checkBoxes.forEach(cb => {
                cb.checked = data.enabled_netdisks.includes(cb.value);
            });
            updateEnabledDynamicTransferPansCount();
        }
    } catch (error) {
        console.error('加载动态转存生效网盘配置失败:', error);
    }
}


async function loadTransferTargetDirConfig() {
    try {
        const response = await fetch('/admin/api/transfer-target-dir');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const input = document.getElementById('transferTargetDirInput');
        const badge = document.getElementById('transferTargetDirBadge');
        const dir = (data.target_dir !== undefined && data.target_dir !== null) ? data.target_dir : 'Pan-Relay分享';

        if (input) {
            input.value = dir;
        }
        if (badge) {
            badge.textContent = dir ? dir : '根目录 (/)';
            badge.className = dir ? 'badge badge-info text-xs' : 'badge badge-secondary text-xs';
        }
    } catch (error) {
        console.error('加载转存目标目录配置失败:', error);
    }
}

async function saveTransferTargetDirConfig() {
    const input = document.getElementById('transferTargetDirInput');
    const target_dir = input ? input.value.trim() : 'Pan-Relay分享';

    try {
        const response = await fetch('/admin/api/transfer-target-dir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_dir })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '转存目标目录配置保存成功', 'success');
        await loadTransferTargetDirConfig();
    } catch (error) {
        console.error('保存转存目标目录配置失败:', error);
        showToast(`保存转存目标目录配置失败: ${error.message}`, 'danger');
        await loadTransferTargetDirConfig();
    }
}

async function selectMainstreamFrontendNetdisks() {
    const mainstreamList = ['百度网盘', '夸克网盘', '阿里云盘', 'UC网盘', '迅雷网盘', '光鸭云盘', '悟空网盘', '移动云盘'];
    const mainstreamSet = new Set(mainstreamList);
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    checkboxes.forEach((checkbox) => {
        checkbox.checked = mainstreamSet.has(checkbox.value);
    });
    updateFrontendNetdiskSelectionUI();
    await saveFrontendDisplayNetdisks();
}

async function toggleAllFrontendDisplayNetdisks() {
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    const allChecked = checkboxes.length > 0 && checkboxes.every((checkbox) => checkbox.checked);
    checkboxes.forEach((checkbox) => {
        checkbox.checked = !allChecked;
    });
    updateFrontendNetdiskSelectionUI();
    await saveFrontendDisplayNetdisks();
}

async function loadFrontendDisplayNetdisks() {
    try {
        const response = await fetch('/admin/api/frontend-display-netdisks');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const enabledSet = new Set(data.enabled_netdisks || []);
        getFrontendDisplayNetdiskCheckboxes().forEach((checkbox) => {
            checkbox.checked = enabledSet.has(checkbox.value);
        });
        updateFrontendNetdiskSelectionUI();
    } catch (error) {
        console.error('加载前端显示网盘配置失败:', error);
        showToast('加载前端显示网盘配置失败，请检查后端日志。', 'danger');
    }
}

async function saveFrontendDisplayNetdisks() {
    const enabledNetdisks = getFrontendDisplayNetdiskCheckboxes()
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value);

    if (enabledNetdisks.length === 0) {
        showToast('前端显示网盘至少需要保留一个。', 'warning');
        await loadFrontendDisplayNetdisks();
        return;
    }

    try {
        const response = await fetch('/admin/api/frontend-display-netdisks', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled_netdisks: enabledNetdisks })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message, 'success');
    } catch (error) {
        console.error('保存前端显示网盘配置失败:', error);
        showToast(`保存前端显示网盘配置失败: ${error.message}`, 'danger');
        await loadFrontendDisplayNetdisks();
    }
}

async function loadFrontendLinkMode() {
    try {
        const response = await fetch('/admin/api/frontend-link-mode');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const select = document.getElementById('frontendLinkModeSelect');
        if (select) {
            select.value = data.mode || 'copy';
        }
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('加载前端出链模式失败:', error);
        showToast('加载前端出链模式失败，请检查后端日志。', 'danger');
    }
}

async function saveFrontendLinkMode() {
    const select = document.getElementById('frontendLinkModeSelect');
    const mode = select ? select.value : 'copy';

    if (select) select.disabled = true;
    try {
        const response = await fetch('/admin/api/frontend-link-mode', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '出链策略保存成功', 'success');
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('保存前端出链模式失败:', error);
        showToast(`保存前端出链模式失败: ${error.message}`, 'danger');
    } finally {
        if (select) select.disabled = false;
    }
}

async function loadDynamicTransferStatus() {
    try {
        const response = await fetch('/admin/api/credential-config');
        if (!response.ok) return;
        const data = await response.json();
        renderDynamicTransferStatuses(data.dynamic_transfer_statuses, data.dynamic_transfer_summary);
    } catch (error) {
        console.error('加载转存状态失败:', error);
    }
}

async function loadSensitiveWordsConfig() {
    try {
        const response = await fetch('/admin/api/sensitive-words-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const inputToggle = document.getElementById('sensitiveWordsInputToggle');
        const outputToggle = document.getElementById('sensitiveWordsOutputToggle');
        const textarea = document.getElementById('sensitiveWordsTextarea');
        const countEl = document.getElementById('sensitiveWordsCount');

        if (inputToggle) inputToggle.checked = Boolean(config.input_enabled ?? true);
        if (outputToggle) outputToggle.checked = Boolean(config.output_enabled ?? true);

        updateSensitiveWordsBodyUiState(
            Boolean(config.input_enabled ?? true),
            Boolean(config.output_enabled ?? true)
        );

        const words = Array.isArray(config.words) ? config.words : [];
        if (textarea) {
            textarea.value = words.join('\n');
        }
        if (countEl) {
            countEl.textContent = String(words.length);
        }
    } catch (error) {
        console.error('加载敏感词配置失败:', error);
        showToast('加载敏感词配置失败，请检查后端日志。', 'danger');
    }
}

async function saveSensitiveWordsConfig() {
    const inputToggle = document.getElementById('sensitiveWordsInputToggle');
    const outputToggle = document.getElementById('sensitiveWordsOutputToggle');
    const textarea = document.getElementById('sensitiveWordsTextarea');
    const saveBtn = document.getElementById('saveSensitiveWordsConfigBtn');

    const wordsRaw = textarea ? textarea.value : '';
    const words = wordsRaw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    const inputEnabled = inputToggle ? inputToggle.checked : true;
    const outputEnabled = outputToggle ? outputToggle.checked : true;

    updateSensitiveWordsBodyUiState(inputEnabled, outputEnabled);

    const payload = {
        enabled: Boolean(inputEnabled || outputEnabled),
        input_enabled: inputEnabled,
        output_enabled: outputEnabled,
        words: words,
    };

    if (saveBtn) saveBtn.disabled = true;
    try {
        const response = await fetch('/admin/api/sensitive-words-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '敏感词配置保存成功', 'success');
        await loadSensitiveWordsConfig();
    } catch (error) {
        console.error('保存敏感词配置失败:', error);
        showToast(`保存敏感词配置失败: ${error.message}`, 'danger');
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

function bindSensitiveWordsTextareaEvents() {
    const textarea = document.getElementById('sensitiveWordsTextarea');
    const countEl = document.getElementById('sensitiveWordsCount');
    if (textarea && countEl) {
        textarea.addEventListener('input', () => {
            const words = textarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
            countEl.textContent = String(words.length);
        });
    }
}

async function loadSecurityConfig() {
    try {
        const response = await fetch('/admin/api/security-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const config = data.config || {};

        const minLenInput = document.getElementById('secMinKeywordLenInput');
        const rateLimitInput = document.getElementById('secRateLimitInput');
        const maxConcurrentInput = document.getElementById('secMaxConcurrentInput');
        const textarea = document.getElementById('secIpBlacklistTextarea');
        const countEl = document.getElementById('secIpBlacklistCount');

        if (minLenInput) minLenInput.value = config.min_keyword_length ?? 2;
        if (rateLimitInput) rateLimitInput.value = config.rate_limit_per_minute ?? 5;
        if (maxConcurrentInput) maxConcurrentInput.value = config.max_concurrent_searches ?? 1;

        const blacklist = Array.isArray(config.ip_blacklist) ? config.ip_blacklist : [];
        if (textarea) textarea.value = blacklist.join('\n');
        if (countEl) countEl.textContent = String(blacklist.length);
    } catch (error) {
        console.error('加载安全防护配置失败:', error);
    }
}

async function saveSecurityConfig() {
    const minLenInput = document.getElementById('secMinKeywordLenInput');
    const rateLimitInput = document.getElementById('secRateLimitInput');
    const maxConcurrentInput = document.getElementById('secMaxConcurrentInput');
    const textarea = document.getElementById('secIpBlacklistTextarea');
    const countEl = document.getElementById('secIpBlacklistCount');

    const blacklistRaw = textarea ? textarea.value : '';
    const ip_blacklist = blacklistRaw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    if (countEl) countEl.textContent = String(ip_blacklist.length);

    const payload = {
        min_keyword_length: parseInt(minLenInput ? minLenInput.value : 2, 10) || 2,
        rate_limit_per_minute: parseInt(rateLimitInput ? rateLimitInput.value : 5, 10) || 5,
        max_concurrent_searches: parseInt(maxConcurrentInput ? maxConcurrentInput.value : 1, 10) || 1,
        ip_blacklist: ip_blacklist,
    };

    try {
        const response = await fetch('/admin/api/security-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '安全防护配置保存成功', 'success');
        await loadSecurityConfig();
    } catch (error) {
        console.error('保存安全防护配置失败:', error);
        showToast(`保存安全防护配置失败: ${error.message}`, 'danger');
    }
}

async function loadAdFilterConfig() {

    try {
        const response = await fetch('/admin/api/ad-filter-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const globalToggle = document.getElementById('adFilterGlobalToggle');
        const modeSelect = document.getElementById('titleFilterModeSelect');
        const textarea = document.getElementById('adFilterTextarea');
        const countEl = document.getElementById('adFilterWordsCount');

        if (globalToggle) globalToggle.checked = Boolean(config.enabled ?? false);
        if (modeSelect) modeSelect.value = config.title_filter_mode || 'loose';

        updateAdFilterBodyUiState(Boolean(config.enabled ?? false));

        const keywords = Array.isArray(config.keywords) ? config.keywords : [];
        if (textarea) {
            textarea.value = keywords.join('\n');
        }
        if (countEl) {
            countEl.textContent = String(keywords.length);
        }
    } catch (error) {
        console.error('加载广告过滤配置失败:', error);
        showToast('加载广告过滤配置失败，请检查后端日志。', 'danger');
    }
}

async function saveAdFilterConfig() {
    const globalToggle = document.getElementById('adFilterGlobalToggle');
    const modeSelect = document.getElementById('titleFilterModeSelect');
    const textarea = document.getElementById('adFilterTextarea');

    const keywordsRaw = textarea ? textarea.value : '';
    const keywords = keywordsRaw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    const titleFilterMode = modeSelect ? modeSelect.value : 'loose';
    const isAdFilterEnabled = globalToggle ? globalToggle.checked : false;

    updateAdFilterBodyUiState(isAdFilterEnabled);

    const payload = {
        enabled: isAdFilterEnabled,
        title_filter_mode: titleFilterMode,
        keywords: keywords,
    };

    try {
        const response = await fetch('/admin/api/ad-filter-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '广告过滤与标题匹配配置保存成功', 'success');
        await loadAdFilterConfig();
    } catch (error) {
        console.error('保存广告过滤配置失败:', error);
        showToast(`保存广告过滤配置失败: ${error.message}`, 'danger');
    }
}

function bindAdFilterTextareaEvents() {
    const textarea = document.getElementById('adFilterTextarea');
    const countEl = document.getElementById('adFilterWordsCount');
    if (textarea && countEl) {
        textarea.addEventListener('input', () => {
            const keywords = textarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
            countEl.textContent = String(keywords.length);
        });
    }
}

async function loadCustomAdConfig() {
    try {
        const response = await fetch('/admin/api/custom-ad-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const globalToggle = document.getElementById('customAdGlobalToggle');
        const isCustomAdEnabled = Boolean(config.enabled ?? false);
        if (globalToggle) globalToggle.checked = isCustomAdEnabled;

        updateCustomAdUiState(isCustomAdEnabled);

        const adUrls = config.ad_share_urls || {};
        const fieldMap = {
            quark: 'customAdQuarkUrl',
            uc: 'customAdUcUrl',
            baidu: 'customAdBaiduUrl',
            aliyun: 'customAdAliyunUrl',
            xunlei: 'customAdXunleiUrl',
            caiyun: 'customAdCaiyunUrl',
            guangya: 'customAdGuangyaUrl',
            wukong: 'customAdWukongUrl',
        };

        for (const [key, elementId] of Object.entries(fieldMap)) {
            const input = document.getElementById(elementId);
            if (input) {
                input.value = (adUrls[key] || '').trim();
            }
        }
    } catch (error) {
        console.error('加载自定义广告配置失败:', error);
        showToast('加载自定义广告配置失败，请检查后端日志。', 'danger');
    }
}

async function saveCustomAdConfig() {
    const globalToggle = document.getElementById('customAdGlobalToggle');

    const fieldMap = {
        quark: 'customAdQuarkUrl',
        uc: 'customAdUcUrl',
        baidu: 'customAdBaiduUrl',
        aliyun: 'customAdAliyunUrl',
        xunlei: 'customAdXunleiUrl',
        caiyun: 'customAdCaiyunUrl',
        guangya: 'customAdGuangyaUrl',
        wukong: 'customAdWukongUrl',
    };

    const adShareUrls = {};
    for (const [key, elementId] of Object.entries(fieldMap)) {
        const input = document.getElementById(elementId);
        adShareUrls[key] = input ? input.value.trim() : '';
    }

    const isCustomAdEnabled = globalToggle ? globalToggle.checked : false;
    updateCustomAdUiState(isCustomAdEnabled);

    const payload = {
        enabled: isCustomAdEnabled,
        ad_share_urls: adShareUrls,
        ad_share_url: adShareUrls.quark || adShareUrls.uc || '',
    };

    try {
        const response = await fetch('/admin/api/custom-ad-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '8大网盘自定义引流配置保存成功', 'success');
        await loadCustomAdConfig();
    } catch (error) {
        console.error('保存自定义广告配置失败:', error);
        showToast(`保存自定义广告配置失败: ${error.message}`, 'danger');
    }
}


function handleRetentionUnitChange() {
    const unitSelect = document.getElementById('storageRetentionUnitSelect');
    const valueInput = document.getElementById('storageRetentionValueInput');
    const intervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const intervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    if (!unitSelect || !valueInput) return;

    const unit = unitSelect.value;
    if (unit === 'minutes') {
        valueInput.min = '30';
        if (parseInt(valueInput.value || '0', 10) < 30) {
            valueInput.value = '30';
        }
        // 智能对齐：如果保留时长设为了分钟级，且当前扫描周期大于2小时，自动对齐为30分钟
        if (intervalUnitSelect && intervalValueInput) {
            if (intervalUnitSelect.value === 'days' || (intervalUnitSelect.value === 'hours' && parseInt(intervalValueInput.value || '0', 10) > 1)) {
                intervalUnitSelect.value = 'minutes';
                intervalValueInput.value = '30';
                intervalValueInput.min = '15';
            }
        }
    } else {
        valueInput.min = '1';
        if (parseInt(valueInput.value || '0', 10) < 1) {
            valueInput.value = '1';
        }
    }
    saveStorageCleanupConfig();
}

function handleCleanupIntervalUnitChange() {
    const intervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const intervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    if (!intervalUnitSelect || !intervalValueInput) return;

    const unit = intervalUnitSelect.value;
    if (unit === 'minutes') {
        intervalValueInput.min = '15';
        if (parseInt(intervalValueInput.value || '0', 10) < 15) {
            intervalValueInput.value = '30';
        }
    } else {
        intervalValueInput.min = '1';
        if (parseInt(intervalValueInput.value || '0', 10) < 1) {
            intervalValueInput.value = '1';
        }
    }
    saveStorageCleanupConfig();
}

function updateStorageCleanupUiState(enabled) {
    const body = document.getElementById('storageCleanupBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        const inputs = body.querySelectorAll('input:not(#storageCleanupGlobalToggle), select');
        inputs.forEach(input => {
            input.disabled = !enabled;
        });
    }
}

// 广告引流植入总开关 → 置灰 8 大网盘配置区
function updateCustomAdUiState(enabled) {
    const body = document.getElementById('customAdPanelsBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('input, button').forEach(el => { el.disabled = !enabled; });
    }
}

// 广告智能净化开关 → 置灰广告词库区
function updateAdFilterBodyUiState(enabled) {
    const body = document.getElementById('adFilterBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('textarea').forEach(el => { el.disabled = !enabled; });
    }
}

// 搜索输入拦截 + 输出结果净化同时关闭 → 置灰敏感词库区
function updateSensitiveWordsBodyUiState(inputEnabled, outputEnabled) {
    const enabled = inputEnabled || outputEnabled;
    const body = document.getElementById('sensitiveWordsBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('textarea').forEach(el => { el.disabled = !enabled; });
    }
}

async function loadStorageCleanupConfig() {
    try {
        const response = await fetch('/admin/api/storage-cleanup-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const resData = data.data || {};
        const config = resData.config || {};

        const globalToggle = document.getElementById('storageCleanupGlobalToggle');
        const retentionValueInput = document.getElementById('storageRetentionValueInput');
        const retentionUnitSelect = document.getElementById('storageRetentionUnitSelect');
        const retentionDaysInput = document.getElementById('storageRetentionDaysInput');
        const cleanupIntervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
        const cleanupIntervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
        const cleanupIntervalInput = document.getElementById('storageCleanupIntervalInput');
        const expiredCountEl = document.getElementById('expiredResourcesCount');

        const isEnabled = Boolean(config.enabled ?? true);
        if (globalToggle) globalToggle.checked = isEnabled;

        updateStorageCleanupUiState(isEnabled);

        if (retentionUnitSelect) {
            retentionUnitSelect.value = config.retention_unit || 'days';
        }
        if (retentionValueInput) {
            const val = config.retention_value ?? config.retention_days ?? 15;
            retentionValueInput.value = val;
            if (config.retention_unit === 'minutes') {
                retentionValueInput.min = '30';
            } else {
                retentionValueInput.min = '1';
            }
        }
        if (retentionDaysInput) {
            retentionDaysInput.value = config.retention_days || 15;
        }

        if (cleanupIntervalUnitSelect) {
            cleanupIntervalUnitSelect.value = config.cleanup_interval_unit || 'hours';
        }
        if (cleanupIntervalValueInput) {
            const intervalVal = config.cleanup_interval_value ?? config.auto_cleanup_interval_hours ?? 12;
            cleanupIntervalValueInput.value = intervalVal;
            if (config.cleanup_interval_unit === 'minutes') {
                cleanupIntervalValueInput.min = '15';
            } else {
                cleanupIntervalValueInput.min = '1';
            }
        }
        if (cleanupIntervalInput) cleanupIntervalInput.value = config.auto_cleanup_interval_hours || 12;

        if (expiredCountEl) {
            expiredCountEl.textContent = String(resData.expired_resources_count ?? 0);
        }
    } catch (error) {
        console.error('加载存储清理配置失败:', error);
        showToast('加载存储清理配置失败，请检查后端日志。', 'danger');
    }
}

async function saveStorageCleanupConfig() {
    const globalToggle = document.getElementById('storageCleanupGlobalToggle');
    const retentionValueInput = document.getElementById('storageRetentionValueInput');
    const retentionUnitSelect = document.getElementById('storageRetentionUnitSelect');
    const retentionDaysInput = document.getElementById('storageRetentionDaysInput');
    const cleanupIntervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    const cleanupIntervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const cleanupIntervalInput = document.getElementById('storageCleanupIntervalInput');

    const unit = retentionUnitSelect?.value || 'days';
    let val = parseInt(retentionValueInput?.value || retentionDaysInput?.value || '15', 10);
    if (unit === 'minutes' && val < 30) {
        val = 30;
        if (retentionValueInput) retentionValueInput.value = '30';
        showToast('为保障访客保存体验与防网盘风控，保留时间最低为 30 分钟。已自动调整为 30 分钟。', 'warning');
    } else if (val < 1) {
        val = 1;
        if (retentionValueInput) retentionValueInput.value = '1';
    }

    const intervalUnit = cleanupIntervalUnitSelect?.value || 'hours';
    let intervalVal = parseInt(cleanupIntervalValueInput?.value || cleanupIntervalInput?.value || '12', 10);
    if (intervalUnit === 'minutes' && intervalVal < 15) {
        intervalVal = 15;
        if (cleanupIntervalValueInput) cleanupIntervalValueInput.value = '15';
        showToast('为保障系统性能与防网盘风控，扫描周期最低为 15 分钟。已自动调整为 15 分钟。', 'warning');
    } else if (intervalVal < 1) {
        intervalVal = 1;
        if (cleanupIntervalValueInput) cleanupIntervalValueInput.value = '1';
    }

    const isEnabled = globalToggle ? globalToggle.checked : true;
    updateStorageCleanupUiState(isEnabled);

    const payload = {
        enabled: isEnabled,
        clean_temp_shares: true,
        clean_old_resources: true,
        retention_unit: unit,
        retention_value: val,
        retention_days: unit === 'days' ? val : Math.max(1, Math.round((unit === 'hours' ? val * 60 : val) / 1440)),
        cleanup_interval_unit: intervalUnit,
        cleanup_interval_value: intervalVal,
        auto_cleanup_interval_hours: intervalUnit === 'hours' ? intervalVal : Math.max(1, Math.round((intervalUnit === 'minutes' ? intervalVal : intervalVal * 1440) / 60)),
    };

    try {
        const response = await fetch('/admin/api/storage-cleanup-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '存储自动清理配置保存成功', 'success');
        await loadStorageCleanupConfig();
    } catch (error) {
        console.error('保存存储清理配置失败:', error);
        showToast(`保存存储清理配置失败: ${error.message}`, 'danger');
    }
}

async function runStorageCleanupNow() {
    const expiredCount = document.getElementById('expiredResourcesCount')?.textContent || '0';
    const confirmPrompt = `确定要立即按当前策略执行全量存储清理吗？系统将自动回收已失效的临时分享并物理删除超过保留期的转存资源（当前检测到约 ${expiredCount} 条超期资源）。此操作不可撤销。`;

    const ok = window.confirmModal
        ? await window.confirmModal({
            title: '执行存储清理确认',
            message: confirmPrompt,
            confirmText: '立即执行',
            cancelText: '取消',
            type: 'danger'
        })
        : true;

    if (!ok) return;

    const runBtn = document.getElementById('runStorageCleanupBtn');
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin text-[10px] mr-1"></i> 清理中...';
    }

    try {
        const response = await fetch('/admin/api/storage-cleanup/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        const res = data.result || {};
        showToast(`清理完成: 临时分享清理 ${res.temp_shares_cleaned || 0} 条，过期转存清理 ${res.resources_cleaned || 0} 条`, 'success');
        await loadStorageCleanupConfig();
    } catch (error) {
        console.error('执行存储清理失败:', error);
        showToast(`执行存储清理失败: ${error.message}`, 'danger');
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="fas fa-trash-alt text-[10px] mr-1"></i> 立即执行清理';
        }
    }
}

function updateApiLivePreview() {
    const scopeEl = document.getElementById('searchScopeSelect');
    const limitEl = document.getElementById('searchApiLimitInput');
    const filterBadEl = document.getElementById('searchApiFilterBadToggle');
    const checkStatusEl = document.getElementById('searchApiCheckStatusToggle');

    const scopeLockEl = document.getElementById('searchScopeLockToggle');
    const limitLockEl = document.getElementById('searchLimitLockToggle');
    const filterBadLockEl = document.getElementById('searchFilterBadLockToggle');
    const checkStatusLockEl = document.getElementById('searchCheckStatusLockToggle');

    const previewEl = document.getElementById('apiDefaultLivePreview');

    if (!previewEl) return;

    const scope = scopeEl ? scopeEl.value : 'all';
    const limit = limitEl ? (limitEl.value || '50') : '50';
    const filterBad = filterBadEl ? filterBadEl.checked : false;
    const checkStatus = checkStatusEl ? checkStatusEl.checked : false;

    const scopeLocked = scopeLockEl ? scopeLockEl.checked : false;
    const limitLocked = limitLockEl ? limitLockEl.checked : false;
    const filterBadLocked = filterBadLockEl ? filterBadLockEl.checked : false;
    const checkStatusLocked = checkStatusLockEl ? checkStatusLockEl.checked : false;

    const origin = window.location.origin || (window.location.protocol + '//' + window.location.host);
    const protocolMatch = origin.match(/^(https?:\/\/)/);
    const protocolStr = protocolMatch ? protocolMatch[1] : 'https://';
    const hostPathStr = origin.replace(/^https?:\/\//, '') + '/api/v1/search';

    const renderParam = (name, val, isLocked, valClassNormal, valClassLocked) => {
        if (isLocked) {
            return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 bg-amber-100/90 text-amber-900 border border-amber-300 rounded-md font-extrabold shadow-2xs transition-all my-0.5" title="防护锁已锁定：外部请求无法强制穿透此参数规则">` +
                `<i class="fas fa-lock text-amber-600 text-[10px]"></i>` +
                `<span class="font-black text-amber-950">${name}</span>` +
                `<span class="text-amber-700 font-bold">=</span>` +
                `<span class="${valClassLocked}">${val}</span>` +
                `</span>`;
        }
        return `<span class="text-indigo-600 font-medium">${name}</span>` +
            `<span class="text-slate-400 font-bold px-0.5">=</span>` +
            `<span class="${valClassNormal}">${val}</span>`;
    };

    const scopeHtml = renderParam('scope', scope, scopeLocked, 'text-teal-700 font-medium', 'text-teal-800 font-black');
    const limitHtml = renderParam('limit', limit, limitLocked, 'text-blue-700 font-medium', 'text-blue-800 font-black');

    previewEl.innerHTML = `<span class="px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 font-bold text-xs me-2 border border-sky-200">GET</span>` +
        `<span class="text-emerald-600 font-semibold">${protocolStr}</span>` +
        `<span class="text-slate-900 font-bold me-0.5">${hostPathStr}</span>` +
        `<span class="text-amber-600 font-bold">?</span>` +
        `<span class="text-indigo-600 font-medium">keyword</span><span class="text-slate-400 font-bold px-0.5">=</span><span class="text-amber-700 font-medium bg-amber-50 px-1 py-0.5 rounded border border-amber-200/60 me-0.5">{kw}</span>` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${scopeHtml}` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${limitHtml}`;
}

async function loadApiModeConfig() {
    try {
        const response = await fetch('/admin/api/api-mode-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const cfg = data.config || {};

        const apiOnlyToggle = document.getElementById('apiOnlyToggle');
        const apiOnlyBadge = document.getElementById('apiOnlyBadge');
        const enableFrontendToggle = document.getElementById('enableFrontendToggle');
        const enableFrontendBadge = document.getElementById('enableFrontendBadge');
        const searchScopeSelect = document.getElementById('searchScopeSelect');
        const searchScopeBadge = document.getElementById('searchScopeBadge');
        const searchApiLimitInput = document.getElementById('searchApiLimitInput');

        const searchScopeLockToggle = document.getElementById('searchScopeLockToggle');
        const searchLimitLockToggle = document.getElementById('searchLimitLockToggle');

        const transferApiKeyInput = document.getElementById('transferApiKeyInput');
        const transferApiKeyBadge = document.getElementById('transferApiKeyBadge');
        const kpiApiMode = document.getElementById('kpiApiMode');

        if (apiOnlyToggle) apiOnlyToggle.checked = Boolean(cfg.api_only);
        if (apiOnlyBadge) {
            apiOnlyBadge.textContent = cfg.api_only ? '已开启' : '未开启';
            apiOnlyBadge.className = cfg.api_only ? 'badge badge-warning text-xs' : 'badge badge-secondary text-xs';
        }

        if (enableFrontendToggle) {
            enableFrontendToggle.checked = Boolean(cfg.enable_frontend);
            updateFrontendConfigPanelsState(Boolean(cfg.enable_frontend));
        }
        if (enableFrontendBadge) {
            enableFrontendBadge.textContent = cfg.enable_frontend ? '已开启' : '已禁用';
            enableFrontendBadge.className = cfg.enable_frontend ? 'badge badge-success text-xs' : 'badge badge-secondary text-xs';
        }

        if (searchScopeSelect) searchScopeSelect.value = cfg.search_scope || 'all';
        if (searchScopeBadge) {
            searchScopeBadge.textContent = (cfg.search_scope === 'all') ? '全网并发聚合' : '仅站长收益库';
            searchScopeBadge.className = (cfg.search_scope === 'all') ? 'badge badge-warning text-xs' : 'badge badge-info text-xs';
        }

        if (searchApiLimitInput) searchApiLimitInput.value = String(cfg.search_limit || 50);

        if (searchScopeLockToggle) searchScopeLockToggle.checked = Boolean(cfg.search_scope_lock);
        if (searchLimitLockToggle) searchLimitLockToggle.checked = Boolean(cfg.search_limit_lock);

        if (transferApiKeyInput) transferApiKeyInput.value = cfg.transfer_api_key || '';
        if (transferApiKeyBadge) {
            const hasKey = Boolean((cfg.transfer_api_key || '').trim());
            transferApiKeyBadge.textContent = hasKey ? '受密钥保护' : '公开调用';
            transferApiKeyBadge.className = hasKey ? 'badge badge-success text-xs' : 'badge badge-secondary text-xs';
        }

        if (kpiApiMode) {
            kpiApiMode.textContent = cfg.api_only ? 'API 无头' : '标准 Web';
            kpiApiMode.style.color = cfg.api_only ? 'var(--admin-warning-text)' : 'var(--admin-success-text)';
        }

        updateApiLivePreview();
    } catch (error) {
        console.error('加载 API 模式配置失败:', error);
    }
}

async function saveApiModeConfig() {
    const apiOnlyToggle = document.getElementById('apiOnlyToggle');
    const enableFrontendToggle = document.getElementById('enableFrontendToggle');
    const searchScopeSelect = document.getElementById('searchScopeSelect');
    const searchApiLimitInput = document.getElementById('searchApiLimitInput');

    const searchScopeLockToggle = document.getElementById('searchScopeLockToggle');
    const searchLimitLockToggle = document.getElementById('searchLimitLockToggle');

    const transferApiKeyInput = document.getElementById('transferApiKeyInput');

    const enabledFrontend = enableFrontendToggle ? enableFrontendToggle.checked : true;
    updateFrontendConfigPanelsState(enabledFrontend);
    updateApiLivePreview();

    const payload = {
        api_only: apiOnlyToggle ? apiOnlyToggle.checked : false,
        enable_frontend: enabledFrontend,
        search_scope: searchScopeSelect ? searchScopeSelect.value : 'all',
        search_limit: searchApiLimitInput ? (parseInt(searchApiLimitInput.value, 10) || 50) : 50,
        search_scope_lock: searchScopeLockToggle ? searchScopeLockToggle.checked : false,
        search_limit_lock: searchLimitLockToggle ? searchLimitLockToggle.checked : false,
        transfer_api_key: transferApiKeyInput ? transferApiKeyInput.value.trim() : '',
    };

    try {
        const response = await fetch('/admin/api/api-mode-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || 'API 模式配置保存成功', 'success');
        await loadApiModeConfig();
    } catch (error) {
        console.error('保存 API 模式配置失败:', error);
        showToast(`保存 API 模式配置失败: ${error.message}`, 'danger');
        await loadApiModeConfig();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindSystemTabEvents();
    bindFrontendNetdiskCheckboxEvents();
    bindFrontendLinkModeEvents();
    bindSensitiveWordsTextareaEvents();
    bindAdFilterTextareaEvents();
    const enableFrontendToggle = document.getElementById('enableFrontendToggle');
    if (enableFrontendToggle) {
        updateFrontendConfigPanelsState(enableFrontendToggle.checked);
    }
    loadApiModeConfig();
    loadPublicSearchApiConfig();
    loadAllowExcelDownloadConfig();
    loadPcQrCodeConfig();
    loadFrontendGithubConfig();
    loadFrontendCopyrightText();
    loadFrontendDisclaimerText();
    loadFrontendSeoConfig();
    loadFrontendLinkCheckConfig();
    loadLinkCheckProxyConfig();
    loadTransferTargetDirConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadDynamicTransferNetdisksConfig();
    loadSensitiveWordsConfig();
    loadSecurityConfig();
    loadAdFilterConfig();

    loadCustomAdConfig();
    loadStorageCleanupConfig();
    loadDynamicTransferStatus();
    updateDynamicTransferStatusVisibility();

    [
        'searchScopeSelect', 'searchApiLimitInput', 'searchApiFilterBadToggle', 'searchApiCheckStatusToggle',
        'searchScopeLockToggle', 'searchLimitLockToggle', 'searchFilterBadLockToggle', 'searchCheckStatusLockToggle'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateApiLivePreview);
            el.addEventListener('input', updateApiLivePreview);
        }
    });

    const transferApiKeyInput = document.getElementById('transferApiKeyInput');
    if (transferApiKeyInput) {
        transferApiKeyInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveApiModeConfig();
            }
        });
    }

    const transferTargetDirInput = document.getElementById('transferTargetDirInput');
    if (transferTargetDirInput) {
        transferTargetDirInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveTransferTargetDirConfig();
            }
        });
    }

    const customAdShareUrlInput = document.getElementById('customAdShareUrlInput');
    if (customAdShareUrlInput) {
        customAdShareUrlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveCustomAdConfig();
            }
        });
    }

});
