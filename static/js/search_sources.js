/**
 * 统一搜索源管理工作区：Tab 切换、Telegram 全局配置与频道列表治理。
 */
(function () {
    let tgChannels = [];
    let tgConfig = null;
    const savedTgSortBy = localStorage.getItem('panrelay_tg_sort_by');
    let tgSortBy = savedTgSortBy || 'id';
    const savedTgOrder = localStorage.getItem('panrelay_tg_order');
    let tgOrder = (savedTgOrder === 'asc' || savedTgOrder === 'desc') ? savedTgOrder : 'asc';
    let tgCurrentPage = 1;
    const savedTgPageSize = parseInt(localStorage.getItem('panrelay_tg_pagesize'), 10);
    let tgPageSize = (savedTgPageSize && [15, 30, 50, 100].includes(savedTgPageSize)) ? savedTgPageSize : 15;

    function handleTgPageSizeChange(val) {
        const size = parseInt(val, 10);
        if (size > 0) {
            tgPageSize = size;
            try {
                localStorage.setItem('panrelay_tg_pagesize', String(tgPageSize));
            } catch (e) {}
            tgCurrentPage = 1;
            renderTgChannels();
        }
    }
    window.handleTgPageSizeChange = handleTgPageSizeChange;

    function handleTgSort(field) {
        if (tgSortBy === field) {
            tgOrder = tgOrder === 'asc' ? 'desc' : 'asc';
        } else {
            tgSortBy = field;
            tgOrder = (field === 'title' || field === 'channel') ? 'asc' : 'desc';
        }
        try {
            localStorage.setItem('panrelay_tg_sort_by', tgSortBy);
            localStorage.setItem('panrelay_tg_order', tgOrder);
        } catch (e) {}
        tgCurrentPage = 1;
        sortTgChannels();
        updateTgSortIcons();
        renderTgChannels();
    }

    function sortTgChannels() {
        if (!tgSortBy) return;
        const factor = tgOrder === 'asc' ? 1 : -1;
        tgChannels.sort((a, b) => {
            let valA, valB;

            if (tgSortBy === 'health_status') {
                const rank = (c) => {
                    const s = c.health?.status;
                    return s === 'healthy' ? 3 : (s === 'no_data' ? 2 : (s === 'error' ? 1 : 0));
                };
                valA = rank(a);
                valB = rank(b);
            } else if (tgSortBy === 'latency_ms') {
                valA = Number(a.health?.latency_ms) || 0;
                valB = Number(b.health?.latency_ms) || 0;
            } else if (tgSortBy === 'checked_at') {
                valA = a.health?.checked_at ? new Date(a.health.checked_at).getTime() : 0;
                valB = b.health?.checked_at ? new Date(b.health.checked_at).getTime() : 0;
            } else if (tgSortBy === 'is_enabled') {
                valA = Boolean(a.is_enabled) ? 1 : 0;
                valB = Boolean(b.is_enabled) ? 1 : 0;
            } else if (tgSortBy === 'title') {
                valA = String(a.title || a.channel || '').toLowerCase();
                valB = String(b.title || b.channel || '').toLowerCase();
            } else if (tgSortBy === 'id') {
                valA = String(a.channel || '').toLowerCase();
                valB = String(b.channel || '').toLowerCase();
            } else {
                valA = String(a[tgSortBy] || '').toLowerCase();
                valB = String(b[tgSortBy] || '').toLowerCase();
            }

            if (valA < valB) return -1 * factor;
            if (valA > valB) return 1 * factor;
            return 0;
        });
    }

    function updateTgSortIcons() {
        const iconMap = {
            'id': 'tgSortIconId',
            'title': 'tgSortIconTitle',
            'channel': 'tgSortIconChannel',
            'is_enabled': 'tgSortIconIsEnabled',
            'health_status': 'tgSortIconHealthStatus',
            'latency_ms': 'tgSortIconLatencyMs',
            'checked_at': 'tgSortIconCheckedAt'
        };

        Object.entries(iconMap).forEach(([field, elementId]) => {
            const iconEl = document.getElementById(elementId);
            if (!iconEl) return;
            if (tgSortBy === field) {
                iconEl.textContent = tgOrder === 'asc' ? '↑' : '↓';
                iconEl.className = 'text-blue-600 font-bold ml-0.5';
            } else {
                iconEl.textContent = '↕';
                iconEl.className = 'text-slate-300 ml-0.5';
            }
        });
    }

    window.handleTgSort = handleTgSort;

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value ?? '');
        return div.innerHTML;
    }

    async function readJson(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        return data;
    }

    function switchTab(tabName, updateHash = true) {
        if (!tabName) return;
        const validTabs = ['api', 'plugins', 'telegram'];
        const normalized = validTabs.includes(tabName) ? tabName : 'api';
        try {
            localStorage.setItem('panrelay_sources_tab', normalized);
        } catch (e) {}

        document.querySelectorAll('.source-tab-btn').forEach((btn) => {
            btn.classList.toggle('is-active', btn.getAttribute('data-tab-target') === normalized);
        });
        document.querySelectorAll('.source-tab-pane').forEach((pane) => {
            pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
        });

        if (normalized === 'telegram') loadTgSearchConfig();
        if (normalized === 'plugins' && typeof window.loadPlugins === 'function') window.loadPlugins();
        if (normalized === 'api' && typeof window.loadApiConfigs === 'function') window.loadApiConfigs();
    }

    function initTabNavigation() {
        document.querySelectorAll('.source-tab-btn').forEach((btn) => {
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                switchTab(btn.getAttribute('data-tab-target'), true);
            });
        });

        const hash = (window.location.hash || '').replace('#', '').trim();
        const queryTab = new URLSearchParams(window.location.search).get('tab');
        let savedTab = null;
        try {
            savedTab = localStorage.getItem('panrelay_sources_tab');
        } catch (e) {}

        switchTab(hash || queryTab || savedTab || 'api', false);
        window.addEventListener('hashchange', () => {
            const currentHash = (window.location.hash || '').replace('#', '').trim();
            if (currentHash) switchTab(currentHash, false);
        });
    }

    function updateTgKPI() {
        const total = tgChannels.length;
        const enabledCount = tgChannels.filter((item) => item.is_enabled).length;
        const proxyNote = tgConfig?.proxy ? ' · 代理启用' : '';
        const kpiStatus = document.getElementById('kpiTgStatus');
        const kpiDetail = document.getElementById('kpiTgDetail');
        const tabBadgeTg = document.getElementById('tabBadgeTg');

        if (kpiStatus) {
            kpiStatus.textContent = `${enabledCount} / ${total}`;
            kpiStatus.style.color = enabledCount > 0 ? 'var(--admin-success-text)' : 'var(--admin-text-muted)';
        }
        if (kpiDetail) kpiDetail.textContent = `总计 ${total} 个 · 启用 ${enabledCount} 个${proxyNote}`;
        if (tabBadgeTg) tabBadgeTg.textContent = `${enabledCount}/${total} 启用`;
    }

    function formatCheckedAt(value) {
        if (!value) return '--';
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false });
    }

    const tgSelectionState = {
        selectedChannels: new Set(),
        selectMode: 'page'
    };

    function toggleSelectTgRow(channel, checked) {
        tgSelectionState.selectMode = 'page';
        const decoded = decodeURIComponent(channel);
        if (checked) {
            tgSelectionState.selectedChannels.add(decoded);
        } else {
            tgSelectionState.selectedChannels.delete(decoded);
        }
        updateTgBatchToolbar();
    }

    function toggleSelectTgPage(checkbox) {
        const isChecked = checkbox.checked;
        tgSelectionState.selectMode = 'page';
        const startIdx = (tgCurrentPage - 1) * tgPageSize;
        const endIdx = Math.min(startIdx + tgPageSize, tgChannels.length);
        const pageItems = tgChannels.slice(startIdx, endIdx);

        pageItems.forEach(item => {
            if (isChecked) {
                tgSelectionState.selectedChannels.add(item.channel);
            } else {
                tgSelectionState.selectedChannels.delete(item.channel);
            }
        });
        renderTgChannels();
    }

    function selectTgCurrentPage() {
        const total = tgChannels.length;
        const startIdx = (tgCurrentPage - 1) * tgPageSize;
        const endIdx = Math.min(startIdx + tgPageSize, total);
        const pageItems = tgChannels.slice(startIdx, endIdx);

        tgSelectionState.selectedChannels.clear();
        pageItems.forEach(item => tgSelectionState.selectedChannels.add(item.channel));
        tgSelectionState.selectMode = 'page';
        renderTgChannels();

        if (typeof showToast === 'function') {
            showToast(`已切换为仅选本页（${pageItems.length} 项）`, 'info');
        }
    }

    function toggleTgSelectAllMode() {
        const total = tgChannels.length;
        const isAll = tgSelectionState.selectMode === 'all';

        if (isAll) {
            selectTgCurrentPage();
        } else {
            tgSelectionState.selectMode = 'all';
            tgChannels.forEach(item => tgSelectionState.selectedChannels.add(item.channel));
            renderTgChannels();
            if (typeof showToast === 'function') {
                showToast(`已全选全部 ${total} 项`, 'info');
            }
        }
    }

    function clearTgSelection() {
        tgSelectionState.selectedChannels.clear();
        tgSelectionState.selectMode = 'page';
        renderTgChannels();
    }

    function updateTgBatchToolbar() {
        const toolbar = document.getElementById('tgBatchToolbar');
        if (!toolbar) return;

        const count = tgSelectionState.selectedChannels.size;
        const total = tgChannels.length;
        const isAll = tgSelectionState.selectMode === 'all';
        const startIdx = (tgCurrentPage - 1) * tgPageSize;
        const endIdx = Math.min(startIdx + tgPageSize, total);
        const pageItems = tgChannels.slice(startIdx, endIdx);
        const pageCount = pageItems.length;
        const allPageSelected = pageCount > 0 && pageItems.every(item => tgSelectionState.selectedChannels.has(item.channel));

        const summaryCountEl = document.getElementById('tgSelectedCount');
        const scopeLink = document.getElementById('tgScopeToggleLink');
        const selectPageCb = document.getElementById('selectTgPageCheckbox');

        if (selectPageCb) {
            selectPageCb.checked = allPageSelected;
            selectPageCb.indeterminate = pageItems.some(item => tgSelectionState.selectedChannels.has(item.channel)) && !allPageSelected;
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

    async function batchEnableTgChannels(isEnabled) {
        const channels = Array.from(tgSelectionState.selectedChannels);
        const isAll = tgSelectionState.selectMode === 'all';
        const actionStr = isEnabled ? '启用' : '停用';

        if (channels.length === 0 && !isAll) {
            showToast(`请先选择要${actionStr}的频道`, 'warning');
            return;
        }

        const targetChannels = isAll ? tgChannels.map(item => item.channel) : channels;

        try {
            const response = await fetch('/admin/api/tg-channels/batch-toggle', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channels: targetChannels, is_enabled: isEnabled })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                showToast(data.message || `已批量${actionStr}频道`, 'success');
                clearTgSelection();
                loadTgChannels();
            } else {
                showToast(data.message || `批量${actionStr}失败`, 'danger');
            }
        } catch (e) {
            showToast(`批量${actionStr}网络请求异常: ${e.message}`, 'danger');
        }
    }

    async function batchDeleteTgChannels() {
        const channels = Array.from(tgSelectionState.selectedChannels);
        const isAll = tgSelectionState.selectMode === 'all';

        if (channels.length === 0 && !isAll) {
            showToast('请先选择要删除的频道', 'warning');
            return;
        }

        const targetChannels = isAll ? tgChannels.map(item => item.channel) : channels;
        if (!confirm(`确定要批量删除选中的 ${targetChannels.length} 个 Telegram 频道吗？该操作不可恢复！`)) {
            return;
        }

        try {
            const response = await fetch('/admin/api/tg-channels/batch-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channels: targetChannels })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                showToast(data.message || '已批量删除频道', 'success');
                clearTgSelection();
                loadTgChannels();
            } else {
                showToast(data.message || '批量删除失败', 'danger');
            }
        } catch (e) {
            showToast(`批量删除网络请求异常: ${e.message}`, 'danger');
        }
    }

    async function batchTestTgChannels(forceAll = false) {
        const channels = Array.from(tgSelectionState.selectedChannels);
        const isAll = forceAll || tgSelectionState.selectMode === 'all';

        if (!forceAll && channels.length === 0 && !isAll) {
            showToast('请先选择要检测连通性的频道', 'warning');
            return;
        }

        const targetChannels = (forceAll || isAll) ? tgChannels.map(item => item.channel) : channels;
        if (targetChannels.length === 0) {
            showToast('暂无 Telegram 频道可供测试', 'warning');
            return;
        }

        showToast(`正在后台测试 ${targetChannels.length} 个 Telegram 频道，请稍候...`, 'info');

        try {
            const response = await fetch('/admin/api/tg-channels/test-batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channels: targetChannels })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                showToast(data.message || '批量测试完成', 'success');
                loadTgChannels();
            } else {
                showToast(data.message || '批量测试失败', 'danger');
            }
        } catch (e) {
            showToast(`批量测试网络请求异常: ${e.message}`, 'danger');
        }
    }

    window.toggleSelectTgRow = toggleSelectTgRow;
    window.toggleSelectTgPage = toggleSelectTgPage;
    window.selectTgCurrentPage = selectTgCurrentPage;
    window.toggleTgSelectAllMode = toggleTgSelectAllMode;
    window.clearTgSelection = clearTgSelection;
    window.batchEnableTgChannels = batchEnableTgChannels;
    window.batchDeleteTgChannels = batchDeleteTgChannels;
    window.batchTestTgChannels = batchTestTgChannels;

    function renderTgChannels() {
        const tbody = document.getElementById('tgChannelTableBody');
        if (!tbody) return;
        const totalCount = tgChannels.length;
        if (totalCount === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">暂无频道，请点击“新增频道”添加</td></tr>';
            updateTgKPI();
            renderTgPagination(0, 1);
            updateTgBatchToolbar();
            return;
        }

        const totalPages = Math.ceil(totalCount / tgPageSize) || 1;
        if (tgCurrentPage > totalPages) tgCurrentPage = totalPages;
        if (tgCurrentPage < 1) tgCurrentPage = 1;

        const startIdx = (tgCurrentPage - 1) * tgPageSize;
        const endIdx = Math.min(startIdx + tgPageSize, totalCount);
        const pageItems = tgChannels.slice(startIdx, endIdx);

        tbody.innerHTML = pageItems.map((item, idx) => {
            const globalIndex = startIdx + idx;
            const health = item.health || {};
            const status = health.status || 'unknown';
            const statusText = health.status_text || '未检测';
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
            const hClass = hStatusClassMap[status] || 'health-unknown';
            const hIcon = hStatusIconMap[status] || 'fa-minus-circle';
            const healthBadge = `<span class="health-text-badge ${hClass}" title="${escapeHtml(health.message || '尚未检测')}"><i class="fas ${hIcon}"></i> ${escapeHtml(statusText)}</span>`;
            const latency = Number(health.latency_ms) > 0 ? `${health.latency_ms} ms` : '--';
            const nextEnabled = !item.is_enabled;
            const enableBadge = item.is_enabled
                ? '<span class="status-dot-badge is-enabled"><span class="dot"></span>已启用</span>'
                : '<span class="status-dot-badge is-disabled"><span class="dot"></span>已停用</span>';
            const toggleClass = item.is_enabled ? 'btn-success' : 'btn-danger';
            const toggleIcon = item.is_enabled ? 'fa-toggle-on' : 'fa-toggle-off';
            const toggleText = item.is_enabled ? '启用' : '停用';
            const rowClass = item.is_enabled ? '' : 'disabled-api';
            const channel = escapeHtml(item.channel);
            const title = escapeHtml(item.title || item.channel);
            const encodedChannel = encodeURIComponent(item.channel);
            const isChecked = tgSelectionState.selectedChannels.has(item.channel);

            return `
                <tr class="${rowClass}">
                    <td class="text-center">
                        <input class="form-check-input tg-row-checkbox" type="checkbox" data-channel="${encodedChannel}" ${isChecked ? 'checked' : ''} onchange="toggleSelectTgRow('${encodedChannel}', this.checked)">
                    </td>
                    <td class="text-center">${globalIndex + 1}</td>
                    <td class="font-medium text-slate-800 text-xs">${title}</td>
                    <td>
                        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="font-mono text-xs text-blue-600 hover:text-blue-700">@${channel}</a>
                    </td>
                    <td class="text-center">${enableBadge}</td>
                    <td class="text-center">${healthBadge}</td>
                    <td class="text-center">${latency}</td>
                    <td class="text-center text-xs text-slate-500">${formatCheckedAt(health.checked_at)}</td>
                    <td class="action-buttons text-center">
                        <div class="inline-flex items-center gap-1.5 justify-center">
                            <button class="btn btn-sm ${toggleClass}" onclick="toggleTgChannel('${encodedChannel}', ${nextEnabled})" title="点击切换状态">
                                <i class="fas ${toggleIcon}"></i> ${toggleText}
                            </button>
                            <button class="btn btn-sm btn-info" onclick="testTgChannel('${encodedChannel}', this)" title="测试频道"><i class="fas fa-vial"></i> 测试</button>
                            <button class="btn btn-sm btn-secondary" onclick="deleteTgChannel('${encodedChannel}')" title="删除频道"><i class="fas fa-trash"></i></button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
        updateTgKPI();
        renderTgPagination(totalCount, totalPages);
        updateTgBatchToolbar();
    }

    function renderTgPagination(totalCount, totalPages) {
        const selEl = document.getElementById('tgPageSizeSelect');
        if (selEl) selEl.value = tgPageSize;
        const curEl = document.getElementById('tgCurrentPageNum');
        if (curEl) curEl.textContent = tgCurrentPage;
        const totEl = document.getElementById('tgTotalPageNum');
        if (totEl) totEl.textContent = totalPages;
        const cntEl = document.getElementById('tgTotalCountNum');
        if (cntEl) cntEl.textContent = totalCount;
        const countEl = document.getElementById('tgTotalCount');
        if (countEl) countEl.textContent = `共 ${totalCount} 条`;

        const controlsEl = document.getElementById('tgPaginationControls');
        const jumpInput = document.getElementById('tgJumpPageInput');
        if (jumpInput) {
            jumpInput.max = totalPages;
            jumpInput.value = tgCurrentPage;
            jumpInput.disabled = totalPages <= 1;
        }
        const jumpBtn = document.getElementById('tgJumpPageBtn');
        if (jumpBtn) {
            jumpBtn.disabled = totalPages <= 1;
        }

        if (!controlsEl) return;
        controlsEl.innerHTML = '';

        // Prev Button
        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${tgCurrentPage === 1 ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
        prevBtn.innerHTML = '<i class="fas fa-chevron-left text-[10px]"></i>';
        prevBtn.disabled = tgCurrentPage === 1;
        prevBtn.onclick = () => { tgCurrentPage--; renderTgChannels(); };
        controlsEl.appendChild(prevBtn);

        // Page numbers
        for (let p = 1; p <= totalPages; p++) {
            if (totalPages > 7 && Math.abs(p - tgCurrentPage) > 2 && p !== 1 && p !== totalPages) {
                if (p === 2 && tgCurrentPage > 4) {
                    const ellipsis = document.createElement('span');
                    ellipsis.className = 'px-1 text-slate-400 text-xs';
                    ellipsis.textContent = '...';
                    controlsEl.appendChild(ellipsis);
                } else if (p === totalPages - 1 && tgCurrentPage < totalPages - 3) {
                    const ellipsis = document.createElement('span');
                    ellipsis.className = 'px-1 text-slate-400 text-xs';
                    ellipsis.textContent = '...';
                    controlsEl.appendChild(ellipsis);
                }
                continue;
            }

            const pageBtn = document.createElement('button');
            pageBtn.type = 'button';
            pageBtn.className = `px-2.5 py-1 text-xs rounded-lg transition font-medium cursor-pointer ${p === tgCurrentPage ? 'bg-blue-600 text-white shadow-2xs font-semibold' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`;
            pageBtn.textContent = p;
            pageBtn.onclick = () => { tgCurrentPage = p; renderTgChannels(); };
            controlsEl.appendChild(pageBtn);
        }

        // Next Button
        const nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = `px-2.5 py-1 text-xs rounded-lg border border-slate-200 transition ${tgCurrentPage === totalPages ? 'opacity-50 cursor-not-allowed bg-slate-50 text-slate-400' : 'bg-white text-slate-600 hover:bg-slate-50 cursor-pointer'}`;
        nextBtn.innerHTML = '<i class="fas fa-chevron-right text-[10px]"></i>';
        nextBtn.disabled = tgCurrentPage === totalPages;
        nextBtn.onclick = () => { tgCurrentPage++; renderTgChannels(); };
        controlsEl.appendChild(nextBtn);
    }

    function handleTgJumpPage() {
        const input = document.getElementById('tgJumpPageInput');
        if (!input) return;
        const page = parseInt(input.value, 10);
        const totalPages = Math.ceil(tgChannels.length / tgPageSize) || 1;
        if (page >= 1 && page <= totalPages) {
            tgCurrentPage = page;
            renderTgChannels();
        } else {
            input.value = tgCurrentPage;
        }
    }
    window.handleTgJumpPage = handleTgJumpPage;

    async function loadTgSearchConfig() {
        try {
            const [configResponse, channelsResponse] = await Promise.all([
                fetch('/admin/api/search-scheduler-config'),
                fetch('/admin/api/tg-channels'),
            ]);
            const configData = await readJson(configResponse);
            const channelsData = await readJson(channelsResponse);
            const scheduler = configData.config || {};
            tgConfig = scheduler.tg || {};
            tgChannels = Array.isArray(channelsData.channels) ? channelsData.channels : [];

            const proxyEl = document.getElementById('tgProxyInput');
            const timeoutEl = document.getElementById('tgTimeoutInput');
            const workersEl = document.getElementById('tgMaxWorkersInput');
            if (proxyEl) proxyEl.value = tgConfig.proxy || '';
            if (timeoutEl) timeoutEl.value = tgConfig.timeout || 10;
            if (workersEl) workersEl.value = tgConfig.max_workers || 4;
            const apiTimeoutEl = document.getElementById('apiTimeoutInput');
            const apiWorkersEl = document.getElementById('apiMaxWorkersInput');
            const pluginTimeoutEl = document.getElementById('pluginTimeoutInput');
            const pluginWorkersEl = document.getElementById('pluginMaxWorkersInput');
            if (apiTimeoutEl) apiTimeoutEl.value = scheduler.api?.timeout || 10;
            if (apiWorkersEl) apiWorkersEl.value = scheduler.api?.max_workers || 8;
            if (pluginTimeoutEl) pluginTimeoutEl.value = scheduler.plugin?.timeout || 10;
            if (pluginWorkersEl) pluginWorkersEl.value = scheduler.plugin?.max_workers || 6;
            sortTgChannels();
            updateTgSortIcons();
            renderTgChannels();
        } catch (error) {
            console.error('加载 TG 配置失败:', error);
            showToast?.(`加载 TG 配置失败：${error.message}`, 'danger');
        }
    }

    async function saveTgSearchConfig() {
        const button = document.getElementById('saveTgSearchConfigBtn');
        if (button) button.disabled = true;
        const payload = { api: { timeout: parseInt(document.getElementById('apiTimeoutInput')?.value || '10', 10), max_workers: parseInt(document.getElementById('apiMaxWorkersInput')?.value || '8', 10) }, tg: { enabled: true, proxy: (document.getElementById('tgProxyInput')?.value || '').trim(), timeout: parseInt(document.getElementById('tgTimeoutInput')?.value || '10', 10), max_workers: parseInt(document.getElementById('tgMaxWorkersInput')?.value || '4', 10) }, plugin: { timeout: parseInt(document.getElementById('pluginTimeoutInput')?.value || '10', 10), max_workers: parseInt(document.getElementById('pluginMaxWorkersInput')?.value || '6', 10) } };
        try {
            const data = await readJson(await fetch('/admin/api/search-scheduler-config', {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
            }));
            showToast?.(data.message || '搜索调度参数已保存', 'success');
            window.AppUI?.closeModal('#searchSettingsModal');
            window.AppUI?.closeModal('#tgSettingsModal');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`保存调度配置失败：${error.message}`, 'danger');
        } finally {
            if (button) button.disabled = false;
        }
    }

    async function addTgChannel() {
        const button = document.getElementById('addTgChannelButton');
        const input = document.getElementById('newTgChannelInput');
        const channel = (input?.value || '').trim();
        if (!channel) {
            showToast?.('请输入频道用户名或公开链接', 'warning');
            input?.focus();
            return;
        }
        if (button) button.disabled = true;
        try {
            const data = await readJson(await fetch('/admin/api/tg-channels', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel,
                    is_enabled: document.getElementById('newTgChannelEnabled')?.value !== 'false',
                }),
            }));
            showToast?.(data.message, 'success');
            if (input) input.value = '';
            window.AppUI?.closeModal('#addTgChannelModal');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`新增频道失败：${error.message}`, 'danger');
        } finally {
            if (button) button.disabled = false;
        }
    }

    async function toggleTgChannel(encodedChannel, isEnabled) {
        const channel = decodeURIComponent(encodedChannel);
        try {
            const data = await readJson(await fetch(`/admin/api/tg-channels/${encodedChannel}/enabled`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_enabled: isEnabled }),
            }));
            showToast?.(data.message, 'success');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`频道 @${channel} 状态更新失败：${error.message}`, 'danger');
        }
    }

    async function setAllTgChannelsEnabled(isEnabled) {
        const action = isEnabled ? '启用' : '停用';
        const modalType = isEnabled ? 'primary' : 'danger';
        if (!(await showConfirm(`确定要${action}全部 Telegram 频道吗？`, modalType, `批量${action}确认`))) return;
        const button = document.getElementById(isEnabled ? 'enableAllTgChannelsButton' : 'disableAllTgChannelsButton');
        if (button) button.disabled = true;
        try {
            const data = await readJson(await fetch(`/admin/api/tg-channels/${isEnabled ? 'enable-all' : 'disable-all'}`, { method: 'PUT' }));
            showToast?.(data.message, 'success');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`批量${action}失败：${error.message}`, 'danger');
        } finally {
            if (button) button.disabled = false;
        }
    }

    async function deleteTgChannel(encodedChannel) {
        const channel = decodeURIComponent(encodedChannel);
        if (!(await showConfirm(`确定要删除频道 @${channel} 吗？`, 'danger', '删除频道确认'))) return;
        try {
            const data = await readJson(await fetch(`/admin/api/tg-channels/${encodedChannel}`, { method: 'DELETE' }));
            showToast?.(data.message, 'success');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`删除频道失败：${error.message}`, 'danger');
        }
    }

    function renderTgTestResult(data) {
        const alert = document.getElementById('tgTestStatusAlert');
        const tbody = document.getElementById('tgTestTableBody');
        if (alert) {
            const type = data.success ? (data.count > 0 ? 'success' : 'warning') : 'danger';
            alert.className = `alert alert-${type} py-2 px-3 small mb-2`;
            alert.innerHTML = `${escapeHtml(data.message || '测试完成')}（耗时：${Number(data.latency_ms) || 0} ms）`;
        }
        const results = Array.isArray(data.results) ? data.results : [];
        if (!tbody) return;
        if (results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">本次检测未匹配到网盘资源</td></tr>';
            return;
        }
        tbody.innerHTML = results.map((item, index) => `
            <tr>
                <td class="text-center text-muted">${index + 1}</td>
                <td><span class="text-break">${escapeHtml(item.title || '无标题')}</span></td>
                <td><span class="badge bg-secondary">${escapeHtml(item.cloud_name || '未知')}</span></td>
                <td><a href="${escapeHtml(item.share_link || '#')}" target="_blank" rel="noopener noreferrer" class="text-break small text-decoration-none">${escapeHtml(item.share_link || '')}</a></td>
            </tr>`).join('');
    }

    async function testTgChannel(encodedChannel, triggerButton = null) {
        const channel = decodeURIComponent(encodedChannel);
        if (triggerButton) triggerButton.disabled = true;
        document.getElementById('tgTestTitle').textContent = `测试频道 @${channel}`;
        document.getElementById('tgTestStatusAlert').innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 正在轮询测试关键词，请稍候...';
        document.getElementById('tgTestTableBody').innerHTML = '';
        window.AppUI?.openModal('#tgTestModal');
        try {
            const response = await fetch(`/admin/api/tg-channels/${encodedChannel}/test`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.message || `HTTP error! status: ${response.status}`);
            renderTgTestResult(data);
            await loadTgSearchConfig();
        } catch (error) {
            renderTgTestResult({ success: false, message: error.message, latency_ms: 0, results: [] });
        } finally {
            if (triggerButton) triggerButton.disabled = false;
        }
    }

    async function testAllTgChannels() {
        if (!(await showConfirm('确定要检测全部 Telegram 频道吗？', 'primary', '批量检测确认'))) return;
        const button = document.getElementById('testAllTgChannelsButton');
        let originalHtml = '';
        if (button) {
            button.disabled = true;
            originalHtml = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 检测中...';
        }
        showToast?.('正在并发检测全部 Telegram 频道，请稍候...', 'info');
        try {
            const data = await readJson(await fetch('/admin/api/tg-channels/test-all', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
            }));
            const toastType = (data.failed_count && data.failed_count > 0) ? 'warning' : 'success';
            showToast?.(data.message || 'Telegram 频道检测完成', toastType);
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`全部检测失败：${error.message}`, 'danger');
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = originalHtml;
            }
        }
    }

    function setupKPIWatchers() {
        const syncBadges = () => {
            const kpiTotalEl = document.getElementById('kpiApiTotal');
            const kpiEnabledEl = document.getElementById('kpiApiEnabled');
            const kpiApiStat = document.getElementById('kpiApiStat');
            const tabBadgeApi = document.getElementById('tabBadgeApi');
            if (typeof apiConfigs !== 'undefined' && Array.isArray(apiConfigs)) {
                const total = apiConfigs.length;
                const enabled = apiConfigs.filter((api) => api.is_enabled).length;
                if (kpiApiStat) kpiApiStat.textContent = `${enabled} / ${total}`;
                if (tabBadgeApi) tabBadgeApi.textContent = `${enabled}/${total}`;
            } else if (kpiTotalEl && kpiEnabledEl && kpiTotalEl.textContent !== '--') {
                const total = parseInt(kpiTotalEl.textContent, 10) || 0;
                const enabled = parseInt(kpiEnabledEl.textContent, 10) || 0;
                if (kpiApiStat) kpiApiStat.textContent = `${enabled} / ${total}`;
                if (tabBadgeApi) tabBadgeApi.textContent = `${enabled}/${total}`;
            }
            const pluginCounts = document.getElementById('statPluginCounts');
            const pluginBadge = document.getElementById('tabBadgePlugins');
            if (pluginCounts && pluginBadge) pluginBadge.textContent = pluginCounts.textContent;
            updateTgKPI();
        };
        setTimeout(syncBadges, 300);
        setTimeout(syncBadges, 900);
        setInterval(syncBadges, 3000);
    }

    window.saveTgSearchConfig = saveTgSearchConfig;
    window.loadTgSearchConfig = loadTgSearchConfig;
    window.addTgChannel = addTgChannel;
    window.toggleTgChannel = toggleTgChannel;
    window.setAllTgChannelsEnabled = setAllTgChannelsEnabled;
    window.deleteTgChannel = deleteTgChannel;
    window.testTgChannel = testTgChannel;
    window.testAllTgChannels = testAllTgChannels;
    window.switchSourceTab = switchTab;

    document.addEventListener('DOMContentLoaded', () => {
        initTabNavigation();
        loadTgSearchConfig();
        setupKPIWatchers();
    });
})();
