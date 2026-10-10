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
        badge.className = `badge ${isView ? 'badge-warning' : 'badge-info'} text-[10px]`;
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

function switchSystemTab(target, updateHash = true) {
    const validTabs = ['storage', 'ads', 'security', 'accounts', 'strategy', 'api', 'frontend'];
    const normalized = validTabs.includes(target) ? target : 'storage';
    try {
        localStorage.setItem('panrelay_system_tab', normalized);
    } catch (e) {}

    const tabBtns = document.querySelectorAll('[data-system-tab-target]');
    if (tabBtns.length === 0) return;

    tabBtns.forEach((b) => {
        b.classList.toggle('is-active', b.getAttribute('data-system-tab-target') === normalized);
    });
    document.querySelectorAll('.system-tab-pane').forEach((pane) => {
        pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
    });

    const container = document.getElementById('systemConfigContainer');
    if (container) {
        if (normalized === 'accounts') {
            container.classList.remove('max-w-4xl');
            container.classList.add('max-w-7xl');
        } else {
            container.classList.remove('max-w-7xl');
            container.classList.add('max-w-4xl');
        }
    }

    if (normalized === 'accounts' && typeof loadCloudAccounts === 'function') {
        loadCloudAccounts();
    }

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
    } catch (e) {}
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
            badge.className = data.enabled ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
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
            badge.className = data.enabled ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
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
    } catch (error) {
        console.error('加载前台 GitHub 标识配置失败:', error);
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
            badge.className = dir ? 'badge badge-info text-[10px]' : 'badge badge-secondary text-[10px]';
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

    previewEl.innerHTML = `<span class="px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 font-bold text-[11px] me-2 border border-sky-200">GET</span>` +
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
            apiOnlyBadge.className = cfg.api_only ? 'badge badge-warning text-[10px]' : 'badge badge-secondary text-[10px]';
        }

        if (enableFrontendToggle) {
            enableFrontendToggle.checked = Boolean(cfg.enable_frontend);
            updateFrontendConfigPanelsState(Boolean(cfg.enable_frontend));
        }
        if (enableFrontendBadge) {
            enableFrontendBadge.textContent = cfg.enable_frontend ? '已开启' : '已禁用';
            enableFrontendBadge.className = cfg.enable_frontend ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
        }

        if (searchScopeSelect) searchScopeSelect.value = cfg.search_scope || 'all';
        if (searchScopeBadge) {
            searchScopeBadge.textContent = (cfg.search_scope === 'all') ? '全网并发聚合' : '仅站长收益库';
            searchScopeBadge.className = (cfg.search_scope === 'all') ? 'badge badge-warning text-[10px]' : 'badge badge-info text-[10px]';
        }

        if (searchApiLimitInput) searchApiLimitInput.value = String(cfg.search_limit || 50);

        if (searchScopeLockToggle) searchScopeLockToggle.checked = Boolean(cfg.search_scope_lock);
        if (searchLimitLockToggle) searchLimitLockToggle.checked = Boolean(cfg.search_limit_lock);

        if (transferApiKeyInput) transferApiKeyInput.value = cfg.transfer_api_key || '';
        if (transferApiKeyBadge) {
            const hasKey = Boolean((cfg.transfer_api_key || '').trim());
            transferApiKeyBadge.textContent = hasKey ? '受密钥保护' : '公开调用';
            transferApiKeyBadge.className = hasKey ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
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
    loadFrontendLinkCheckConfig();
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

    initAccountPoolEvents();
});


// ==================== 网盘多账号池管理 ====================

let _currentCloudFilter = 'ALL';
let _accountsData = [];

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function loadCloudAccounts(cloud = null) {
    const tableBody = document.getElementById('accountsTableBody');
    if (!tableBody) return;

    if (cloud !== null) {
        _currentCloudFilter = cloud;
    }

    try {
        const url = _currentCloudFilter && _currentCloudFilter !== 'ALL'
            ? `/admin/api/accounts?cloud_name=${encodeURIComponent(_currentCloudFilter)}`
            : '/admin/api/accounts';
        const res = await fetch(url, { credentials: 'same-origin' });
        const data = await res.json();

        if (!data.success) {
            tableBody.innerHTML = `<tr><td colspan="9" class="p-8 text-center text-red-500 font-medium"><i class="fas fa-triangle-exclamation mr-2"></i>加载失败: ${data.message || '未知错误'}</td></tr>`;
            return;
        }

        _accountsData = data.accounts || [];
        const summary = data.summary || {};

        // 更新头部 KPI
        const totalEl = document.getElementById('statTotalAccounts');
        const validEl = document.getElementById('statValidAccounts');
        const storageEl = document.getElementById('statStorageSpace');
        const transfersEl = document.getElementById('statTransfers');
        const badgeEl = document.getElementById('accountsTabBadge');

        if (totalEl) totalEl.textContent = summary.total_count || 0;
        if (validEl) validEl.textContent = `${summary.valid_count || 0} / ${summary.total_count || 0}`;
        if (badgeEl) badgeEl.textContent = summary.total_count || 0;

        if (storageEl) {
            const used = formatBytes(summary.used_space_bytes || 0);
            const total = summary.total_space_bytes ? formatBytes(summary.total_space_bytes) : '不限量';
            storageEl.textContent = `${used} / ${total}`;
        }

        const totalTransfers = _accountsData.reduce((acc, cur) => acc + (cur.transferred_count || 0), 0);
        if (transfersEl) transfersEl.textContent = `${totalTransfers} 次`;

        renderAccountsTable(_accountsData);
    } catch (err) {
        console.error('加载账号池异常:', err);
        tableBody.innerHTML = `<tr><td colspan="9" class="p-8 text-center text-red-500"><i class="fas fa-circle-exclamation mr-2"></i>网络请求异常</td></tr>`;
    }
}

function renderStorageRingHtml(acc) {
    const unsupportedSpaceClouds = ['悟空网盘', '移动云盘'];
    if (unsupportedSpaceClouds.includes(acc.cloud_name)) {
        return `
            <div class="flex items-center gap-2.5">
                <div class="relative inline-flex items-center justify-center flex-shrink-0" style="width: 34px; height: 34px;">
                    <svg class="w-full h-full" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="14.5" fill="none" class="stroke-slate-200 dark:stroke-slate-700" stroke-width="2.8" stroke-dasharray="3 3"></circle>
                    </svg>
                    <span class="absolute text-[9px] font-medium text-slate-400">--</span>
                </div>
                <div class="flex flex-col text-[11px] leading-tight">
                    <span class="text-[11px] font-medium text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-700/60 px-2 py-0.5 rounded-md w-max">不支持容量</span>
                </div>
            </div>
        `;
    }

    if (!acc.total_space_bytes || acc.total_space_bytes <= 0) {
        return `
            <div class="flex items-center gap-2.5">
                <div class="relative inline-flex items-center justify-center flex-shrink-0" style="width: 34px; height: 34px;">
                    <svg class="w-full h-full" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="14.5" fill="none" class="stroke-slate-200 dark:stroke-slate-700" stroke-width="2.8"></circle>
                    </svg>
                    <span class="absolute text-[9px] font-medium text-slate-400">--</span>
                </div>
                <div class="flex flex-col text-[11px] leading-tight">
                    <span class="text-slate-400">未探测</span>
                </div>
            </div>
        `;
    }

    const usedStr = formatBytes(acc.used_space_bytes || 0);
    const totalStr = formatBytes(acc.total_space_bytes);
    const pct = Math.min(100, Math.round(((acc.used_space_bytes || 0) / acc.total_space_bytes) * 100));

    // SVG 圆环周长: 2 * Math.PI * 14.5 ≈ 91.1
    const circumference = 91.1;
    const offset = Math.max(0, (circumference - (pct / 100) * circumference)).toFixed(1);

    let strokeColor = '#4f46e5';
    let textColor = 'text-indigo-600 dark:text-indigo-400';
    if (pct > 90) {
        strokeColor = '#f43f5e';
        textColor = 'text-rose-600 dark:text-rose-400';
    } else if (pct > 75) {
        strokeColor = '#f59e0b';
        textColor = 'text-amber-600 dark:text-amber-400';
    }

    return `
        <div class="flex items-center gap-2.5">
            <div class="relative inline-flex items-center justify-center flex-shrink-0" style="width: 36px; height: 36px;">
                <svg class="w-full h-full -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="14.5" fill="none" class="stroke-slate-100 dark:stroke-slate-700" stroke-width="3"></circle>
                    <circle cx="18" cy="18" r="14.5" fill="none" stroke="${strokeColor}" stroke-width="3" stroke-dasharray="91.1" stroke-dashoffset="${offset}" stroke-linecap="round" class="transition-all duration-300"></circle>
                </svg>
                <span class="absolute text-[9px] font-bold ${textColor}">${pct}%</span>
            </div>
            <div class="flex flex-col text-[11px] leading-tight">
                <span class="font-semibold text-slate-700 dark:text-slate-200">${usedStr}</span>
                <span class="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">总 ${totalStr}</span>
            </div>
        </div>
    `;
}

function renderAccountsTable(accounts) {
    const tableBody = document.getElementById('accountsTableBody');
    if (!tableBody) return;

    if (!accounts || accounts.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="p-12 text-center text-slate-400 dark:text-slate-500">
                    <div class="flex flex-col items-center justify-center gap-2">
                        <i class="fas fa-folder-open text-3xl text-slate-300 dark:text-slate-600 mb-1"></i>
                        <span class="text-sm font-medium">暂无网盘账号</span>
                        <span class="text-xs text-slate-400">点击右上角「添加网盘账号」按钮快速接入账号</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const cloudBadgeMap = {
        '夸克网盘': 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-300',
        '百度网盘': 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300',
        '阿里云盘': 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/40 dark:text-amber-300',
        'UC网盘': 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/40 dark:text-orange-300',
        '迅雷网盘': 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/40 dark:text-sky-300',
        '光鸭云盘': 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-900/40 dark:text-rose-300',
        '悟空网盘': 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/40 dark:text-purple-300',
        '移动云盘': 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300',
    };

    let html = '';
    accounts.forEach(acc => {
        const cloudClass = cloudBadgeMap[acc.cloud_name] || 'bg-slate-50 text-slate-700 border-slate-200';
        const isValid = acc.is_valid === 1;
        const isActive = acc.is_active === 1;

        // 圆形环形空间容量展示
        const spaceHtml = renderStorageRingHtml(acc);

        // 状态徽章
        let statusBadge = '';
        if (!isActive) {
            statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400">已停用</span>';
        } else if (isValid) {
            statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400 flex items-center gap-1 w-max"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>正常就绪</span>';
        } else {
            const reason = acc.invalid_reason ? escapeHtml(acc.invalid_reason) : '凭据失效';
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400 flex items-center gap-1 w-max cursor-help" title="${reason}"><span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>失效</span>`;
        }

        html += `
            <tr class="hover:bg-slate-50/60 dark:hover:bg-slate-700/30 transition-colors">
                <td class="p-3.5 pl-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-1 text-[11px] font-semibold rounded-lg border ${cloudClass} shadow-2xs">
                        ${escapeHtml(acc.cloud_name)}
                    </span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <div class="font-bold text-slate-800 dark:text-white text-xs">${escapeHtml(acc.account_name)}</div>
                </td>
                <td class="p-3.5 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                    ${acc.username ? `<span class="font-medium text-xs">${escapeHtml(acc.username)}</span>` : '<span class="text-slate-400">--</span>'}
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <div class="flex items-center gap-2">
                        ${statusBadge}
                        <label class="plugin-switch" title="切换账号启用/停用">
                            <input type="checkbox" ${isActive ? 'checked' : ''} onchange="toggleAccountActive(${acc.id}, this.checked)">
                            <span class="plugin-switch-slider"></span>
                        </label>
                    </div>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    ${spaceHtml}
                </td>
                <td class="p-3.5 text-slate-500 whitespace-nowrap">
                    <div class="flex flex-col text-[11px] gap-0.5">
                        <span>优先级: <strong class="text-indigo-600 dark:text-indigo-400">${acc.priority}</strong></span>
                        <span>权重: <strong>${acc.weight}</strong></span>
                    </div>
                </td>
                <td class="p-3.5 text-center font-bold text-slate-700 dark:text-slate-200 whitespace-nowrap">
                    ${acc.transferred_count || 0}
                </td>
                <td class="p-3.5 text-slate-400 text-[11px] whitespace-nowrap">
                    <div>用: ${acc.last_used_at ? acc.last_used_at.substring(5, 16) : '未调用'}</div>
                    <div>保: ${acc.last_keepalive_at ? acc.last_keepalive_at.substring(5, 16) : '未保活'}</div>
                </td>
                <td class="p-3.5 pr-4 text-right account-table-sticky-col whitespace-nowrap">
                    <div class="flex items-center justify-end gap-1.5">
                        <button class="btn btn-outline-secondary btn-xs" onclick="testAccount(${acc.id})" title="测试连通性与空间">
                            <i class="fas fa-stethoscope text-indigo-500"></i>
                        </button>
                        <button class="btn btn-outline-secondary btn-xs" onclick="openEditAccountModal(${acc.id})" title="编辑账号">
                            <i class="fas fa-pen-to-square"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-xs" onclick="deleteAccount(${acc.id})" title="删除账号">
                            <i class="fas fa-trash-can text-red-500"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function openAddAccountModal() {
    const modal = document.getElementById('accountModal');
    const form = document.getElementById('accountForm');
    const title = document.getElementById('accountModalTitle');
    const idInput = document.getElementById('modalAccountId');
    const cloudSelect = document.getElementById('modalCloudName');

    if (!modal || !form) return;

    form.reset();
    idInput.value = '';
    title.innerHTML = '<i class="fas fa-user-plus text-indigo-600"></i> 添加网盘账号';

    if (_currentCloudFilter && _currentCloudFilter !== 'ALL' && cloudSelect) {
        cloudSelect.value = _currentCloudFilter;
    }

    modal.style.display = 'flex';
}

function openEditAccountModal(accountId) {
    const account = _accountsData.find(a => a.id === accountId);
    if (!account) return;

    const modal = document.getElementById('accountModal');
    const title = document.getElementById('accountModalTitle');
    const idInput = document.getElementById('modalAccountId');
    const cloudSelect = document.getElementById('modalCloudName');
    const nameInput = document.getElementById('modalAccountName');
    const credInput = document.getElementById('modalCredential');
    const priorityInput = document.getElementById('modalPriority');
    const weightInput = document.getElementById('modalWeight');
    const activeCheck = document.getElementById('modalIsActive');

    if (!modal) return;

    idInput.value = account.id;
    title.innerHTML = '<i class="fas fa-user-pen text-indigo-600"></i> 编辑网盘账号';
    if (cloudSelect) cloudSelect.value = account.cloud_name;
    if (nameInput) nameInput.value = account.account_name;
    if (credInput) credInput.value = account.credential;
    if (priorityInput) priorityInput.value = account.priority;
    if (weightInput) weightInput.value = account.weight;
    if (activeCheck) activeCheck.checked = account.is_active === 1;

    modal.style.display = 'flex';
}

function closeAccountModal() {
    const modal = document.getElementById('accountModal');
    if (modal) modal.style.display = 'none';
}

async function handleAccountFormSubmit(e) {
    e.preventDefault();

    const id = document.getElementById('modalAccountId').value;
    const cloud_name = document.getElementById('modalCloudName').value;
    const account_name = document.getElementById('modalAccountName').value.trim();
    const credential = document.getElementById('modalCredential').value.trim();
    const priority = parseInt(document.getElementById('modalPriority').value) || 0;
    const weight = parseInt(document.getElementById('modalWeight').value) || 10;
    const is_active = document.getElementById('modalIsActive').checked ? 1 : 0;
    const auto_test = document.getElementById('modalAutoTest').checked;

    const submitBtn = document.getElementById('btnSubmitAccountModal');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 保存中...';
    }

    try {
        const payload = {
            cloud_name,
            account_name,
            credential,
            priority,
            weight,
            is_active,
            auto_test,
        };

        const isEdit = Boolean(id);
        const url = isEdit ? `/admin/api/accounts/${id}` : '/admin/api/accounts';
        const method = isEdit ? 'PUT' : 'POST';

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        });
        const data = await res.json();

        if (data.success) {
            if (typeof showToast === 'function') {
                showToast(data.message || '操作成功', 'success');
            }
            closeAccountModal();
            loadCloudAccounts();
        } else {
            showToast(data.message || '保存失败: 未知错误', 'danger');
        }
    } catch (err) {
        console.error('保存账号异常:', err);
        showToast('网络请求异常: ' + err.message, 'danger');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check"></i> 保存账号';
        }
    }
}

async function toggleAccountActive(accountId, isActive) {
    try {
        const res = await fetch(`/admin/api/accounts/${accountId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: isActive ? 1 : 0 }),
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast(`账号已${isActive ? '启用' : '停用'}`, 'info');
            loadCloudAccounts();
        } else {
            showToast(data.message || '切换账号状态失败', 'danger');
        }
    } catch (err) {
        console.error('切换账号状态异常:', err);
        showToast('切换账号状态异常: ' + err.message, 'danger');
    }
}

async function testAccount(accountId) {
    showToast('正在向网盘发起健康自检与容量探测...', 'info');
    try {
        const res = await fetch(`/admin/api/accounts/${accountId}/test`, {
            method: 'POST',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || '测试通过，账号状态健康', 'success');
        } else {
            showToast(data.message || '自测未通过: 连接失败', 'warning');
        }
        loadCloudAccounts();
    } catch (err) {
        showToast('自测请求异常: ' + err.message, 'danger');
    }
}

async function deleteAccount(accountId) {
    const acc = _accountsData.find(a => a.id === accountId);
    const name = acc ? acc.account_name : `ID:${accountId}`;
    const cloud = acc ? acc.cloud_name : '网盘';

    const confirmed = window.confirmModal
        ? await window.confirmModal({
            title: '删除网盘账号',
            message: `确定要彻底删除 ${cloud} 账号「${name}」吗？删除后该账号将不再参与任何转存与分流任务。`,
            confirmText: '确认删除',
            cancelText: '取消',
            type: 'danger'
        })
        : true;

    if (!confirmed) return;

    try {
        const res = await fetch(`/admin/api/accounts/${accountId}`, {
            method: 'DELETE',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast('账号已安全删除', 'success');
            loadCloudAccounts();
        } else {
            showToast('删除失败: ' + (data.message || '未知错误'), 'danger');
        }
    } catch (err) {
        showToast('删除请求失败: ' + err.message, 'danger');
    }
}

async function triggerKeepaliveAll() {
    const btn = document.getElementById('btnKeepaliveAccounts');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 续期保活中...';
    }
    showToast('正在遍历网盘账号池执行静默续期与保活...', 'info');
    try {
        const res = await fetch('/admin/api/accounts/keepalive', {
            method: 'POST',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            const r = data.result || {};
            const msg = `续期完成: 检查 ${r.total_checked || 0} 个账号，成功刷新 ${r.refreshed || 0} 个，失败 ${r.failed || 0} 个`;
            showToast(msg, 'success');
            loadCloudAccounts();
        } else {
            showToast('保活失败: ' + (data.message || '未知异常'), 'warning');
        }
    } catch (err) {
        showToast('保活请求异常: ' + err.message, 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-rotate"></i> 一键全盘续期';
        }
    }
}

async function exportAccountsCsv() {
    const cloud = (_currentCloudFilter && _currentCloudFilter !== 'ALL') ? _currentCloudFilter : '';
    const url = cloud ? `/admin/api/accounts/export-csv?cloud_name=${encodeURIComponent(cloud)}` : '/admin/api/accounts/export-csv';
    const btn = document.getElementById('btnExportAccounts');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 导出中...';
    }
    showToast(`正在导出${cloud ? ` [${cloud}] ` : '全部'}网盘账号配置...`, 'info');

    try {
        const res = await fetch(url, { credentials: 'same-origin' });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            showToast(data.message || '导出失败: 服务器异常', 'danger');
            return;
        }

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;

        // 获取或构建文件名
        let filename = '';
        const disposition = res.headers.get('content-disposition');
        if (disposition && disposition.includes('filename*=')) {
            const parts = disposition.split("filename*=");
            if (parts.length > 1) {
                const encName = parts[1].replace(/UTF-8''/i, '').replace(/["']/g, '').trim();
                try {
                    filename = decodeURIComponent(encName);
                } catch (e) {}
            }
        }
        if (!filename && disposition && disposition.includes('filename=')) {
            const match = disposition.match(/filename="?([^";]+)"?/i);
            if (match && match[1]) filename = match[1].trim();
        }
        if (!filename) {
            const nowStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            const filterStr = cloud ? `_${cloud}` : '';
            filename = `网盘账号池${filterStr}_${nowStr}.csv`;
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();

        setTimeout(() => {
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();
        }, 1000);

        showToast('导出成功，文件已开始下载', 'success');
    } catch (err) {
        console.error('导出异常:', err);
        // Fallback: direct window.open
        window.open(url, '_blank');
        showToast('已唤起浏览器下载', 'info');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-file-export"></i> 导出 CSV';
        }
    }
}

let _selectedCsvFile = null;

function openAccountImportModal() {
    const modal = document.getElementById('accountImportModal');
    const form = document.getElementById('accountImportForm');
    const resultDiv = document.getElementById('accountImportResult');
    const fileInput = document.getElementById('accountCsvFileInput');
    const fileNameEl = document.getElementById('accountCsvFileName');
    const iconEl = document.getElementById('accountCsvIcon');

    if (!modal || !form) return;

    form.reset();
    _selectedCsvFile = null;
    if (fileInput) fileInput.value = '';
    if (fileNameEl) fileNameEl.textContent = '点击选择或将 CSV 文件拖拽至此处';
    if (iconEl) iconEl.className = 'fas fa-cloud-arrow-up text-3xl text-indigo-500 mb-2 block';
    if (resultDiv) {
        resultDiv.className = 'hidden';
        resultDiv.innerHTML = '';
    }

    modal.style.display = 'flex';
}

function closeAccountImportModal() {
    const modal = document.getElementById('accountImportModal');
    if (modal) modal.style.display = 'none';
}

function handleCsvFileSelect(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv') && file.type !== 'text/csv') {
        showToast('请选择 .csv 格式的文件', 'warning');
        return;
    }
    _selectedCsvFile = file;
    const fileNameEl = document.getElementById('accountCsvFileName');
    const iconEl = document.getElementById('accountCsvIcon');
    if (fileNameEl) {
        fileNameEl.innerHTML = `<span class="text-indigo-600 dark:text-indigo-400 font-semibold">${escapeHtml(file.name)}</span> <span class="text-slate-400 text-[11px]">(${formatBytes(file.size)})</span>`;
    }
    if (iconEl) {
        iconEl.className = 'fas fa-file-csv text-3xl text-emerald-500 mb-2 block';
    }
}

async function handleAccountImportSubmit(e) {
    e.preventDefault();
    if (!_selectedCsvFile) {
        showToast('请先选择要导入的 CSV 文件', 'warning');
        return;
    }

    const autoTest = document.getElementById('accountImportAutoTest')?.checked ?? true;
    const submitBtn = document.getElementById('btnSubmitAccountImport');
    const resultDiv = document.getElementById('accountImportResult');

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 正在导入解析...';
    }
    if (resultDiv) {
        resultDiv.className = 'hidden';
        resultDiv.innerHTML = '';
    }

    const formData = new FormData();
    formData.append('file', _selectedCsvFile);
    formData.append('auto_test', autoTest ? 'true' : 'false');

    try {
        const res = await fetch('/admin/api/accounts/import-csv', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || '导入完成', 'success');
            loadCloudAccounts();

            if (data.errors && data.errors.length > 0) {
                if (resultDiv) {
                    resultDiv.className = 'p-3 rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20 text-xs max-h-40 overflow-y-auto space-y-1';
                    let errHtml = `<div class="font-bold text-amber-800 dark:text-amber-400 flex items-center gap-1.5"><i class="fas fa-triangle-exclamation"></i> 导入报告：成功 ${data.imported} 个，失败/跳过 ${data.failed} 条</div><ul class="list-disc pl-4 space-y-0.5 text-slate-600 dark:text-slate-400">`;
                    data.errors.forEach(err => {
                        errHtml += `<li>第 ${err.row} 行: ${escapeHtml(err.error)}</li>`;
                    });
                    errHtml += '</ul>';
                    resultDiv.innerHTML = errHtml;
                }
            } else {
                setTimeout(() => {
                    closeAccountImportModal();
                }, 800);
            }
        } else {
            showToast(data.message || '导入失败', 'danger');
            if (resultDiv) {
                resultDiv.className = 'p-3 rounded-xl border border-red-200 bg-red-50 dark:border-red-900/40 dark:bg-red-950/20 text-xs max-h-40 overflow-y-auto space-y-1';
                let errHtml = `<div class="font-bold text-red-700 dark:text-red-400"><i class="fas fa-circle-xmark mr-1"></i> ${escapeHtml(data.message || '导入失败')}</div>`;
                if (data.errors && data.errors.length > 0) {
                    errHtml += '<ul class="list-disc pl-4 space-y-0.5 text-slate-600 dark:text-slate-400 mt-1">';
                    data.errors.forEach(err => {
                        errHtml += `<li>第 ${err.row} 行: ${escapeHtml(err.error)}</li>`;
                    });
                    errHtml += '</ul>';
                }
                resultDiv.innerHTML = errHtml;
            }
        }
    } catch (err) {
        console.error('导入账号异常:', err);
        showToast('上传请求异常: ' + err.message, 'danger');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-upload mr-1"></i> 开始导入';
        }
    }
}

function initAccountCsvDropZone() {
    const dropZone = document.getElementById('accountCsvDropZone');
    const fileInput = document.getElementById('accountCsvFileInput');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleCsvFileSelect(e.target.files[0]);
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/30');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/30');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt?.files;
        if (files && files.length > 0) {
            handleCsvFileSelect(files[0]);
        }
    });
}

function initAccountPoolEvents() {
    const btnAdd = document.getElementById('btnAddAccount');
    if (btnAdd) btnAdd.addEventListener('click', openAddAccountModal);

    const btnClose = document.getElementById('btnCloseAccountModal');
    if (btnClose) btnClose.addEventListener('click', closeAccountModal);

    const btnCancel = document.getElementById('btnCancelAccountModal');
    if (btnCancel) btnCancel.addEventListener('click', closeAccountModal);

    const modal = document.getElementById('accountModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeAccountModal();
            }
        });
    }

    const form = document.getElementById('accountForm');
    if (form) form.addEventListener('submit', handleAccountFormSubmit);

    const btnKeepalive = document.getElementById('btnKeepaliveAccounts');
    if (btnKeepalive) btnKeepalive.addEventListener('click', triggerKeepaliveAll);

    // 导出与导入 CSV 按钮
    const btnExport = document.getElementById('btnExportAccounts');
    if (btnExport) btnExport.addEventListener('click', exportAccountsCsv);

    const btnImport = document.getElementById('btnImportAccounts');
    if (btnImport) btnImport.addEventListener('click', openAccountImportModal);

    const btnCloseImport = document.getElementById('btnCloseAccountImportModal');
    if (btnCloseImport) btnCloseImport.addEventListener('click', closeAccountImportModal);

    const btnCancelImport = document.getElementById('btnCancelAccountImportModal');
    if (btnCancelImport) btnCancelImport.addEventListener('click', closeAccountImportModal);

    const importModal = document.getElementById('accountImportModal');
    if (importModal) {
        importModal.addEventListener('click', (e) => {
            if (e.target === importModal) {
                closeAccountImportModal();
            }
        });
    }

    const importForm = document.getElementById('accountImportForm');
    if (importForm) importForm.addEventListener('submit', handleAccountImportSubmit);

    initAccountCsvDropZone();

    // 平台过滤胶囊标签点击
    const filterContainer = document.getElementById('accountPlatformFilter');
    if (filterContainer) {
        filterContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.account-filter-btn');
            if (!btn) return;
            filterContainer.querySelectorAll('.account-filter-btn').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            const cloud = btn.getAttribute('data-cloud');
            loadCloudAccounts(cloud);
        });
    }

    // 监听全局 Tab 切换，切换到 accounts 时自动加载
    document.querySelectorAll('[data-system-tab-target]').forEach(tabBtn => {
        tabBtn.addEventListener('click', () => {
            if (tabBtn.getAttribute('data-system-tab-target') === 'accounts') {
                loadCloudAccounts();
            }
        });
    });

    // 初始静默加载一次以更新 Badge
    loadCloudAccounts();
}



