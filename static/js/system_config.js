function getFrontendDisplayNetdiskCheckboxes() {
    return Array.from(document.querySelectorAll('.frontend-display-netdisk-checkbox'));
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
        const response = await fetch('/api/public-search-api-config');
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
        const response = await fetch('/api/public-search-api-config', {
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
        const response = await fetch('/api/frontend-display-netdisks');
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
        const response = await fetch('/api/frontend-display-netdisks', {
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
        const response = await fetch('/api/frontend-link-mode');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const radio = document.querySelector(`.frontend-link-mode-radio[name="frontendLinkMode"][value="${data.mode || 'copy'}"]`);
        if (radio) {
            radio.checked = true;
        }
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
        const response = await fetch('/api/frontend-link-mode', {
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
        const response = await fetch('/cookie-config');
        const data = await response.json();
        document.getElementById('baiduCookie').value = data.baidu_cookie || '';
        document.getElementById('quarkCookie').value = data.quark_cookie || '';
    } catch (error) {
        console.error('加载 Cookie 失败:', error);
        showToast('加载 Cookie 失败，请检查后端日志。', 'danger');
    }
}

async function saveCookieConfig() {
    const saveButton = document.getElementById('saveCookieConfigBtn');
    const payload = {
        baidu_cookie: document.getElementById('baiduCookie').value.trim(),
        quark_cookie: document.getElementById('quarkCookie').value.trim(),
    };

    saveButton.disabled = true;
    try {
        const response = await fetch('/cookie-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast('Cookie配置保存成功', 'success');
    } catch (error) {
        showToast(`Cookie配置保存失败: ${error.message}`, 'danger');
    } finally {
        saveButton.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindFrontendNetdiskCheckboxEvents();
    loadPublicSearchApiConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadCookieConfig();

    const saveCookieConfigBtn = document.getElementById('saveCookieConfigBtn');
    if (saveCookieConfigBtn) {
        saveCookieConfigBtn.addEventListener('click', saveCookieConfig);
    }
});
