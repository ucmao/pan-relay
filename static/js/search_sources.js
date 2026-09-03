/**
 * static/js/search_sources.js
 * 统一检索源管理工作区：Tab 切换驱动、Telegram 频道检索配置与联调、全源状态统计
 */

(function () {
    // 1. Tab 切换控制器
    function switchTab(tabName, updateHash = true) {
        if (!tabName) return;

        // 规范化 Tab 标识
        const validTabs = ['api', 'plugins', 'telegram'];
        const normalized = validTabs.includes(tabName) ? tabName : 'api';

        // 更新按钮高亮
        const tabBtns = document.querySelectorAll('.source-tab-btn');
        tabBtns.forEach((btn) => {
            const target = btn.getAttribute('data-tab-target');
            btn.classList.toggle('is-active', target === normalized);
        });

        // 切换内容显隐
        const panes = document.querySelectorAll('.source-tab-pane');
        panes.forEach((pane) => {
            pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
        });

        // 写入 URL Hash
        if (updateHash && window.history && window.history.replaceState) {
            window.history.replaceState(null, '', `#${normalized}`);
        }

        // 切换到 TG 时若尚未加载配置则触发加载
        if (normalized === 'telegram') {
            loadTgSearchConfig();
        }
    }

    function initTabNavigation() {
        const tabBtns = document.querySelectorAll('.source-tab-btn');
        tabBtns.forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const target = btn.getAttribute('data-tab-target');
                switchTab(target, true);
            });
        });

        // 优先读取 URL hash，其次读取 search params
        const hash = (window.location.hash || '').replace('#', '').trim();
        const urlParams = new URLSearchParams(window.location.search);
        const queryTab = urlParams.get('tab');
        const initialTab = hash || queryTab || 'api';

        switchTab(initialTab, false);

        window.addEventListener('hashchange', () => {
            const currentHash = (window.location.hash || '').replace('#', '').trim();
            if (currentHash) {
                switchTab(currentHash, false);
            }
        });
    }

    // 2. Telegram 频道配置与联调
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
                const channelsArr = Array.isArray(cfg.channels) ? cfg.channels : [];
                if (channelsEl) {
                    channelsEl.value = channelsArr.join(', ');
                    const testChanEl = document.getElementById('tgTestChannel');
                    if (testChanEl && !testChanEl.value && channelsArr.length > 0) {
                        testChanEl.value = channelsArr[0];
                    }
                }

                // 同步 KPI 与 Badge
                updateTgKPI(cfg.enabled, channelsArr.length, cfg.proxy);
            }
        } catch (error) {
            console.error('加载 TG 搜索配置失败:', error);
            if (typeof showToast === 'function') {
                showToast('加载 TG 搜索配置失败，请检查网络或后端状态', 'danger');
            }
        }
    }

    function updateTgKPI(enabled, channelCount, proxy) {
        const kpiStatus = document.getElementById('kpiTgStatus');
        const kpiDetail = document.getElementById('kpiTgDetail');
        const tabBadgeTg = document.getElementById('tabBadgeTg');

        if (kpiStatus) {
            kpiStatus.textContent = enabled ? '已启用' : '已停用';
            kpiStatus.style.color = enabled ? 'var(--admin-success-text)' : 'var(--admin-text-muted)';
        }

        if (kpiDetail) {
            const proxyNote = proxy ? ' · 代理启用' : '';
            kpiDetail.textContent = `监控 ${channelCount} 个频道${proxyNote}`;
        }

        if (tabBadgeTg) {
            tabBadgeTg.textContent = enabled ? `${channelCount} 个频道` : '已停用';
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
            if (typeof showToast === 'function') {
                showToast(data.message || 'Telegram 搜索配置已成功保存！', 'success');
            }
            await loadTgSearchConfig();
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(`保存 TG 配置失败: ${error.message}`, 'danger');
            }
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
            if (typeof showToast === 'function') {
                showToast('请先输入要测试的 Telegram 频道名称', 'warning');
            }
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

    // 3. 跨 Tab 指标监听与更新
    function setupKPIWatchers() {
        // 定期或在数据渲染后同步 API & Plugin 计数至 Badge
        const syncBadges = () => {
            // API
            const kpiTotalEl = document.getElementById('kpiApiTotal');
            const kpiEnabledEl = document.getElementById('kpiApiEnabled');
            const kpiApiStat = document.getElementById('kpiApiStat');
            const tabBadgeApi = document.getElementById('tabBadgeApi');

            if (typeof apiConfigs !== 'undefined' && Array.isArray(apiConfigs)) {
                const total = apiConfigs.length;
                const enabled = apiConfigs.filter((a) => a.is_enabled).length;
                if (kpiApiStat) kpiApiStat.textContent = `${enabled} / ${total}`;
                if (tabBadgeApi) tabBadgeApi.textContent = `${enabled}/${total}`;
            } else if (kpiTotalEl && kpiEnabledEl && kpiTotalEl.textContent !== '--') {
                const totalText = parseInt(kpiTotalEl.textContent, 10) || 0;
                const enabledText = parseInt(kpiEnabledEl.textContent, 10) || 0;
                if (kpiApiStat) kpiApiStat.textContent = `${enabledText} / ${totalText}`;
                if (tabBadgeApi) tabBadgeApi.textContent = `${enabledText}/${totalText}`;
            }

            // Plugins
            const pluginCountsEl = document.getElementById('statPluginCounts');
            const tabBadgePlugins = document.getElementById('tabBadgePlugins');
            if (pluginCountsEl && pluginCountsEl.textContent !== '0 / 0' && pluginCountsEl.textContent !== '-- / --') {
                if (tabBadgePlugins) tabBadgePlugins.textContent = pluginCountsEl.textContent;
            }
        };

        // 初始化延迟 300ms 和 800ms 执行两次同步以捕获异步加载的数据
        setTimeout(syncBadges, 300);
        setTimeout(syncBadges, 900);
        setInterval(syncBadges, 3000);
    }

    // 暴露方法至全局供内联 onclick 或其他脚本调用
    window.saveTgSearchConfig = saveTgSearchConfig;
    window.runTgTest = runTgTest;
    window.loadTgSearchConfig = loadTgSearchConfig;
    window.switchSourceTab = switchTab;

    document.addEventListener('DOMContentLoaded', () => {
        initTabNavigation();
        loadTgSearchConfig();
        setupKPIWatchers();
    });
})();
