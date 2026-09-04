function getFrontendDisplayNetdiskCheckboxes() {
    return Array.from(document.querySelectorAll('.frontend-display-netdisk-checkbox'));
}

function getFrontendLinkModeRadios() {
    return Array.from(document.querySelectorAll('.frontend-link-mode-radio[name="frontendLinkMode"]'));
}

function updateDynamicTransferStatusVisibility() {
    const panel = document.getElementById('dynamicTransferStatusPanel');
    const selectedMode = document.querySelector('.frontend-link-mode-radio[name="frontendLinkMode"]:checked');
    const kpiEl = document.getElementById('kpiDeliveryMode');
    if (kpiEl && selectedMode) {
        kpiEl.textContent = selectedMode.value === 'view' ? '动态转存模式' : '原始链接模式';
    }
    if (!panel) {
        return;
    }

    panel.classList.toggle('d-none', !selectedMode || selectedMode.value !== 'view');
}

function bindFrontendLinkModeEvents() {
    getFrontendLinkModeRadios().forEach((radio) => {
        radio.addEventListener('change', updateDynamicTransferStatusVisibility);
    });
}

function bindSystemTabEvents() {
    document.querySelectorAll('[data-system-tab-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-system-tab-target');
            document.querySelectorAll('[data-system-tab-target]').forEach((b) => b.classList.remove('is-active'));
            document.querySelectorAll('.system-tab-pane').forEach((pane) => pane.classList.remove('is-active'));
            btn.classList.add('is-active');
            const targetPane = document.getElementById(`tab-pane-${target}`);
            if (targetPane) {
                targetPane.classList.add('is-active');
            }
        });
    });
}

function bindCredentialTabEvents() {
    document.querySelectorAll('[data-cred-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-cred-target');
            document.querySelectorAll('[data-cred-target]').forEach((b) => b.classList.remove('is-active'));
            document.querySelectorAll('.credential-tab-pane').forEach((pane) => pane.classList.remove('is-active'));
            btn.classList.add('is-active');
            const targetPane = document.getElementById(`cred-pane-${target}`);
            if (targetPane) {
                targetPane.classList.add('is-active');
            }
        });
    });
}

function renderDynamicTransferStatuses(statuses, summary) {
    const summaryEl = document.getElementById('dynamicTransferStatusSummary');
    const gridEl = document.getElementById('dynamicTransferStatusGrid');

    const safeStatuses = Array.isArray(statuses) ? statuses : [];
    const enabledCount = Number(summary?.enabled_count || 0);
    const totalCount = Number(summary?.total_count || safeStatuses.length || 5);

    const credentialsTabBadge = document.getElementById('credentialsTabBadge');
    if (credentialsTabBadge) {
        credentialsTabBadge.textContent = String(enabledCount);
    }

    if (summaryEl) {
        summaryEl.textContent = `当前有 ${enabledCount} / ${totalCount} 个云盘具备自动转存替换条件。未配置或基础校验未通过的平台，查看时会自动回退原始链接。`;
    }

    if (gridEl) {
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

    // 更新网盘 Sub-Tab 的健康状态点与状态文本
    const cloudKeyMap = {
        '百度网盘': { dotId: 'dot-baidu', textId: 'baiduStatusText' },
        '夸克网盘': { dotId: 'dot-quark', textId: 'quarkStatusText' },
        '阿里云盘': { dotId: 'dot-aliyun', textId: 'aliyunStatusText' },
        'UC网盘': { dotId: 'dot-uc', textId: 'ucStatusText' },
        '迅雷网盘': { dotId: 'dot-xunlei', textId: 'xunleiStatusText' },
    };

    safeStatuses.forEach((item) => {
        const keyInfo = cloudKeyMap[item.cloud_name];
        if (!keyInfo) return;

        const dotEl = document.getElementById(keyInfo.dotId);
        const textEl = document.getElementById(keyInfo.textId);
        const statusClass = item.status || 'missing';

        if (dotEl) {
            dotEl.className = `cred-status-dot ${statusClass}`;
        }
        if (textEl) {
            textEl.textContent = item.title || '未配置';
            if (statusClass === 'enabled') {
                textEl.className = 'text-[11px] text-emerald-600 font-semibold';
            } else if (statusClass === 'invalid') {
                textEl.className = 'text-[11px] text-amber-600 font-semibold';
            } else {
                textEl.className = 'text-[11px] text-slate-400 font-medium';
            }
        }
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
        const toggle = document.getElementById('publicSearchApiToggle');
        const badge = document.getElementById('publicSearchApiBadge');
        if (toggle) {
            toggle.checked = Boolean(data.enabled);
        }
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

    if (saveButton) saveButton.disabled = true;
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
        if (saveButton) saveButton.disabled = false;
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

    if (saveButton) saveButton.disabled = true;
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
        if (saveButton) saveButton.disabled = false;
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

    if (saveButton) saveButton.disabled = true;
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
        if (saveButton) saveButton.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindSystemTabEvents();
    bindCredentialTabEvents();
    bindFrontendNetdiskCheckboxEvents();
    bindFrontendLinkModeEvents();
    loadPublicSearchApiConfig();
    loadAllowExcelDownloadConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadCookieConfig();
    updateDynamicTransferStatusVisibility();

    const saveCookieConfigBtn = document.getElementById('saveCookieConfigBtn');
    if (saveCookieConfigBtn) {
        saveCookieConfigBtn.addEventListener('click', saveCookieConfig);
    }
});
