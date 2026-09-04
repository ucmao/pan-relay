// 插件管理前端交互逻辑

let currentPluginsData = [];

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

        if (!tbody) return;

        if (currentPluginsData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11" class="text-center text-muted py-5">
                        <i class="fas fa-puzzle-piece fa-2x mb-2 text-secondary d-block"></i>
                        暂未发现任何插件。请在 <code>src/plugins/</code> 目录下创建继承自 <code>BasePlugin</code> 的 Python 模块。
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = currentPluginsData.map((p, idx) => {
            const isEnabled = Boolean(p.is_enabled);
            const statusBadge = isEnabled
                ? `<span class="plugin-status-badge is-enabled"><i class="fas fa-check-circle"></i> 已启用</span>`
                : `<span class="plugin-status-badge is-disabled"><i class="fas fa-pause-circle"></i> 已停用</span>`;

            return `
                <tr>
                    <td class="text-center text-muted align-middle">${idx + 1}</td>
                    <td class="text-center align-middle" id="statusBadge-${escapeHtml(p.name)}">${statusBadge}</td>
                    <td class="align-middle">
                        <span class="plugin-code-tag">${escapeHtml(p.name)}</span>
                    </td>
                    <td class="align-middle">
                        <strong class="text-dark">${escapeHtml(p.display_name || p.name)}</strong>
                    </td>
                    <td class="text-center align-middle text-muted small">v${escapeHtml(p.version || '1.0.0')}</td>
                    <td class="text-center align-middle text-muted small">${escapeHtml(p.author || '-')}</td>
                    <td class="text-center align-middle">
                        <span class="badge bg-light text-secondary border">${p.priority || 100}</span>
                    </td>
                    <td class="text-center align-middle text-muted small">${p.timeout || 6.0}s</td>
                    <td class="align-middle text-muted small text-break" style="max-width: 260px;">
                        ${escapeHtml(p.description || '无说明')}
                    </td>
                    <td class="text-center align-middle">
                        <label class="plugin-switch" title="${isEnabled ? '点击停用' : '点击启用'}">
                            <input type="checkbox" id="switch-${escapeHtml(p.name)}" ${isEnabled ? 'checked' : ''} onchange="togglePlugin('${escapeHtml(p.name)}', this.checked)">
                            <span class="plugin-slider"></span>
                        </label>
                    </td>
                    <td class="text-center align-middle">
                        <button class="btn btn-outline-primary btn-sm me-1" onclick="openTestModal('${escapeHtml(p.name)}', '${escapeHtml(p.display_name || p.name)}', ${p.timeout || 6.0})" title="在线检索测试">
                            <i class="fas fa-play me-1"></i> 测试
                        </button>
                        <button class="btn btn-outline-info btn-sm" onclick="checkPluginHealth('${escapeHtml(p.name)}')" title="健康检查探测">
                            <i class="fas fa-heartbeat me-1"></i> 探测
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

    } catch (err) {
        console.error('加载插件数据出错:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11" class="text-center text-danger py-4">
                        <i class="fas fa-exclamation-circle me-1"></i> 加载插件数据失败: ${escapeHtml(err.message)}
                    </td>
                </tr>
            `;
        }
        showToast(`加载插件失败: ${err.message}`, 'danger');
    }
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

async function reloadPlugins() {
    const btn = document.getElementById('reloadPluginsButton');
    if (btn) btn.disabled = true;

    try {
        const response = await fetch('/admin/api/plugins/reload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.message || '热重载插件失败');
        }

        showToast(data.message || '插件目录重新扫描成功', 'success');
        await loadPlugins();
    } catch (err) {
        showToast(`重新扫描失败: ${err.message}`, 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function enableAllPlugins() {
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

document.addEventListener('DOMContentLoaded', () => {
    loadPlugins();
});
