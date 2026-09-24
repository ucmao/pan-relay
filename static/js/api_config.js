let apiConfigs = [];
const savedApiSortBy = localStorage.getItem('panrelay_api_sort_by');
let apiSortBy = savedApiSortBy || 'id';
const savedApiOrder = localStorage.getItem('panrelay_api_order');
let apiOrder = (savedApiOrder === 'asc' || savedApiOrder === 'desc') ? savedApiOrder : 'asc';
let apiCurrentPage = 1;
const savedApiPageSize = parseInt(localStorage.getItem('panrelay_api_pagesize'), 10);
let apiPageSize = (savedApiPageSize && [15, 30, 50, 100].includes(savedApiPageSize)) ? savedApiPageSize : 15;

function handleApiPageSizeChange(val) {
    const size = parseInt(val, 10);
    if (size > 0) {
        apiPageSize = size;
        try {
            localStorage.setItem('panrelay_api_pagesize', String(apiPageSize));
        } catch (e) {}
        apiCurrentPage = 1;
        renderTable();
    }
}
window.handleApiPageSizeChange = handleApiPageSizeChange;

function handleApiSort(field) {
    if (apiSortBy === field) {
        apiOrder = apiOrder === 'asc' ? 'desc' : 'asc';
    } else {
        apiSortBy = field;
        apiOrder = (field === 'name' || field === 'url') ? 'asc' : 'desc';
    }
    try {
        localStorage.setItem('panrelay_api_sort_by', apiSortBy);
        localStorage.setItem('panrelay_api_order', apiOrder);
    } catch (e) {}
    apiCurrentPage = 1;
    sortApiConfigs();
    updateApiSortIcons();
    renderTable();
}

function sortApiConfigs() {
    if (!apiSortBy) return;
    const factor = apiOrder === 'asc' ? 1 : -1;
    apiConfigs.sort((a, b) => {
        let valA = a[apiSortBy];
        let valB = b[apiSortBy];

        if (apiSortBy === 'status') {
            const rank = (val) => (val === 'healthy' || val === true ? 2 : (val === 'unhealthy' || val === false ? 1 : 0));
            valA = rank(valA);
            valB = rank(valB);
        } else if (apiSortBy === 'response_time_ms' || apiSortBy === 'id') {
            valA = Number(valA) || 0;
            valB = Number(valB) || 0;
        } else if (apiSortBy === 'is_enabled') {
            valA = Boolean(valA) ? 1 : 0;
            valB = Boolean(valB) ? 1 : 0;
        } else if (apiSortBy === 'checked_at') {
            valA = valA ? new Date(valA).getTime() : 0;
            valB = valB ? new Date(valB).getTime() : 0;
        } else {
            valA = String(valA || '').toLowerCase();
            valB = String(valB || '').toLowerCase();
        }

        if (valA < valB) return -1 * factor;
        if (valA > valB) return 1 * factor;
        return 0;
    });
}

function updateApiSortIcons() {
    const iconMap = {
        'id': 'apiSortIconId',
        'name': 'apiSortIconName',
        'is_enabled': 'apiSortIconIsEnabled',
        'status': 'apiSortIconStatus',
        'checked_at': 'apiSortIconCheckedAt',
        'url': 'apiSortIconUrl',
        'response_time_ms': 'apiSortIconResponseTimeMs'
    };

    Object.entries(iconMap).forEach(([field, elementId]) => {
        const iconEl = document.getElementById(elementId);
        if (!iconEl) return;
        if (apiSortBy === field) {
            iconEl.textContent = apiOrder === 'asc' ? '↑' : '↓';
            iconEl.className = 'text-blue-600 font-bold ml-0.5';
        } else {
            iconEl.textContent = '↕';
            iconEl.className = 'text-slate-300 ml-0.5';
        }
    });
}

window.handleApiSort = handleApiSort;

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
        sortApiConfigs();
        updateApiSortIcons();
        renderTable();
    } catch (error) {
        console.error('加载 API 配置时出错:', error);
        showToast('加载 API 配置失败，请检查后端连接或日志。', 'danger');
    }
}

const apiSelectionState = {
    selectedIds: new Set(),
    selectMode: 'page' // 'page' or 'all'
};

function toggleSelectApiRow(id, checked) {
    apiSelectionState.selectMode = 'page';
    if (checked) {
        apiSelectionState.selectedIds.add(id);
    } else {
        apiSelectionState.selectedIds.delete(id);
    }
    updateApiBatchToolbar();
}

function toggleSelectApiPage(checkbox) {
    const isChecked = checkbox.checked;
    apiSelectionState.selectMode = 'page';
    const startIdx = (apiCurrentPage - 1) * apiPageSize;
    const endIdx = Math.min(startIdx + apiPageSize, apiConfigs.length);
    const pageItems = apiConfigs.slice(startIdx, endIdx);

    pageItems.forEach(api => {
        if (isChecked) {
            apiSelectionState.selectedIds.add(api.id);
        } else {
            apiSelectionState.selectedIds.delete(api.id);
        }
    });
    renderTable();
}

function selectApiCurrentPage() {
    const total = apiConfigs.length;
    const startIdx = (apiCurrentPage - 1) * apiPageSize;
    const endIdx = Math.min(startIdx + apiPageSize, total);
    const pageItems = apiConfigs.slice(startIdx, endIdx);

    apiSelectionState.selectedIds.clear();
    pageItems.forEach(api => apiSelectionState.selectedIds.add(api.id));
    apiSelectionState.selectMode = 'page';
    renderTable();

    if (typeof showToast === 'function') {
        showToast(`已切换为仅选本页（${pageItems.length} 项）`, 'info');
    }
}

function toggleApiSelectAllMode() {
    const total = apiConfigs.length;
    const isAll = apiSelectionState.selectMode === 'all';

    if (isAll) {
        selectApiCurrentPage();
    } else {
        apiSelectionState.selectMode = 'all';
        apiConfigs.forEach(api => apiSelectionState.selectedIds.add(api.id));
        renderTable();
        if (typeof showToast === 'function') {
            showToast(`已全选全部 ${total} 项`, 'info');
        }
    }
}

function clearApiSelection() {
    apiSelectionState.selectedIds.clear();
    apiSelectionState.selectMode = 'page';
    renderTable();
}

function updateApiBatchToolbar() {
    const toolbar = document.getElementById('apiBatchToolbar');
    if (!toolbar) return;

    const count = apiSelectionState.selectedIds.size;
    const total = apiConfigs.length;
    const isAll = apiSelectionState.selectMode === 'all';
    const startIdx = (apiCurrentPage - 1) * apiPageSize;
    const endIdx = Math.min(startIdx + apiPageSize, total);
    const pageItems = apiConfigs.slice(startIdx, endIdx);
    const pageCount = pageItems.length;
    const allPageSelected = pageCount > 0 && pageItems.every(api => apiSelectionState.selectedIds.has(api.id));

    const summaryCountEl = document.getElementById('apiSelectedCount');
    const scopeLink = document.getElementById('apiScopeToggleLink');
    const selectPageCb = document.getElementById('selectApiPageCheckbox');

    if (selectPageCb) {
        selectPageCb.checked = allPageSelected;
        selectPageCb.indeterminate = pageItems.some(api => apiSelectionState.selectedIds.has(api.id)) && !allPageSelected;
    }

    if (count > 0 || isAll) {
        toolbar.classList.add('active');
        if (summaryCountEl) summaryCountEl.textContent = isAll ? total : count;
        if (scopeLink) {
            scopeLink.style.display = 'inline-flex';
            scopeLink.textContent = isAll ? '(切换为仅选本页)' : `(全选全部 ${total} 条)`;
        }
    } else {
        toolbar.classList.remove('active');
        if (scopeLink) scopeLink.style.display = 'none';
    }
}

async function batchEnableApis(isEnabled) {
    const ids = Array.from(apiSelectionState.selectedIds);
    const isAll = apiSelectionState.selectMode === 'all';
    const actionStr = isEnabled ? '启用' : '停用';

    if (ids.length === 0 && !isAll) {
        showToast(`请先选择要${actionStr}的 API`, 'warning');
        return;
    }

    const targetIds = isAll ? apiConfigs.map(a => a.id) : ids;

    try {
        const response = await fetch('/admin/api/configs/batch-toggle', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: targetIds, is_enabled: isEnabled })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `已批量${actionStr} API`, 'success');
            clearApiSelection();
            loadApiConfigs();
        } else {
            showToast(data.message || `批量${actionStr}失败`, 'danger');
        }
    } catch (e) {
        showToast(`批量${actionStr}网络请求异常: ${e.message}`, 'danger');
    }
}

async function batchDeleteApis() {
    const ids = Array.from(apiSelectionState.selectedIds);
    const isAll = apiSelectionState.selectMode === 'all';

    if (ids.length === 0 && !isAll) {
        showToast('请先选择要删除的 API', 'warning');
        return;
    }

    const targetIds = isAll ? apiConfigs.map(a => a.id) : ids;
    if (!confirm(`确定要批量删除选中的 ${targetIds.length} 个 API 搜索源吗？该操作不可恢复！`)) {
        return;
    }

    try {
        const response = await fetch('/admin/api/configs/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: targetIds })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || '已批量删除 API', 'success');
            clearApiSelection();
            loadApiConfigs();
        } else {
            showToast(data.message || '批量删除失败', 'danger');
        }
    } catch (e) {
        showToast(`批量删除网络请求异常: ${e.message}`, 'danger');
    }
}

async function batchTestApis(forceAll = false) {
    const ids = Array.from(apiSelectionState.selectedIds);
    const isAll = forceAll || apiSelectionState.selectMode === 'all';

    if (!forceAll && ids.length === 0 && !isAll) {
        showToast('请先选择要联调测试的 API', 'warning');
        return;
    }

    const targetIds = (forceAll || isAll) ? apiConfigs.map(a => a.id) : ids;
    if (targetIds.length === 0) {
        showToast('暂无 API 接口可供测试', 'warning');
        return;
    }
    showToast(`正在后台测试 ${targetIds.length} 个 API 接口，请稍候...`, 'info');

    try {
        const response = await fetch('/admin/api/test-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: targetIds })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || '批量测试完成', 'success');
            loadApiConfigs();
        } else {
            showToast(data.message || '批量测试失败', 'danger');
        }
    } catch (e) {
        showToast(`批量测试网络请求异常: ${e.message}`, 'danger');
    }
}

window.toggleSelectApiRow = toggleSelectApiRow;
window.toggleSelectApiPage = toggleSelectApiPage;
window.selectApiCurrentPage = selectApiCurrentPage;
window.toggleApiSelectAllMode = toggleApiSelectAllMode;
window.clearApiSelection = clearApiSelection;
window.batchEnableApis = batchEnableApis;
window.batchDeleteApis = batchDeleteApis;
window.batchTestApis = batchTestApis;

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

    if (totalCount === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-slate-400 py-6">暂无 API 搜索源数据</td></tr>`;
        renderApiPagination(0, 1);
        updateApiBatchToolbar();
        return;
    }

    const totalPages = Math.ceil(totalCount / apiPageSize) || 1;
    if (apiCurrentPage > totalPages) apiCurrentPage = totalPages;
    if (apiCurrentPage < 1) apiCurrentPage = 1;

    const startIdx = (apiCurrentPage - 1) * apiPageSize;
    const endIdx = Math.min(startIdx + apiPageSize, totalCount);
    const pageItems = apiConfigs.slice(startIdx, endIdx);

    pageItems.forEach((api, idx) => {
        const globalIndex = startIdx + idx;
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
        const isRowChecked = apiSelectionState.selectedIds.has(api.id);
        row.innerHTML = `
                    <td class="text-center">
                        <input class="form-check-input api-row-checkbox" type="checkbox" data-id="${api.id}" ${isRowChecked ? 'checked' : ''} onchange="toggleSelectApiRow(${api.id}, this.checked)">
                    </td>
                    <td class="text-center">${globalIndex + 1}</td>
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

    renderApiPagination(totalCount, totalPages);
    updateApiBatchToolbar();
}

function renderApiPagination(totalCount, totalPages) {
    const selectEl = document.getElementById('apiPageSizeSelect');
    if (selectEl) selectEl.value = String(apiPageSize);
    const curEl = document.getElementById('apiCurrentPageNum');
    if (curEl) curEl.textContent = apiCurrentPage;
    const totEl = document.getElementById('apiTotalPageNum');
    if (totEl) totEl.textContent = totalPages;
    const cntEl = document.getElementById('apiTotalCountNum');
    if (cntEl) cntEl.textContent = totalCount;
    const countEl = document.getElementById('apiTotalCount');
    if (countEl) countEl.textContent = `共 ${totalCount} 条`;

    const controlsEl = document.getElementById('apiPaginationControls');
    const jumpInput = document.getElementById('apiJumpPageInput');
    if (jumpInput) {
        jumpInput.max = totalPages;
        jumpInput.value = apiCurrentPage;
        jumpInput.disabled = totalPages <= 1;
    }
    const jumpBtn = document.getElementById('apiJumpPageBtn');
    if (jumpBtn) {
        jumpBtn.disabled = totalPages <= 1;
    }

    if (!controlsEl) return;
    controlsEl.innerHTML = '';

    // Prev Button
    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${apiCurrentPage === 1 ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
    prevBtn.innerHTML = '<i class="fas fa-chevron-left text-[10px]"></i>';
    prevBtn.disabled = apiCurrentPage === 1;
    prevBtn.onclick = () => { apiCurrentPage--; renderTable(); };
    controlsEl.appendChild(prevBtn);

    // Page numbers
    for (let p = 1; p <= totalPages; p++) {
        if (totalPages > 7 && Math.abs(p - apiCurrentPage) > 2 && p !== 1 && p !== totalPages) {
            if (p === 2 && apiCurrentPage > 4) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'px-1 text-slate-400 text-xs';
                ellipsis.textContent = '...';
                controlsEl.appendChild(ellipsis);
            } else if (p === totalPages - 1 && apiCurrentPage < totalPages - 3) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'px-1 text-slate-400 text-xs';
                ellipsis.textContent = '...';
                controlsEl.appendChild(ellipsis);
            }
            continue;
        }

        const pageBtn = document.createElement('button');
        pageBtn.type = 'button';
        pageBtn.className = `px-2.5 py-1 text-xs rounded-lg transition font-medium cursor-pointer ${p === apiCurrentPage ? 'bg-blue-600 text-white shadow-2xs font-semibold' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`;
        pageBtn.textContent = p;
        pageBtn.onclick = () => { apiCurrentPage = p; renderTable(); };
        controlsEl.appendChild(pageBtn);
    }

    // Next Button
    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${apiCurrentPage === totalPages ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
    nextBtn.innerHTML = '<i class="fas fa-chevron-right text-[10px]"></i>';
    nextBtn.disabled = apiCurrentPage === totalPages;
    nextBtn.onclick = () => { apiCurrentPage++; renderTable(); };
    controlsEl.appendChild(nextBtn);
}

function handleApiJumpPage() {
    const input = document.getElementById('apiJumpPageInput');
    if (!input) return;
    const page = parseInt(input.value, 10);
    const totalPages = Math.ceil(apiConfigs.length / apiPageSize) || 1;
    if (page >= 1 && page <= totalPages) {
        apiCurrentPage = page;
        renderTable();
    } else {
        input.value = apiCurrentPage;
    }
}
window.handleApiJumpPage = handleApiJumpPage;

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
    if (!(await showConfirm('确定要测试所有 API 搜索源吗？', 'primary', '批量测试确认'))) return;

    let originalHtml = '';
    if (btn) {
        btn.disabled = true;
        originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 检测中...';
    }
    showToast('正在并发检测所有 API 搜索源连通性...', 'info');

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
