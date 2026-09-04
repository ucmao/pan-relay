let apiConfigs = [];

/**
 * 显示 Toast 通知
 * @param {string} message - 提示消息
 * @param {string} type - 提示类型 ('success', 'danger', 'info', 'warning')
 */


// 新增：格式化 JSON 输入框内容
function formatJson(textareaId) {
    const textarea = document.getElementById(textareaId);
    if (!textarea) return;

    try {
        const jsonText = textarea.value.trim();
        if (!jsonText) return;

        // 尝试解析并重新格式化
        const parsedJson = JSON.parse(jsonText);
        textarea.value = JSON.stringify(parsedJson, null, 4);
        showToast('JSON 格式化成功', 'success');
    } catch (e) {
        showToast('JSON 格式化失败: 请检查语法错误', 'danger');
    }
}

// 新增：从模态框中获取 API 数据
function getApiDataFromModal(prefix) {
    const isNewApi = (prefix === 'api');

    // 确保必填字段不为空
    const name = document.getElementById(`${prefix}Name`).value;
    const url = document.getElementById(`${prefix}Url`).value;
    const request = document.getElementById(`${prefix}Request`).value;
    const responseMapping = document.getElementById(`${prefix}Response`).value;

    if (!name || !url || !responseMapping) {
        showToast('请填写所有带 * 的必填字段', 'warning');
        return null;
    }

    // 只有当 request 不为空时才验证 JSON 格式
    if (request && request.trim() !== '') {
        try {
            JSON.parse(request);
        } catch (e) {
            showToast('请求体 JSON 格式不正确', 'danger');
            return null;
        }
    }

    const api = {
        name: name,
        url: url,
        method: document.getElementById(`${prefix}Method`).value,
        request: request,
        response: responseMapping,
        is_enabled: document.getElementById(`${prefix}IsEnabled`).value === 'true',
        id: isNewApi ? 0 : document.getElementById('editApiId').value,
        status: null,
        response_time_ms: null
    };
    return api;
}

// 新增：在模态框中测试 API 草稿
async function testDraftApi(prefix) {
    const testButtonId = (prefix === 'api') ? 'apiTestButton' : 'editApiTestButton';
    const testButton = document.getElementById(testButtonId);
    if (testButton) testButton.disabled = true;

    const api = getApiDataFromModal(prefix);
    if (!api) {
        if (testButton) testButton.disabled = false;
        return;
    }
    const apiName = api.name;

    try {
        const response = await fetch('/admin/api/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(api)
        });

        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.error || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }
        const data = await response.json();

        if (data.test_outcome === 'no_data') {
            showToast(`API ${apiName} 可正常访问，但“仙逆、逆袭、总裁”均无结果，未自动禁用。`, 'warning');
        } else if (data.status) {
            showToast(`API ${apiName} 测试成功！耗时 ${data.response_time_ms}ms`, 'success');
        } else {
            showToast(`API ${apiName} 测试失败/异常！请检查配置。`, 'danger');
        }
    } catch (error) {
        showToast(`API ${apiName} 测试失败！错误：${error.message}`, 'danger');
    } finally {
        if (testButton) testButton.disabled = false;
    }
}

// 从服务器获取 API 配置
async function loadApiConfigs() {
    try {
        const response = await fetch('/admin/api/configs');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        apiConfigs = await response.json();
        renderTable();
    } catch (error) {
        console.error('加载 API 配置时出错:', error);
        showToast('加载 API 配置失败，请检查后端连接或日志。', 'danger');
    }
}

// 渲染表格
function renderTable() {
    const tbody = document.getElementById('apiTableBody');
    tbody.innerHTML = '';

    const enabledCount = apiConfigs.filter(a => a.is_enabled).length;
    const totalCount = apiConfigs.length;

    const kpiTotalEl = document.getElementById('kpiApiTotal');
    if (kpiTotalEl) kpiTotalEl.textContent = `${totalCount} 个`;
    const kpiEnabledEl = document.getElementById('kpiApiEnabled');
    if (kpiEnabledEl) kpiEnabledEl.textContent = `${enabledCount} 个`;

    const kpiApiStat = document.getElementById('kpiApiStat');
    if (kpiApiStat) kpiApiStat.textContent = `${enabledCount} / ${totalCount}`;
    const tabBadgeApi = document.getElementById('tabBadgeApi');
    if (tabBadgeApi) tabBadgeApi.textContent = `${enabledCount}/${totalCount}`;

    apiConfigs.forEach((api, index) => {
        const isHealthy = api.status === 'healthy' || api.status === true;
        const isUnhealthy = api.status === 'unhealthy' || api.status === false;
        const healthClass = isHealthy ? 'health-normal' : (isUnhealthy ? 'health-error' : 'health-unknown');
        const healthIcon = isHealthy ? 'fa-check-circle' : (isUnhealthy ? 'fa-exclamation-circle' : 'fa-minus-circle');
        const healthText = isHealthy ? '正常' : (isUnhealthy ? '异常' : '未检测');
        const healthBadge = `<span class="health-text-badge ${healthClass}" title="最新测试结果"><i class="fas ${healthIcon}"></i> ${healthText}</span>`;
        const timeDisplay = api.response_time_ms !== null && api.response_time_ms > 0 ? `${api.response_time_ms} ms` : '--';
        const checkedAtDisplay = formatCheckedAt(api.checked_at);

        let toggleBtnClass;
        let toggleBtnText;
        let toggleBtnIcon;
        let nextAction;

        if (api.is_enabled) {
            toggleBtnClass = 'btn-success';
            toggleBtnText = '启用';
            toggleBtnIcon = 'fa-toggle-on';
            nextAction = false;
        } else {
            toggleBtnClass = 'btn-danger';
            toggleBtnText = '禁止';
            toggleBtnIcon = 'fa-toggle-off';
            nextAction = true;
        }

        const rowClass = api.is_enabled ? '' : 'disabled-api';
        const enableBadge = api.is_enabled
            ? '<span class="status-dot-badge is-enabled"><span class="dot"></span>已启用</span>'
            : '<span class="status-dot-badge is-disabled"><span class="dot"></span>已停用</span>';

        const row = document.createElement('tr');
        row.className = rowClass;
        row.innerHTML = `
                    <td class="text-center">${index + 1}</td>
                    <td><strong>${escapeHtml(api.name)}</strong></td>
                    <td class="text-center">${enableBadge}</td>
                    <td class="text-center">${healthBadge}</td>
                    <td class="text-center text-xs text-slate-500">${checkedAtDisplay}</td>
                    <td style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: normal; word-wrap: break-word;">${api.url}</td>
                    <td class="text-center">${timeDisplay}</td>
                    <td class="action-buttons text-center">
                        <div class="inline-flex items-center gap-1.5 justify-center">
                            <button class="btn btn-sm ${toggleBtnClass}" title="点击切换状态"
                                    onclick="toggleEnabled(${api.id}, ${nextAction})">
                                <i class="fas ${toggleBtnIcon}"></i> ${toggleBtnText}
                            </button>
                            <button class="btn btn-sm btn-info" onclick="testApi(${api.id}, this)" title="测试单个 API">
                                <i class="fas fa-play"></i> 测试
                            </button>
                            <div class="dropdown relative inline-block">
                                <button class="btn btn-sm btn-secondary dropdown-toggle" type="button"
                                    data-ui-dropdown-toggle aria-expanded="false" title="更多操作">
                                    <i class="fas fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu dropdown-menu-end">
                                    <li>
                                        <a class="dropdown-item" href="javascript:void(0)" onclick="editApi(${api.id})">
                                            <i class="fas fa-edit me-2 text-slate-400"></i> 修改
                                        </a>
                                    </li>
                                    <li>
                                        <a class="dropdown-item" href="javascript:void(0)" onclick="copyApi(${api.id})">
                                            <i class="fas fa-copy me-2 text-slate-400"></i> 复制
                                        </a>
                                    </li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li>
                                        <a class="dropdown-item text-danger" href="javascript:void(0)" onclick="deleteApi(${api.id})">
                                            <i class="fas fa-trash me-2"></i> 删除
                                        </a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </td>
                `;
        tbody.appendChild(row);
    });
}

function formatCheckedAt(value) {
    if (!value) return '--';
    const date = new Date(value.replace(' ', 'T'));
    return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false });
}

// 辅助函数：转义HTML字符，防止XSS攻击
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 辅助函数：根据 ID 查找配置对象和它的当前索引
function getApiConfigById(apiId) {
    const index = apiConfigs.findIndex(api => api.id == apiId);
    return { api: apiConfigs[index], index: index };
}

function normalizeApiId(apiId) {
    const normalizedId = Number.parseInt(apiId, 10);
    return Number.isInteger(normalizedId) && normalizedId > 0 ? normalizedId : null;
}

// 切换单个 API 的启用/禁用状态
async function toggleEnabled(apiId, isEnabled) {
    const action = isEnabled ? '启用' : '禁止';
    const { api } = getApiConfigById(apiId);

    if (!api) {
        showToast('API 配置不存在!', 'danger');
        return;
    }

    try {
        const response = await fetch(`/admin/api/configs/${apiId}/enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_enabled: isEnabled })
        });

        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        showToast(`API "${api.name}" 已成功${action}。`, 'success');
        loadApiConfigs();
    } catch (error) {
        console.error(`切换 API 启用状态时出错:`, error);
        showToast(`API ${action}失败: ${error.message}`, 'danger');
    }
}

// 全部测试 API
async function testAllApis() {
    const btn = document.getElementById('testAllApiButton');
    if (!(await showConfirm('确定要测试所有 API 检索源吗？', 'primary', '批量测试确认'))) return;

    let originalHtml = '';
    if (btn) {
        btn.disabled = true;
        originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 检测中...';
    }
    showToast('正在并发检测所有 API 检索源连通性...', 'info');

    try {
        const response = await fetch('/admin/api/test-all', { method: 'POST' });
        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }
        const data = await response.json();
        const toastType = (data.failed_count && data.failed_count > 0) ? 'warning' : 'success';
        showToast(data.message || '全量 API 测试完成', toastType);
        await loadApiConfigs();
    } catch (error) {
        console.error('全部测试 API 时出错:', error);
        showToast(`全部测试失败: ${error.message}`, 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

// 全部启用所有 API
async function enableAllApis() {
    const enableAllButton = document.getElementById('enableAllButton');
    if (await showConfirm('确定要启用所有 API 配置吗？', 'primary', '批量启用确认')) {
        enableAllButton.disabled = true;

        try {
            const response = await fetch('/admin/api/configs/enable-all', { method: 'PUT' });

            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
                } catch {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }

            const data = await response.json();
            showToast(data.message, 'success');
            loadApiConfigs();
        } catch (error) {
            console.error('全部启用 API 时出错:', error);
            showToast(`全部启用失败: ${error.message}`, 'danger');
        } finally {
            enableAllButton.disabled = false;
        }
    }
}

// 全部禁用 API
async function disableAllApis() {
    const disableAllButton = document.getElementById('disableAllButton');
    if (await showConfirm('确定要禁用所有 API 配置吗？', 'danger', '批量禁用确认')) {
        disableAllButton.disabled = true;

        try {
            const response = await fetch('/admin/api/configs/disable-all', { method: 'PUT' });

            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
                } catch {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }

            const data = await response.json();
            showToast(data.message, 'success');
            loadApiConfigs();
        } catch (error) {
            console.error('全部禁用 API 时出错:', error);
            showToast(`全部禁用失败: ${error.message}`, 'danger');
        } finally {
            disableAllButton.disabled = false;
        }
    }
}

// 添加 API
async function addApi() {
    const api = getApiDataFromModal('api');
    if (!api) return;

    try {
        const response = await fetch('/admin/api/configs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(api)
        });

        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        const data = await response.json();
        showToast(data.message, 'success');
        loadApiConfigs();
        document.getElementById('addApiForm').reset();
        window.AppUI.closeModal('addApiModal');
    } catch (error) {
        console.error('添加 API 配置时出错:', error);
        showToast(`添加 API 配置失败: ${error.message}`, 'danger');
    }
}

// 修改 API
function editApi(apiId) {
    const { api } = getApiConfigById(apiId);
    if (!api) {
        showToast('未找到该配置！', 'warning');
        return;
    }
    document.getElementById('editApiId').value = apiId;
    document.getElementById('editApiName').value = api.name;
    document.getElementById('editApiUrl').value = api.url;
    document.getElementById('editApiMethod').value = api.method;
    document.getElementById('editApiRequest').value = api.request;
    document.getElementById('editApiResponse').value = api.response;
    document.getElementById('editApiIsEnabled').value = api.is_enabled ? 'true' : 'false';

    window.AppUI.openModal('editApiModal');
}

// 保存修改
async function saveEditedApi() {
    const apiId = normalizeApiId(document.getElementById('editApiId').value);
    if (!apiId) {
        showToast('未获取到有效的 API ID，无法保存修改。', 'danger');
        return;
    }
    const isEnabledValue = document.getElementById('editApiIsEnabled').value;

    const { api: originalApi } = getApiConfigById(apiId);
    if (!originalApi) {
        showToast('无法获取原始配置，保存失败！', 'danger');
        return;
    }

    if (isEnabledValue === 'true' && (originalApi.status === 'unhealthy' || originalApi.status === false)) {
        showToast(`API "${originalApi.name}" 状态异常，无法启用。请先测试并修复。`, 'danger');
        return;
    }

    const api = getApiDataFromModal('editApi');
    if (!api) return;

    api.id = apiId;
    api.status = originalApi.status;

    try {
        const response = await fetch(`/admin/api/configs/${apiId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(api)
        });

        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        const data = await response.json();
        showToast(data.message, 'success');
        loadApiConfigs();
        window.AppUI.closeModal('editApiModal');
    } catch (error) {
        console.error('修改 API 配置时出错:', error);
        showToast(`修改 API 配置失败: ${error.message}`, 'danger');
    }
}

// 删除 API
async function deleteApi(apiId) {
    apiId = normalizeApiId(apiId);
    if (!apiId) {
        showToast('未获取到有效的 API ID，无法删除。', 'danger');
        return;
    }

    const { api } = getApiConfigById(apiId);
    if (!api) return;

    if (await showConfirm(`确定删除 API "${api.name}" 吗？此操作不可撤销。`, 'danger')) {
        try {
            const response = await fetch(`/admin/api/configs/${apiId}`, { method: 'DELETE' });

            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
                } catch {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }

            const data = await response.json();
            showToast(data.message, 'success');
            loadApiConfigs();
        } catch (error) {
            console.error('删除 API 配置时出错:', error);
            showToast(`删除 API 配置失败: ${error.message}`, 'danger');
        }
    }
}

// 测试 API (单个)
async function testApi(apiId, triggerButton = null) {
    const { api } = getApiConfigById(apiId);
    if (!api) return;
    const testButton = triggerButton;
    const originalButtonHtml = testButton ? testButton.innerHTML : '';

    if (testButton) {
        testButton.disabled = true;
        testButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 测试中';
    }

    try {
        const apiWithId = { ...api, id: apiId };
        const response = await fetch('/admin/api/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(apiWithId)
        });

        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.error || `HTTP error! status: ${response.status}`);
            } catch {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        const data = await response.json();
        if (data.test_outcome === 'no_data') {
            showToast(`API ${api.name} 可正常访问，但“仙逆、逆袭、总裁”均无结果，未自动禁用。`, 'warning');
        } else if (data.status) {
            showToast(`API ${api.name} 测试成功！耗时 ${data.response_time_ms}ms`, 'success');
        } else {
            showToast(`API ${api.name} 测试完成，状态异常，已自动禁止。`, 'warning');
        }

        loadApiConfigs();
    } catch (error) {
        showToast(`API ${api.name} 测试失败！错误：${error.message}`, 'danger');
        loadApiConfigs();
    } finally {
        if (testButton) {
            testButton.disabled = false;
            testButton.innerHTML = originalButtonHtml;
        }
    }
}

// 复制 API
async function copyApi(apiId) {
    // 添加确认提示
    if (await showConfirm('确定要复制此API配置吗？')) {
        try {
            const response = await fetch(`/admin/api/configs/copy/${apiId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || `HTTP error! status: ${response.status}`);
                } catch {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }

            const data = await response.json();
            showToast(data.message, 'success');
            loadApiConfigs();
        } catch (error) {
            console.error('复制 API 配置时出错:', error);
            showToast(`复制 API 配置失败: ${error.message}`, 'danger');
        }
    }
}

window.enableAllApis = enableAllApis;
window.disableAllApis = disableAllApis;
window.testAllApis = testAllApis;
window.testApi = testApi;
window.editApi = editApi;
window.copyApi = copyApi;
window.deleteApi = deleteApi;
window.toggleEnabled = toggleEnabled;

const testAllApiButton = document.getElementById('testAllApiButton');
if (testAllApiButton) {
    testAllApiButton.addEventListener('click', testAllApis);
}

const enableAllButton = document.getElementById('enableAllButton');
if (enableAllButton) {
    enableAllButton.addEventListener('click', enableAllApis);
}

const disableAllButton = document.getElementById('disableAllButton');
if (disableAllButton) {
    disableAllButton.addEventListener('click', disableAllApis);
}

// 初始化加载数据
loadApiConfigs();
