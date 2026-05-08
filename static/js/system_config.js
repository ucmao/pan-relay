function getFrontendDisplayNetdiskCheckboxes() {
    return Array.from(document.querySelectorAll('.frontend-display-netdisk-checkbox'));
}

function getFrontendLinkModeRadios() {
    return Array.from(document.querySelectorAll('.frontend-link-mode-radio[name="frontendLinkMode"]'));
}

function updateDynamicTransferStatusVisibility() {
    const panel = document.getElementById('dynamicTransferStatusPanel');
    if (!panel) {
        return;
    }

    const selectedMode = document.querySelector('.frontend-link-mode-radio[name="frontendLinkMode"]:checked');
    panel.classList.toggle('d-none', !selectedMode || selectedMode.value !== 'view');
}

function bindFrontendLinkModeEvents() {
    getFrontendLinkModeRadios().forEach((radio) => {
        radio.addEventListener('change', updateDynamicTransferStatusVisibility);
    });
}

function renderDynamicTransferStatuses(statuses, summary) {
    const summaryEl = document.getElementById('dynamicTransferStatusSummary');
    const gridEl = document.getElementById('dynamicTransferStatusGrid');

    if (!summaryEl || !gridEl) {
        return;
    }

    const safeStatuses = Array.isArray(statuses) ? statuses : [];
    const enabledCount = Number(summary?.enabled_count || 0);
    const totalCount = Number(summary?.total_count || safeStatuses.length || 5);

    summaryEl.textContent = `当前有 ${enabledCount} / ${totalCount} 个云盘具备自动转存替换条件。未配置或基础校验未通过的平台，查看时会自动回退原始链接。`;

    gridEl.innerHTML = safeStatuses.map((item) => {
        const statusClass = item.status || 'missing';
        const badgeTextMap = {
            enabled: '已启用',
            invalid: '待处理',
            missing: '未配置',
        };
        const badgeText = badgeTextMap[statusClass] || '未配置';

        return `
            <article class="dynamic-transfer-status-card status-${statusClass}">
                <div class="dynamic-transfer-status-card-top">
                    <div>
                        <h4 class="dynamic-transfer-status-card-title">${item.cloud_name || ''}</h4>
                        <p class="dynamic-transfer-status-card-meta">${item.credential_type || ''}</p>
                    </div>
                    <span class="dynamic-transfer-status-badge">${badgeText}</span>
                </div>
                <div class="dynamic-transfer-status-card-body">
                    <strong>${item.title || ''}</strong>
                    <p>${item.description || ''}</p>
                </div>
            </article>
        `;
    }).join('');
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
        checkbox.addEventListener('change', updateFrontendNetdiskSelectionUI);
    });
}

async function loadPublicSearchApiConfig() {
    try {
        const response = await fetch('/admin/api/public-search-api-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const targetValue = data.enabled ? 'true' : 'false';
        const radio = document.querySelector(`.frontend-link-mode-radio[name="publicSearchApiEnabled"][value="${targetValue}"]`);
        if (radio) {
            radio.checked = true;
        }
    } catch (error) {
        console.error('加载公开聚合接口配置失败:', error);
        showToast('加载公开聚合接口配置失败，请检查后端日志。', 'danger');
    }
}

async function savePublicSearchApiConfig() {
    const saveButton = document.getElementById('savePublicSearchApiButton');
    const selectedMode = document.querySelector('.frontend-link-mode-radio[name="publicSearchApiEnabled"]:checked');
    const enabled = selectedMode ? selectedMode.value === 'true' : true;

    saveButton.disabled = true;
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
    } catch (error) {
        console.error('保存公开聚合接口配置失败:', error);
        showToast(`保存公开聚合接口配置失败: ${error.message}`, 'danger');
    } finally {
        saveButton.disabled = false;
    }
}

function toggleAllFrontendDisplayNetdisks() {
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    const allChecked = checkboxes.length > 0 && checkboxes.every((checkbox) => checkbox.checked);
    checkboxes.forEach((checkbox) => {
        checkbox.checked = !allChecked;
    });
    updateFrontendNetdiskSelectionUI();
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
    const saveButton = document.getElementById('saveFrontendNetdiskConfigButton');
    const enabledNetdisks = getFrontendDisplayNetdiskCheckboxes()
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value);

    if (enabledNetdisks.length === 0) {
        showToast('前端显示网盘至少需要保留一个。', 'warning');
        return;
    }

    saveButton.disabled = true;
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
    } finally {
        saveButton.disabled = false;
    }
}

async function loadFrontendLinkMode() {
    try {
        const response = await fetch('/admin/api/frontend-link-mode');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const radio = document.querySelector(`.frontend-link-mode-radio[name="frontendLinkMode"][value="${data.mode || 'copy'}"]`);
        if (radio) {
            radio.checked = true;
        }
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('加载前端出链模式失败:', error);
        showToast('加载前端出链模式失败，请检查后端日志。', 'danger');
    }
}

async function saveFrontendLinkMode() {
    const selectedMode = document.querySelector('.frontend-link-mode-radio[name="frontendLinkMode"]:checked');
    const saveButton = document.getElementById('saveFrontendLinkModeButton');

    saveButton.disabled = true;
    try {
        const response = await fetch('/admin/api/frontend-link-mode', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: selectedMode ? selectedMode.value : 'copy' })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message, 'success');
    } catch (error) {
        console.error('保存前端出链模式失败:', error);
        showToast(`保存前端出链模式失败: ${error.message}`, 'danger');
    } finally {
        saveButton.disabled = false;
    }
}

async function loadCookieConfig() {
    try {
        const response = await fetch('/admin/api/credential-config');
        const data = await response.json();
        document.getElementById('baiduCookie').value = data.baidu_cookie || '';
        document.getElementById('quarkCookie').value = data.quark_cookie || '';
        document.getElementById('aliyunToken').value = data.aliyun_token || '';
        document.getElementById('ucCookie').value = data.uc_cookie || '';
        document.getElementById('xunleiRefreshToken').value = data.xunlei_refresh_token || '';
        document.getElementById('xunleiCaptchaSign').value = data.xunlei_captcha_sign || '';
        document.getElementById('xunleiUserId').value = data.xunlei_user_id || '';
        renderDynamicTransferStatuses(data.dynamic_transfer_statuses, data.dynamic_transfer_summary);
    } catch (error) {
        console.error('加载云盘凭证失败:', error);
        showToast('加载云盘凭证失败，请检查后端日志。', 'danger');
    }
}

async function saveCookieConfig() {
    const saveButton = document.getElementById('saveCookieConfigBtn');
    const payload = {
        baidu_cookie: document.getElementById('baiduCookie').value.trim(),
        quark_cookie: document.getElementById('quarkCookie').value.trim(),
        aliyun_token: document.getElementById('aliyunToken').value.trim(),
        uc_cookie: document.getElementById('ucCookie').value.trim(),
        xunlei_refresh_token: document.getElementById('xunleiRefreshToken').value.trim(),
        xunlei_captcha_sign: document.getElementById('xunleiCaptchaSign').value.trim(),
        xunlei_user_id: document.getElementById('xunleiUserId').value.trim(),
    };

    saveButton.disabled = true;
    try {
        const response = await fetch('/admin/api/credential-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '云盘凭证保存成功', 'success');
        await loadCookieConfig();
    } catch (error) {
        showToast(`云盘凭证保存失败: ${error.message}`, 'danger');
    } finally {
        saveButton.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindFrontendNetdiskCheckboxEvents();
    bindFrontendLinkModeEvents();
    loadPublicSearchApiConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadCookieConfig();
    updateDynamicTransferStatusVisibility();

    const saveCookieConfigBtn = document.getElementById('saveCookieConfigBtn');
    if (saveCookieConfigBtn) {
        saveCookieConfigBtn.addEventListener('click', saveCookieConfig);
    }
});
