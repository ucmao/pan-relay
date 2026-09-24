// 插件管理前端交互逻辑

let currentPluginsData = [];
const savedPluginSortBy = localStorage.getItem('panrelay_plugin_sort_by');
let pluginSortBy = savedPluginSortBy || 'id';
const savedPluginOrder = localStorage.getItem('panrelay_plugin_order');
let pluginOrder = (savedPluginOrder === 'asc' || savedPluginOrder === 'desc') ? savedPluginOrder : 'asc';
let pluginCurrentPage = 1;
const savedPluginPageSize = parseInt(localStorage.getItem('panrelay_plugin_pagesize'), 10);
let pluginPageSize = (savedPluginPageSize && [15, 30, 50, 100].includes(savedPluginPageSize)) ? savedPluginPageSize : 15;

function handlePluginPageSizeChange(val) {
    const size = parseInt(val, 10);
    if (size > 0) {
        pluginPageSize = size;
        try {
            localStorage.setItem('panrelay_plugin_pagesize', String(pluginPageSize));
        } catch (e) {}
        pluginCurrentPage = 1;
        renderPluginTable();
    }
}
window.handlePluginPageSizeChange = handlePluginPageSizeChange;

function handlePluginSort(field) {
    if (pluginSortBy === field) {
        pluginOrder = pluginOrder === 'asc' ? 'desc' : 'asc';
    } else {
        pluginSortBy = field;
        pluginOrder = (field === 'name' || field === 'description') ? 'asc' : 'desc';
    }
    try {
        localStorage.setItem('panrelay_plugin_sort_by', pluginSortBy);
        localStorage.setItem('panrelay_plugin_order', pluginOrder);
    } catch (e) {}
    pluginCurrentPage = 1;
    sortPluginData();
    updatePluginSortIcons();
    renderPluginTable();
}

function sortPluginData() {
    if (!pluginSortBy) return;
    const factor = pluginOrder === 'asc' ? 1 : -1;
    currentPluginsData.sort((a, b) => {
        let valA, valB;

        if (pluginSortBy === 'health_status') {
            const rank = (p) => {
                const s = p.health?.status;
                return s === 'healthy' ? 3 : (s === 'no_data' ? 2 : (s === 'error' ? 1 : 0));
            };
            valA = rank(a);
            valB = rank(b);
        } else if (pluginSortBy === 'latency_ms') {
            valA = Number(a.health?.latency_ms) || 0;
            valB = Number(b.health?.latency_ms) || 0;
        } else if (pluginSortBy === 'checked_at') {
            valA = a.health?.checked_at ? new Date(a.health.checked_at).getTime() : 0;
            valB = b.health?.checked_at ? new Date(b.health.checked_at).getTime() : 0;
        } else if (pluginSortBy === 'is_enabled') {
            valA = Boolean(a.is_enabled) ? 1 : 0;
            valB = Boolean(b.is_enabled) ? 1 : 0;
        } else if (pluginSortBy === 'name') {
            valA = String(a.display_name || a.name || '').toLowerCase();
            valB = String(b.display_name || b.name || '').toLowerCase();
        } else if (pluginSortBy === 'id') {
            valA = String(a.name || a.id || '').toLowerCase();
            valB = String(b.name || b.id || '').toLowerCase();
        } else {
            valA = String(a[pluginSortBy] || '').toLowerCase();
            valB = String(b[pluginSortBy] || '').toLowerCase();
        }

        if (valA < valB) return -1 * factor;
        if (valA > valB) return 1 * factor;
        return 0;
    });
}

function updatePluginSortIcons() {
    const iconMap = {
        'id': 'pluginSortIconId',
        'name': 'pluginSortIconName',
        'is_enabled': 'pluginSortIconIsEnabled',
        'health_status': 'pluginSortIconHealthStatus',
        'latency_ms': 'pluginSortIconLatencyMs',
        'checked_at': 'pluginSortIconCheckedAt',
        'description': 'pluginSortIconDescription'
    };

    Object.entries(iconMap).forEach(([field, elementId]) => {
        const iconEl = document.getElementById(elementId);
        if (!iconEl) return;
        if (pluginSortBy === field) {
            iconEl.textContent = pluginOrder === 'asc' ? '↑' : '↓';
            iconEl.className = 'text-blue-600 font-bold ml-0.5';
        } else {
            iconEl.textContent = '↕';
            iconEl.className = 'text-slate-300 ml-0.5';
        }
    });
}

window.handlePluginSort = handlePluginSort;

async function loadPlugins() {
    const tbody = document.getElementById('pluginTableBody');
    const statCounts = document.getElementById('statPluginCounts');

    try {
        const response = await fetch('/admin/api/plugins');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || '获取插件列表失败');
        }

        currentPluginsData = data.plugins || [];
        const total = data.total || currentPluginsData.length;
        const enabled = data.enabled_count || currentPluginsData.filter(p => p.is_enabled).length;

        if (statCounts) {
            statCounts.textContent = `${enabled} / ${total}`;
        }
        const tabBadgePlugins = document.getElementById('tabBadgePlugins');
        if (tabBadgePlugins) {
            tabBadgePlugins.textContent = `${enabled}/${total}`;
        }

        sortPluginData();
        updatePluginSortIcons();
        renderPluginTable();
    } catch (error) {
        console.error('加载插件失败:', error);
        showToast('加载插件失败: ' + error.message, 'danger');
    }
}

const pluginSelectionState = {
    selectedNames: new Set(),
    selectMode: 'page'
};

function toggleSelectPluginRow(name, checked) {
    pluginSelectionState.selectMode = 'page';
    if (checked) {
        pluginSelectionState.selectedNames.add(name);
    } else {
        pluginSelectionState.selectedNames.delete(name);
    }
    updatePluginBatchToolbar();
}

function toggleSelectPluginPage(checkbox) {
    const isChecked = checkbox.checked;
    pluginSelectionState.selectMode = 'page';
    const startIdx = (pluginCurrentPage - 1) * pluginPageSize;
    const endIdx = Math.min(startIdx + pluginPageSize, currentPluginsData.length);
    const pageItems = currentPluginsData.slice(startIdx, endIdx);

    pageItems.forEach(p => {
        if (isChecked) {
            pluginSelectionState.selectedNames.add(p.name);
        } else {
            pluginSelectionState.selectedNames.delete(p.name);
        }
    });
    renderPluginTable();
}

function selectPluginCurrentPage() {
    const total = currentPluginsData.length;
    const startIdx = (pluginCurrentPage - 1) * pluginPageSize;
    const endIdx = Math.min(startIdx + pluginPageSize, total);
    const pageItems = currentPluginsData.slice(startIdx, endIdx);

    pluginSelectionState.selectedNames.clear();
    pageItems.forEach(p => pluginSelectionState.selectedNames.add(p.name));
    pluginSelectionState.selectMode = 'page';
    renderPluginTable();

    if (typeof showToast === 'function') {
        showToast(`已切换为仅选本页（${pageItems.length} 项）`, 'info');
    }
}

function togglePluginSelectAllMode() {
    const total = currentPluginsData.length;
    const isAll = pluginSelectionState.selectMode === 'all';

    if (isAll) {
        selectPluginCurrentPage();
    } else {
        pluginSelectionState.selectMode = 'all';
        currentPluginsData.forEach(p => pluginSelectionState.selectedNames.add(p.name));
        renderPluginTable();
        if (typeof showToast === 'function') {
            showToast(`已全选全部 ${total} 项`, 'info');
        }
    }
}

function clearPluginSelection() {
    pluginSelectionState.selectedNames.clear();
    pluginSelectionState.selectMode = 'page';
    renderPluginTable();
}

function updatePluginBatchToolbar() {
    const toolbar = document.getElementById('pluginBatchToolbar');
    if (!toolbar) return;

    const count = pluginSelectionState.selectedNames.size;
    const total = currentPluginsData.length;
    const isAll = pluginSelectionState.selectMode === 'all';
    const startIdx = (pluginCurrentPage - 1) * pluginPageSize;
    const endIdx = Math.min(startIdx + pluginPageSize, total);
    const pageItems = currentPluginsData.slice(startIdx, endIdx);
    const pageCount = pageItems.length;
    const allPageSelected = pageCount > 0 && pageItems.every(p => pluginSelectionState.selectedNames.has(p.name));

    const summaryCountEl = document.getElementById('pluginSelectedCount');
    const scopeLink = document.getElementById('pluginScopeToggleLink');
    const selectPageCb = document.getElementById('selectPluginPageCheckbox');

    if (selectPageCb) {
        selectPageCb.checked = allPageSelected;
        selectPageCb.indeterminate = pageItems.some(p => pluginSelectionState.selectedNames.has(p.name)) && !allPageSelected;
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

async function batchEnablePlugins(isEnabled) {
    const names = Array.from(pluginSelectionState.selectedNames);
    const isAll = pluginSelectionState.selectMode === 'all';
    const actionStr = isEnabled ? '启用' : '停用';

    if (names.length === 0 && !isAll) {
        showToast(`请先选择要${actionStr}的插件`, 'warning');
        return;
    }

    const targetNames = isAll ? currentPluginsData.map(p => p.name) : names;

    try {
        const response = await fetch('/admin/api/plugins/batch-toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names: targetNames, is_enabled: isEnabled })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `已批量${actionStr}插件`, 'success');
            clearPluginSelection();
            loadPlugins();
        } else {
            showToast(data.message || `批量${actionStr}失败`, 'danger');
        }
    } catch (e) {
        showToast(`批量${actionStr}网络请求异常: ${e.message}`, 'danger');
    }
}

async function batchTestPlugins(forceAll = false) {
    const names = Array.from(pluginSelectionState.selectedNames);
    const isAll = forceAll || pluginSelectionState.selectMode === 'all';

    if (!forceAll && names.length === 0 && !isAll) {
        showToast('请先选择要测试的插件', 'warning');
        return;
    }

    const targetNames = (forceAll || isAll) ? currentPluginsData.map(p => p.name) : names;
    if (targetNames.length === 0) {
        showToast('暂无 Python 插件可供测试', 'warning');
        return;
    }
    showToast(`正在后台检测 ${targetNames.length} 个 Python 插件，请稍候...`, 'info');

    try {
        const response = await fetch('/admin/api/plugins/test-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names: targetNames })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || '批量测试插件完成', 'success');
            loadPlugins();
        } else {
            showToast(data.message || '批量测试插件失败', 'danger');
        }
    } catch (e) {
        showToast(`批量测试网络请求异常: ${e.message}`, 'danger');
    }
}

window.toggleSelectPluginRow = toggleSelectPluginRow;
window.toggleSelectPluginPage = toggleSelectPluginPage;
window.selectPluginCurrentPage = selectPluginCurrentPage;
window.togglePluginSelectAllMode = togglePluginSelectAllMode;
window.clearPluginSelection = clearPluginSelection;
window.batchEnablePlugins = batchEnablePlugins;
window.batchTestPlugins = batchTestPlugins;

function renderPluginTable() {
    const tbody = document.getElementById('pluginTableBody');
    if (!tbody) return;

    try {
        const totalCount = currentPluginsData.length;
        if (totalCount === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted py-5">
                        <i class="fas fa-puzzle-piece fa-2x mb-2 text-secondary d-block"></i>
                        暂未发现任何插件。请在 <code>src/plugins/</code> 目录下创建继承自 <code>BasePlugin</code> 的 Python 模块。
                    </td>
                </tr>
            `;
            renderPluginPagination(0, 1);
            updatePluginBatchToolbar();
            return;
        }

        const totalPages = Math.ceil(totalCount / pluginPageSize) || 1;
        if (pluginCurrentPage > totalPages) pluginCurrentPage = totalPages;
        if (pluginCurrentPage < 1) pluginCurrentPage = 1;

        const startIdx = (pluginCurrentPage - 1) * pluginPageSize;
        const endIdx = Math.min(startIdx + pluginPageSize, totalCount);
        const pageItems = currentPluginsData.slice(startIdx, endIdx);

        tbody.innerHTML = pageItems.map((p, idx) => {
            const globalIndex = startIdx + idx;
            const isEnabled = Boolean(p.is_enabled);
            const statusBadge = isEnabled
                ? `<span class="status-dot-badge is-enabled"><span class="dot"></span>已启用</span>`
                : `<span class="status-dot-badge is-disabled"><span class="dot"></span>已停用</span>`;
            const health = p.health || {};
            const hStatus = health.status || 'unknown';
            const hText = hStatus === 'healthy' ? '正常' : (hStatus === 'error' ? '异常' : (hStatus === 'no_data' ? '无数据' : '未检测'));
            const hStatusClassMap = {
                'healthy': 'health-normal',
                'error': 'health-error',
                'no_data': 'health-nodata',
                'unknown': 'health-unknown'
            };
            const hStatusIconMap = {
                'healthy': 'fa-check-circle',
                'error': 'fa-exclamation-circle',
                'no_data': 'fa-info-circle',
                'unknown': 'fa-minus-circle'
            };
            const hClass = hStatusClassMap[hStatus] || 'health-unknown';
            const hIcon = hStatusIconMap[hStatus] || 'fa-minus-circle';
            const healthBadge = `<span class="health-text-badge ${hClass}" title="${escapeHtml(health.message || '尚未检测')}"><i class="fas ${hIcon}"></i> ${escapeHtml(hText)}</span>`;

            const latencyMs = Number(health.latency_ms);
            const latencyDisplay = latencyMs > 0 ? `${latencyMs} ms` : '--';
            const checkedAtDisplay = formatPluginCheckedAt(health.checked_at);

            const toggleClass = isEnabled ? 'btn-success' : 'btn-danger';
            const toggleIcon = isEnabled ? 'fa-toggle-on' : 'fa-toggle-off';
            const toggleText = isEnabled ? '启用' : '停用';
            const nextEnabled = !isEnabled;
            const isChecked = pluginSelectionState.selectedNames.has(p.name);

            return `
                <tr>
                    <td class="text-center align-middle">
                        <input class="form-check-input plugin-row-checkbox" type="checkbox" data-name="${escapeHtml(p.name)}" ${isChecked ? 'checked' : ''} onchange="toggleSelectPluginRow('${escapeHtml(p.name)}', this.checked)">
                    </td>
                    <td class="text-center text-muted align-middle">${globalIndex + 1}</td>
                    <td class="align-middle">
                        <strong class="text-dark">${escapeHtml(p.display_name || p.name)}</strong>
                    </td>
                    <td class="text-center align-middle" id="statusBadge-${escapeHtml(p.name)}">${statusBadge}</td>
                    <td class="text-center align-middle">${healthBadge}</td>
                    <td class="text-center align-middle font-mono text-xs">${latencyDisplay}</td>
                    <td class="text-center align-middle text-xs text-slate-500">${checkedAtDisplay}</td>
                    <td class="align-middle text-muted small text-break" style="max-width: 260px;">
                        ${escapeHtml(p.description || '无说明')}
                    </td>
                    <td class="action-buttons text-center align-middle">
                        <div class="inline-flex items-center gap-1.5 justify-center">
                            <button class="btn btn-sm ${toggleClass}" onclick="togglePlugin('${escapeHtml(p.name)}', ${nextEnabled})" title="点击切换状态">
                                <i class="fas ${toggleIcon}"></i> ${toggleText}
                            </button>
                            <button class="btn btn-sm btn-info" onclick="openTestModal('${escapeHtml(p.name)}', '${escapeHtml(p.display_name || p.name)}', ${p.timeout || 6.0})" title="在线检索测试">
                                <i class="fas fa-vial"></i> 测试
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        renderPluginPagination(totalCount, totalPages);
        updatePluginBatchToolbar();

    } catch (err) {
        console.error('加载插件数据出错:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center text-danger py-4">
                        <i class="fas fa-exclamation-circle me-1"></i> 加载插件数据失败: ${escapeHtml(err.message)}
                    </td>
                </tr>
            `;
        }
        showToast(`加载插件失败: ${err.message}`, 'danger');
    }
}

function renderPluginPagination(totalCount, totalPages) {
    const selEl = document.getElementById('pluginPageSizeSelect');
    if (selEl) selEl.value = pluginPageSize;
    const curEl = document.getElementById('pluginCurrentPageNum');
    if (curEl) curEl.textContent = pluginCurrentPage;
    const totEl = document.getElementById('pluginTotalPageNum');
    if (totEl) totEl.textContent = totalPages;
    const cntEl = document.getElementById('pluginTotalCountNum');
    if (cntEl) cntEl.textContent = totalCount;
    const countEl = document.getElementById('pluginTotalCount');
    if (countEl) countEl.textContent = `共 ${totalCount} 条`;

    const controlsEl = document.getElementById('pluginPaginationControls');
    const jumpInput = document.getElementById('pluginJumpPageInput');
    if (jumpInput) {
        jumpInput.max = totalPages;
        jumpInput.value = pluginCurrentPage;
        jumpInput.disabled = totalPages <= 1;
    }
    const jumpBtn = document.getElementById('pluginJumpPageBtn');
    if (jumpBtn) {
        jumpBtn.disabled = totalPages <= 1;
    }

    if (!controlsEl) return;
    controlsEl.innerHTML = '';

    // Prev Button
    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${pluginCurrentPage === 1 ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
    prevBtn.innerHTML = '<i class="fas fa-chevron-left text-[10px]"></i>';
    prevBtn.disabled = pluginCurrentPage === 1;
    prevBtn.onclick = () => { pluginCurrentPage--; renderPluginTable(); };
    controlsEl.appendChild(prevBtn);

    // Page numbers
    for (let p = 1; p <= totalPages; p++) {
        if (totalPages > 7 && Math.abs(p - pluginCurrentPage) > 2 && p !== 1 && p !== totalPages) {
            if (p === 2 && pluginCurrentPage > 4) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'px-1 text-slate-400 text-xs';
                ellipsis.textContent = '...';
                controlsEl.appendChild(ellipsis);
            } else if (p === totalPages - 1 && pluginCurrentPage < totalPages - 3) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'px-1 text-slate-400 text-xs';
                ellipsis.textContent = '...';
                controlsEl.appendChild(ellipsis);
            }
            continue;
        }

        const pageBtn = document.createElement('button');
        pageBtn.type = 'button';
        pageBtn.className = `px-2.5 py-1 text-xs rounded-lg transition font-medium cursor-pointer ${p === pluginCurrentPage ? 'bg-blue-600 text-white shadow-2xs font-semibold' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`;
        pageBtn.textContent = p;
        pageBtn.onclick = () => { pluginCurrentPage = p; renderPluginTable(); };
        controlsEl.appendChild(pageBtn);
    }

    // Next Button
    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${pluginCurrentPage === totalPages ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
    nextBtn.innerHTML = '<i class="fas fa-chevron-right text-[10px]"></i>';
    nextBtn.disabled = pluginCurrentPage === totalPages;
    nextBtn.onclick = () => { pluginCurrentPage++; renderPluginTable(); };
    controlsEl.appendChild(nextBtn);
}

function handlePluginJumpPage() {
    const input = document.getElementById('pluginJumpPageInput');
    if (!input) return;
    const page = parseInt(input.value, 10);
    const totalPages = Math.ceil(currentPluginsData.length / pluginPageSize) || 1;
    if (page >= 1 && page <= totalPages) {
        pluginCurrentPage = page;
        renderPluginTable();
    } else {
        input.value = pluginCurrentPage;
    }
}
window.handlePluginJumpPage = handlePluginJumpPage;

function formatPluginCheckedAt(value) {
    if (!value) return '--';
    const date = new Date(String(value).replace(' ', 'T'));
    return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false });
}

async function togglePlugin(pluginName, isEnabled) {
    try {
        const response = await fetch(`/admin/api/plugins/${encodeURIComponent(pluginName)}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_enabled: isEnabled })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || '切换状态失败');
        }

        showToast(data.message || `插件 [${pluginName}] 状态已更新`, 'success');
        await loadPlugins();
    } catch (err) {
        showToast(`操作失败: ${err.message}`, 'danger');
        // 恢复 checkbox
        const chk = document.getElementById(`switch-${pluginName}`);
        if (chk) chk.checked = !isEnabled;
    }
}

async function enableAllPlugins() {
    if (!(await showConfirm('确定要启用所有 Python 插件扩展吗？', 'primary', '批量启用确认'))) return;
    const btn = document.getElementById('enableAllPluginsButton');
    if (btn) btn.disabled = true;
    try {
        const response = await fetch('/admin/api/plugins/enable-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        showToast(data.message || '全部插件已启用', 'success');
        await loadPlugins();
    } catch (err) {
        showToast(`全部启用失败: ${err.message}`, 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function disableAllPlugins() {
    if (!(await showConfirm('确定要【禁用】所有 Python 插件扩展吗？', 'danger', '批量禁用确认'))) return;
    const btn = document.getElementById('disableAllPluginsButton');
    if (btn) btn.disabled = true;
    try {
        const response = await fetch('/admin/api/plugins/disable-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        showToast(data.message || '全部插件已停用', 'warning');
        await loadPlugins();
    } catch (err) {
        showToast(`全部禁用失败: ${err.message}`, 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function testAllPlugins() {
    if (!(await showConfirm('确定要测试所有 Python 插件扩展吗？', 'primary', '批量测试确认'))) return;
    const btn = document.getElementById('testAllPluginsButton');
    let originalHtml = '';
    if (btn) {
        btn.disabled = true;
        originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 检测中...';
    }
    showToast('正在并发探测所有插件健康度...', 'info');
    try {
        const response = await fetch('/admin/api/plugins/test-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || '全部测试失败');
        }
        const toastType = (data.failed_count && data.failed_count > 0) ? 'warning' : 'success';
        showToast(data.message || '全部插件检测完成', toastType);
        await loadPlugins();
    } catch (err) {
        showToast(`全部测试失败: ${err.message}`, 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

async function checkPluginHealth(pluginName) {
    try {
        showToast(`正在探测插件 [${pluginName}] 的健康度...`, 'info', 2000);
        const response = await fetch(`/admin/api/plugins/${encodeURIComponent(pluginName)}/health`);
        const data = await response.json();
        if (data.healthy) {
            showToast(`插件 [${pluginName}] 健康检测正常: ${data.message || 'OK'}`, 'success');
        } else {
            showToast(`插件 [${pluginName}] 异常: ${data.message || '健康检测未通过'}`, 'warning');
        }
    } catch (err) {
        showToast(`探测插件异常: ${err.message}`, 'danger');
    }
}

function openTestModal(name, displayName, timeout) {
    document.getElementById('currentTestPluginName').value = name;
    document.getElementById('modalPluginName').textContent = name;
    document.getElementById('modalPluginDisplayName').textContent = displayName;
    document.getElementById('modalPluginTimeout').textContent = timeout;

    const resultArea = document.getElementById('pluginTestResultArea');
    if (resultArea) resultArea.classList.add('d-none');

    const modalEl = document.getElementById('testPluginModal');
    if (window.UIModal) {
        const modal = window.UIModal.getOrCreateInstance(modalEl);
        modal.show();
    } else {
        modalEl.classList.add('show');
        modalEl.style.display = 'block';
    }
}

async function runPluginTest() {
    const pluginName = document.getElementById('currentTestPluginName').value;
    const keywordInput = document.getElementById('pluginTestKeyword');
    const keyword = (keywordInput?.value || '仙逆').trim() || '仙逆';
    const btn = document.getElementById('startPluginTestBtn');
    const resultArea = document.getElementById('pluginTestResultArea');
    const statusAlert = document.getElementById('pluginTestStatusAlert');
    const tbody = document.getElementById('pluginTestTableBody');

    if (!pluginName) {
        showToast('未指定待测试插件', 'warning');
        return;
    }

    if (btn) btn.disabled = true;
    if (resultArea) resultArea.classList.remove('d-none');
    if (statusAlert) {
        statusAlert.className = 'alert alert-info py-2 px-3 small mb-2';
        statusAlert.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> 正在调用插件 [${escapeHtml(pluginName)}] 执行多关键词测试，优先词: "<strong>${escapeHtml(keyword)}</strong>"...`;
    }
    if (tbody) tbody.innerHTML = '';

    const startTime = performance.now();
    try {
        const response = await fetch(`/admin/api/plugins/${encodeURIComponent(pluginName)}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword })
        });
        const latencyMs = Math.round(performance.now() - startTime);
        const data = await response.json();

        if (!data.success) {
            statusAlert.className = 'alert alert-danger py-2 px-3 small mb-2';
            statusAlert.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> 测试失败 (${latencyMs}ms): ${escapeHtml(data.message || '未知异常')}`;
            return;
        }

        const results = data.results || [];
        statusAlert.className = results.length > 0
            ? 'alert alert-success py-2 px-3 small mb-2'
            : 'alert alert-warning py-2 px-3 small mb-2';
        statusAlert.innerHTML = results.length > 0
            ? `<i class="fas fa-check-circle me-1"></i> 使用关键词“${escapeHtml(data.keyword || keyword)}”测试成功！耗时: <strong>${latencyMs}ms</strong>，共获取到 <strong>${results.length}</strong> 条资源。`
            : `<i class="fas fa-info-circle me-1"></i> ${escapeHtml(data.message || '插件可调用，但轮询关键词均无结果。')}`;

        if (results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">该插件在此关键词下未返回任何有效资源。</td></tr>`;
        } else {
            tbody.innerHTML = results.map((item, idx) => `
                <tr>
                    <td class="text-center text-muted small">${idx + 1}</td>
                    <td>
                        <div class="fw-semibold text-break">${escapeHtml(item.title || item.name || '无标题')}</div>
                        ${item.datetime ? `<div class="text-muted small">${escapeHtml(item.datetime)}</div>` : ''}
                    </td>
                    <td>
                        <span class="badge bg-secondary">${escapeHtml(item.cloud_name || '其他')}</span>
                    </td>
                    <td>
                        <a href="${escapeHtml(item.share_link || item.url || '#')}" target="_blank" class="text-break small text-decoration-none">
                            ${escapeHtml(item.share_link || item.url || '')}
                        </a>
                        ${item.password ? `<span class="badge bg-light text-dark border ms-1">提取码: ${escapeHtml(item.password)}</span>` : ''}
                    </td>
                </tr>
            `).join('');
        }
    } catch (err) {
        if (statusAlert) {
            statusAlert.className = 'alert alert-danger py-2 px-3 small mb-2';
            statusAlert.innerHTML = `<i class="fas fa-times-circle me-1"></i> 请求异常: ${escapeHtml(err.message)}`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

window.loadPlugins = loadPlugins;
window.enableAllPlugins = enableAllPlugins;
window.disableAllPlugins = disableAllPlugins;
window.testAllPlugins = testAllPlugins;

document.addEventListener('DOMContentLoaded', () => {
    loadPlugins();
});
