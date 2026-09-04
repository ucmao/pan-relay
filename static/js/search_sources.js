/**
 * 统一检索源管理工作区：Tab 切换、Telegram 全局配置与频道列表治理。
 */
(function () {
    let tgChannels = [];
    let tgConfig = null;

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

        document.querySelectorAll('.source-tab-btn').forEach((btn) => {
            btn.classList.toggle('is-active', btn.getAttribute('data-tab-target') === normalized);
        });
        document.querySelectorAll('.source-tab-pane').forEach((pane) => {
            pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
        });

        if (updateHash && window.history?.replaceState) {
            window.history.replaceState(null, '', `#${normalized}`);
        }
        if (normalized === 'telegram') loadTgSearchConfig();
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
        switchTab(hash || queryTab || 'api', false);
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

    function renderTgChannels() {
        const tbody = document.getElementById('tgChannelTableBody');
        if (!tbody) return;
        if (tgChannels.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">暂无频道，请点击“新增频道”添加</td></tr>';
            updateTgKPI();
            return;
        }

        tbody.innerHTML = tgChannels.map((item, index) => {
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

            return `
                <tr class="${rowClass}">
                    <td class="text-center">${index + 1}</td>
                    <td class="text-center">${enableBadge}</td>
                    <td class="text-center">${healthBadge}</td>
                    <td>
                        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="font-mono text-xs text-blue-600 hover:text-blue-700">@${channel}</a>
                    </td>
                    <td class="font-medium text-slate-800 text-xs">${title}</td>
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
    }

    async function loadTgSearchConfig() {
        try {
            const [configResponse, channelsResponse] = await Promise.all([
                fetch('/admin/api/tg-search-config'),
                fetch('/admin/api/tg-channels'),
            ]);
            const configData = await readJson(configResponse);
            const channelsData = await readJson(channelsResponse);
            tgConfig = configData.config || {};
            tgChannels = Array.isArray(channelsData.channels) ? channelsData.channels : [];

            const proxyEl = document.getElementById('tgProxyInput');
            const timeoutEl = document.getElementById('tgTimeoutInput');
            const workersEl = document.getElementById('tgMaxWorkersInput');
            if (proxyEl) proxyEl.value = tgConfig.proxy || '';
            if (timeoutEl) timeoutEl.value = tgConfig.timeout || 10;
            if (workersEl) workersEl.value = tgConfig.max_workers || 4;
            renderTgChannels();
        } catch (error) {
            console.error('加载 TG 配置失败:', error);
            showToast?.(`加载 TG 配置失败：${error.message}`, 'danger');
        }
    }

    async function saveTgSearchConfig() {
        const button = document.getElementById('saveTgSearchConfigBtn');
        if (button) button.disabled = true;
        const payload = {
            enabled: true,
            proxy: (document.getElementById('tgProxyInput')?.value || '').trim(),
            timeout: parseInt(document.getElementById('tgTimeoutInput')?.value || '10', 10),
            max_workers: parseInt(document.getElementById('tgMaxWorkersInput')?.value || '4', 10),
        };
        try {
            const data = await readJson(await fetch('/admin/api/tg-search-config', {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
            }));
            showToast?.(data.message || 'Telegram 抓取设置已保存', 'success');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`保存 TG 配置失败：${error.message}`, 'danger');
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
        if (button) button.disabled = true;
        showToast?.('正在并发检测全部 Telegram 频道，请稍候...', 'info');
        try {
            const data = await readJson(await fetch('/admin/api/tg-channels/test-all', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
            }));
            showToast?.(data.message, 'success');
            await loadTgSearchConfig();
        } catch (error) {
            showToast?.(`全部检测失败：${error.message}`, 'danger');
        } finally {
            if (button) button.disabled = false;
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
