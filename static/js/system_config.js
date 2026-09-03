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

async function loadTgSearchConfig() {
    try {
        const response = await fetch('/admin/api/tg-search-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success && data.config) {
            const cfg = data.config;
            const targetVal = cfg.enabled ? 'true' : 'false';
            const radio = document.querySelector(`.frontend-link-mode-radio[name="tgSearchEnabled"][value="${targetVal}"]`);
            if (radio) radio.checked = true;

            const proxyEl = document.getElementById('tgProxyInput');
            if (proxyEl) proxyEl.value = cfg.proxy || '';

            const timeoutEl = document.getElementById('tgTimeoutInput');
            if (timeoutEl) timeoutEl.value = cfg.timeout || 10;

            const workersEl = document.getElementById('tgMaxWorkersInput');
            if (workersEl) workersEl.value = cfg.max_workers || 4;

            const channelsEl = document.getElementById('tgChannelsInput');
            if (channelsEl) {
                const channelsArr = Array.isArray(cfg.channels) ? cfg.channels : [];
                channelsEl.value = channelsArr.join(', ');
                const testChanEl = document.getElementById('tgTestChannel');
                if (testChanEl && !testChanEl.value && channelsArr.length > 0) {
                    testChanEl.value = channelsArr[0];
                }
            }
        }
    } catch (error) {
        console.error('加载 TG 搜索配置失败:', error);
        showToast('加载 TG 搜索配置失败，请检查网络或后端状态', 'danger');
    }
}

async function saveTgSearchConfig() {
    const saveBtn = document.getElementById('saveTgSearchConfigBtn');
    if (saveBtn) saveBtn.disabled = true;

    const enabledRadio = document.querySelector('.frontend-link-mode-radio[name="tgSearchEnabled"]:checked');
    const enabled = enabledRadio ? enabledRadio.value === 'true' : true;
    const proxy = (document.getElementById('tgProxyInput')?.value || '').trim();
    const timeout = parseInt(document.getElementById('tgTimeoutInput')?.value || '10', 10);
    const max_workers = parseInt(document.getElementById('tgMaxWorkersInput')?.value || '4', 10);
    const channels = (document.getElementById('tgChannelsInput')?.value || '').trim();

    const payload = {
        enabled,
        proxy,
        timeout,
        max_workers,
        channels,
    };

    try {
        const response = await fetch('/admin/api/tg-search-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        showToast(data.message || 'Telegram 搜索配置已成功保存！', 'success');
        await loadTgSearchConfig();
    } catch (error) {
        showToast(`保存 TG 配置失败: ${error.message}`, 'danger');
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function runTgTest() {
    const btn = document.getElementById('doTgTestBtn');
    const chanInput = document.getElementById('tgTestChannel');
    const kwInput = document.getElementById('tgTestKeyword');
    const resultArea = document.getElementById('tgTestResultArea');
    const statusAlert = document.getElementById('tgTestStatusAlert');
    const tbody = document.getElementById('tgTestTableBody');

    const channel = (chanInput?.value || '').trim();
    const keyword = (kwInput?.value || '测试').trim() || '测试';
    const proxy = (document.getElementById('tgProxyInput')?.value || '').trim();
    const timeout = parseInt(document.getElementById('tgTimeoutInput')?.value || '10', 10);

    if (!channel) {
        showToast('请先输入要测试的 Telegram 频道名称', 'warning');
        if (chanInput) chanInput.focus();
        return;
    }

    if (btn) btn.disabled = true;
    if (resultArea) resultArea.classList.remove('d-none');
    if (statusAlert) {
        statusAlert.className = 'alert alert-info py-2 px-3 small mb-2';
        statusAlert.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> 正在向频道 <strong>@${channel}</strong> 发起测试检索（关键词: "${keyword}"）...`;
    }
    if (tbody) tbody.innerHTML = '';

    try {
        const response = await fetch('/admin/api/tg-search-config/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel, keyword, proxy, timeout }),
        });
        const data = await response.json();

        if (!data.success) {
            statusAlert.className = 'alert alert-warning py-2 px-3 small mb-2';
            statusAlert.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> ${data.message || '测试未返回有效结果'}`;
            return;
        }

        statusAlert.className = 'alert alert-success py-2 px-3 small mb-2';
        statusAlert.innerHTML = `<i class="fas fa-check-circle me-1"></i> ${data.message} (耗时: ${data.latency_ms}ms)`;

        const results = data.results || [];
        if (results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">该频道在本次搜索中未匹配到公开网盘链接（可能为私有频道、防抓取跳转或无对应关键词资源）</td></tr>`;
        } else {
            tbody.innerHTML = results.map((item, idx) => `
                <tr>
                    <td class="text-center text-muted">${idx + 1}</td>
                    <td><span class="text-break">${escapeHtml(item.title || item[1] || '无标题')}</span></td>
                    <td><span class="badge bg-secondary">${escapeHtml(item.cloud_name || item[3] || '未知')}</span></td>
                    <td>
                        <a href="${escapeHtml(item.share_link || item[2] || '#')}" target="_blank" class="text-break small text-decoration-none">
                            ${escapeHtml(item.share_link || item[2] || '')}
                        </a>
                    </td>
                </tr>
            `).join('');
        }
    } catch (error) {
        if (statusAlert) {
            statusAlert.className = 'alert alert-danger py-2 px-3 small mb-2';
            statusAlert.innerHTML = `<i class="fas fa-times-circle me-1"></i> 请求出错: ${error.message}`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindFrontendNetdiskCheckboxEvents();
    bindFrontendLinkModeEvents();
    loadPublicSearchApiConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadCookieConfig();
    loadTgSearchConfig();
    updateDynamicTransferStatusVisibility();

    const saveCookieConfigBtn = document.getElementById('saveCookieConfigBtn');
    if (saveCookieConfigBtn) {
        saveCookieConfigBtn.addEventListener('click', saveCookieConfig);
    }
});

