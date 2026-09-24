function getFrontendDisplayNetdiskCheckboxes() {
    return Array.from(document.querySelectorAll('.frontend-display-netdisk-checkbox'));
}

function updateDynamicTransferStatusVisibility() {
    const panel = document.getElementById('dynamicTransferStatusPanel');
    const select = document.getElementById('frontendLinkModeSelect');
    const badge = document.getElementById('frontendLinkModeBadge');
    const kpiEl = document.getElementById('kpiDeliveryMode');
    const excelToggle = document.getElementById('allowExcelDownloadToggle');
    const excelSwitchLabel = document.getElementById('allowExcelDownloadSwitchLabel');
    const excelDesc = document.getElementById('excelDownloadDesc');
    const excelContainer = document.getElementById('excelDownloadSettingContainer');

    const mode = select ? select.value : 'copy';
    const isView = mode === 'view';

    if (kpiEl) {
        kpiEl.textContent = isView ? '动态转存' : '原始链接';
    }
    if (badge) {
        badge.textContent = isView ? '动态转存模式' : '原始链接模式';
        badge.className = `badge ${isView ? 'badge-warning' : 'badge-info'} text-[10px]`;
    }
    if (panel) {
        panel.classList.toggle('d-none', !isView);
    }

    // 联动处理 Excel 下载导出配置
    if (excelToggle && excelSwitchLabel) {
        if (isView) {
            excelToggle.disabled = true;
            excelSwitchLabel.style.opacity = '0.55';
            excelSwitchLabel.style.cursor = 'not-allowed';
            excelSwitchLabel.setAttribute('title', '动态转存模式下已自动停用 Excel 批量导出');
        } else {
            excelToggle.disabled = false;
            excelSwitchLabel.style.opacity = '1';
            excelSwitchLabel.style.cursor = '';
            excelSwitchLabel.setAttribute('title', '切换 Excel 导出按钮');
        }
    }
    if (excelDesc) {
        if (isView) {
            excelDesc.innerHTML = '<span class="text-amber-600 dark:text-amber-500 font-medium inline-flex items-center gap-1.5"><i class="fas fa-lock text-[11px]"></i>当前为动态转存模式，为保障单条资源转存收益，已自动禁用导出</span>';
        } else {
            excelDesc.textContent = '允许访客将前台搜索列表结果导出为表格';
        }
    }
    if (excelContainer) {
        excelContainer.classList.toggle('opacity-90', isView);
    }
}

function bindFrontendLinkModeEvents() {
    const select = document.getElementById('frontendLinkModeSelect');
    if (select) {
        select.addEventListener('change', updateDynamicTransferStatusVisibility);
    }
}

function switchSystemTab(target, updateHash = true) {
    const validTabs = ['storage', 'ads', 'security', 'credentials', 'strategy', 'api', 'frontend'];
    const normalized = validTabs.includes(target) ? target : 'storage';
    try {
        localStorage.setItem('panrelay_system_tab', normalized);
    } catch (e) {}

    const tabBtns = document.querySelectorAll('[data-system-tab-target]');
    if (tabBtns.length === 0) return;

    tabBtns.forEach((b) => {
        b.classList.toggle('is-active', b.getAttribute('data-system-tab-target') === normalized);
    });
    document.querySelectorAll('.system-tab-pane').forEach((pane) => {
        pane.classList.toggle('is-active', pane.id === `tab-pane-${normalized}`);
    });

    if (updateHash && window.history?.replaceState) {
        window.history.replaceState(null, '', `#${normalized}`);
    }
}

function bindSystemTabEvents() {
    document.querySelectorAll('[data-system-tab-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-system-tab-target');
            switchSystemTab(target, true);
        });
    });

    const hash = (window.location.hash || '').replace('#', '').trim();
    const queryTab = new URLSearchParams(window.location.search).get('tab');
    let savedTab = null;
    try {
        savedTab = localStorage.getItem('panrelay_system_tab');
    } catch (e) {}
    switchSystemTab(hash || queryTab || savedTab || 'storage', false);
}

function bindCredentialTabEvents() {
    document.querySelectorAll('[data-cred-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-cred-target');
            try {
                localStorage.setItem('panrelay_cred_tab', target);
            } catch (e) {}
            document.querySelectorAll('[data-cred-target]').forEach((b) => b.classList.remove('is-active'));
            document.querySelectorAll('.credential-tab-pane').forEach((pane) => pane.classList.remove('is-active'));
            btn.classList.add('is-active');
            const targetPane = document.getElementById(`cred-pane-${target}`);
            if (targetPane) {
                targetPane.classList.add('is-active');
            }
        });
    });

    const queryCred = new URLSearchParams(window.location.search).get('cred');
    let savedCred = null;
    try {
        savedCred = localStorage.getItem('panrelay_cred_tab');
    } catch (e) {}
    const activeCred = queryCred || savedCred;
    if (activeCred) {
        const targetBtn = document.querySelector(`[data-cred-target="${activeCred}"]`);
        if (targetBtn) {
            targetBtn.click();
        }
    }
}

function renderDynamicTransferStatuses(statuses, summary) {
    const summaryEl = document.getElementById('dynamicTransferStatusSummary');
    const gridEl = document.getElementById('dynamicTransferStatusGrid');
    const manageLink = document.getElementById('dynamicTransferManageLink');

    const safeStatuses = Array.isArray(statuses) ? statuses : [];
    const enabledCount = Number(summary?.enabled_count || 0);
    const totalCount = Number(summary?.total_count || safeStatuses.length || 5);

    const credentialsTabBadge = document.getElementById('credentialsTabBadge');
    if (credentialsTabBadge) {
        credentialsTabBadge.textContent = String(enabledCount);
    }

    if (summaryEl) {
        summaryEl.textContent = `(${enabledCount}/${totalCount} 已就绪)`;
    }

    if (manageLink) {
        manageLink.onclick = (e) => {
            const credMainTabBtn = document.querySelector('[data-system-tab-target="credentials"]');
            if (credMainTabBtn) {
                e.preventDefault();
                credMainTabBtn.click();
            }
        };
    }

    if (gridEl) {
        const cloudTargetMap = {
            '百度网盘': 'baidu',
            '夸克网盘': 'quark',
            '阿里云盘': 'aliyun',
            'UC网盘': 'uc',
            '迅雷网盘': 'xunlei',
            '光鸭云盘': 'guangya',
            '悟空网盘': 'wukong',
            '移动云盘': 'caiyun',
        };

        gridEl.innerHTML = safeStatuses.map((item) => {
            const statusClass = item.status || 'missing';
            const badgeTextMap = {
                enabled: '已启用',
                invalid: '异常',
                missing: '未配置',
            };
            const badgeText = badgeTextMap[statusClass] || '未配置';
            const targetKey = cloudTargetMap[item.cloud_name] || '';
            const isEnabled = statusClass === 'enabled';
            const isInvalid = statusClass === 'invalid';

            let pillClass = 'bg-slate-100/90 text-slate-500 border-slate-200/70 hover:bg-slate-200/70';
            let dotClass = 'bg-slate-400';
            if (isEnabled) {
                pillClass = 'bg-emerald-50 text-emerald-700 border-emerald-200/80 hover:bg-emerald-100/80';
                dotClass = 'bg-emerald-500';
            } else if (isInvalid) {
                pillClass = 'bg-amber-50 text-amber-700 border-amber-200/80 hover:bg-amber-100/80';
                dotClass = 'bg-amber-500';
            }

            return `
                <button type="button" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer shadow-2xs ${pillClass}" data-cred-nav="${targetKey}" title="${item.cloud_name}: ${badgeText} (${item.credential_type || ''})，点击前往配置">
                    <span class="w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0"></span>
                    <span>${item.cloud_name}</span>
                    <span class="text-[10px] opacity-75 font-normal">${badgeText}</span>
                </button>
            `;
        }).join('');

        gridEl.querySelectorAll('[data-cred-nav]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const targetKey = btn.getAttribute('data-cred-nav');
                if (!targetKey) return;

                const credMainTabBtn = document.querySelector('[data-system-tab-target="credentials"]');
                if (credMainTabBtn) {
                    credMainTabBtn.click();
                    const credSubTabBtn = document.querySelector(`[data-cred-target="${targetKey}"]`);
                    if (credSubTabBtn) {
                        credSubTabBtn.click();
                    }

                    setTimeout(() => {
                        const pane = document.getElementById(`cred-pane-${targetKey}`);
                        if (pane) {
                            pane.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            const textarea = pane.querySelector('textarea, input');
                            if (textarea) {
                                textarea.focus();
                            }
                        }
                    }, 120);
                } else {
                    window.location.href = `/admin/system-config?tab=credentials&cred=${targetKey}`;
                }
            });
        });
    }

    // 更新网盘 Sub-Tab 的健康状态点与状态文本
    const cloudKeyMap = {
        '百度网盘': { dotId: 'dot-baidu', textId: 'baiduStatusText' },
        '夸克网盘': { dotId: 'dot-quark', textId: 'quarkStatusText' },
        '阿里云盘': { dotId: 'dot-aliyun', textId: 'aliyunStatusText' },
        'UC网盘': { dotId: 'dot-uc', textId: 'ucStatusText' },
        '迅雷网盘': { dotId: 'dot-xunlei', textId: 'xunleiStatusText' },
        '光鸭云盘': { dotId: 'dot-guangya', textId: 'guangyaStatusText' },
        '悟空网盘': { dotId: 'dot-wukong', textId: 'wukongStatusText' },
        '移动云盘': { dotId: 'dot-caiyun', textId: 'caiyunStatusText' },
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
        checkbox.addEventListener('change', async () => {
            updateFrontendNetdiskSelectionUI();
            await saveFrontendDisplayNetdisks();
        });
    });
}

function updateApiConfigPanelsState(enabled) {
    const panels = [
        document.getElementById('apiDefaultStrategyPanel'),
        document.getElementById('transferAuthPanel')
    ];
    panels.forEach(panel => {
        if (!panel) return;
        if (enabled) {
            panel.classList.remove('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = false;
            });
        } else {
            panel.classList.add('opacity-50', 'pointer-events-none', 'select-none');
            panel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = true;
            });
        }
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
        updateApiConfigPanelsState(Boolean(data.enabled));

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
    updateApiConfigPanelsState(enabled);

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
        updateDynamicTransferStatusVisibility();
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

async function loadFrontendLinkCheckConfig() {
    try {
        const response = await fetch('/admin/api/frontend-link-check-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
        if (checkToggle) {
            checkToggle.checked = Boolean(data.enable_link_check !== false);
        }

        const enabledPans = Array.isArray(data.enabled_check_pans) ? data.enabled_check_pans : [];
        const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
        checkBoxes.forEach(cb => {
            cb.checked = enabledPans.includes(cb.value);
        });
        updateEnabledCheckPansCount();
    } catch (error) {
        console.error('加载前台测活配置失败:', error);
        showToast('加载前台测活配置失败，请检查后端日志。', 'danger');
    }
}

function updateLinkCheckPanelState() {
    const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
    const wrapper = document.getElementById('linkCheckNetdisksWrapper');
    if (!wrapper || !checkToggle) return;

    if (checkToggle.checked) {
        wrapper.classList.remove('d-none');
    } else {
        wrapper.classList.add('d-none');
    }
}

function updateEnabledCheckPansCount() {
    const countEl = document.getElementById('enabledCheckPansCount');
    const toggleBtn = document.getElementById('toggleAllLinkCheckNetdisksButton');
    const checkBoxes = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox'));
    const checkedCount = checkBoxes.filter(cb => cb.checked).length;

    if (countEl) {
        countEl.textContent = checkedCount;
    }
    if (toggleBtn) {
        toggleBtn.textContent = (checkBoxes.length > 0 && checkedCount === checkBoxes.length) ? '取消全选' : '全选';
    }
    updateLinkCheckPanelState();
}

async function selectMainstreamLinkCheckNetdisks() {
    const mainstreamList = ['百度网盘', '夸克网盘', '阿里云盘', 'UC网盘', '迅雷网盘', '光鸭云盘', '悟空网盘', '移动云盘'];
    const mainstreamSet = new Set(mainstreamList);
    const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
    checkBoxes.forEach(cb => {
        cb.checked = mainstreamSet.has(cb.value);
    });
    await saveFrontendLinkCheckConfig();
}

async function toggleAllLinkCheckNetdisks() {
    const checkBoxes = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox'));
    if (!checkBoxes.length) return;
    const allChecked = checkBoxes.every(cb => cb.checked);
    checkBoxes.forEach(cb => {
        cb.checked = !allChecked;
    });
    await saveFrontendLinkCheckConfig();
}

async function saveFrontendLinkCheckConfig() {
    const checkToggle = document.getElementById('enableFrontendLinkCheckToggle');
    const enable_link_check = checkToggle ? checkToggle.checked : true;

    const enabled_check_pans = Array.from(document.querySelectorAll('.link-check-netdisk-checkbox:checked')).map(cb => cb.value);
    updateEnabledCheckPansCount();

    try {
        const response = await fetch('/admin/api/frontend-link-check-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enable_link_check,
                enabled_check_pans,
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '前台测活与过滤配置保存成功', 'success');
        if (data.data && Array.isArray(data.data.enabled_check_pans)) {
            const checkBoxes = document.querySelectorAll('.link-check-netdisk-checkbox');
            checkBoxes.forEach(cb => {
                cb.checked = data.data.enabled_check_pans.includes(cb.value);
            });
            updateEnabledCheckPansCount();
        }
    } catch (error) {
        console.error('保存前台测活配置失败:', error);
        showToast(`保存前台测活配置失败: ${error.message}`, 'danger');
        await loadFrontendLinkCheckConfig();
    }
}

async function loadTransferTargetDirConfig() {
    try {
        const response = await fetch('/admin/api/transfer-target-dir');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const input = document.getElementById('transferTargetDirInput');
        const badge = document.getElementById('transferTargetDirBadge');
        const dir = (data.target_dir !== undefined && data.target_dir !== null) ? data.target_dir : 'Pan-Relay分享';

        if (input) {
            input.value = dir;
        }
        if (badge) {
            badge.textContent = dir ? dir : '根目录 (/)';
            badge.className = dir ? 'badge badge-info text-[10px]' : 'badge badge-secondary text-[10px]';
        }
    } catch (error) {
        console.error('加载转存目标目录配置失败:', error);
    }
}

async function saveTransferTargetDirConfig() {
    const input = document.getElementById('transferTargetDirInput');
    const target_dir = input ? input.value.trim() : 'Pan-Relay分享';

    try {
        const response = await fetch('/admin/api/transfer-target-dir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_dir })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '转存目标目录配置保存成功', 'success');
        await loadTransferTargetDirConfig();
    } catch (error) {
        console.error('保存转存目标目录配置失败:', error);
        showToast(`保存转存目标目录配置失败: ${error.message}`, 'danger');
        await loadTransferTargetDirConfig();
    }
}

async function selectMainstreamFrontendNetdisks() {
    const mainstreamList = ['百度网盘', '夸克网盘', '阿里云盘', 'UC网盘', '迅雷网盘', '光鸭云盘', '悟空网盘', '移动云盘'];
    const mainstreamSet = new Set(mainstreamList);
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    checkboxes.forEach((checkbox) => {
        checkbox.checked = mainstreamSet.has(checkbox.value);
    });
    updateFrontendNetdiskSelectionUI();
    await saveFrontendDisplayNetdisks();
}

async function toggleAllFrontendDisplayNetdisks() {
    const checkboxes = getFrontendDisplayNetdiskCheckboxes();
    const allChecked = checkboxes.length > 0 && checkboxes.every((checkbox) => checkbox.checked);
    checkboxes.forEach((checkbox) => {
        checkbox.checked = !allChecked;
    });
    updateFrontendNetdiskSelectionUI();
    await saveFrontendDisplayNetdisks();
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
    const enabledNetdisks = getFrontendDisplayNetdiskCheckboxes()
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value);

    if (enabledNetdisks.length === 0) {
        showToast('前端显示网盘至少需要保留一个。', 'warning');
        await loadFrontendDisplayNetdisks();
        return;
    }

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
        await loadFrontendDisplayNetdisks();
    }
}

async function loadFrontendLinkMode() {
    try {
        const response = await fetch('/admin/api/frontend-link-mode');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const select = document.getElementById('frontendLinkModeSelect');
        if (select) {
            select.value = data.mode || 'copy';
        }
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('加载前端出链模式失败:', error);
        showToast('加载前端出链模式失败，请检查后端日志。', 'danger');
    }
}

async function saveFrontendLinkMode() {
    const select = document.getElementById('frontendLinkModeSelect');
    const mode = select ? select.value : 'copy';

    if (select) select.disabled = true;
    try {
        const response = await fetch('/admin/api/frontend-link-mode', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '出链策略保存成功', 'success');
        updateDynamicTransferStatusVisibility();
    } catch (error) {
        console.error('保存前端出链模式失败:', error);
        showToast(`保存前端出链模式失败: ${error.message}`, 'danger');
    } finally {
        if (select) select.disabled = false;
    }
}

async function loadCookieConfig() {
    try {
        const response = await fetch('/admin/api/credential-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const baidu = document.getElementById('baiduCookie');
        if (baidu) baidu.value = data.baidu_cookie || '';
        const quark = document.getElementById('quarkCookie');
        if (quark) quark.value = data.quark_cookie || '';
        const aliyun = document.getElementById('aliyunToken');
        if (aliyun) aliyun.value = data.aliyun_token || '';
        const uc = document.getElementById('ucCookie');
        if (uc) uc.value = data.uc_cookie || '';
        const xunleiRefreshToken = document.getElementById('xunleiRefreshToken');
        if (xunleiRefreshToken) xunleiRefreshToken.value = data.xunlei_refresh_token || '';
        const xunleiCaptchaSign = document.getElementById('xunleiCaptchaSign');
        if (xunleiCaptchaSign) xunleiCaptchaSign.value = data.xunlei_captcha_sign || '';
        const xunleiUserId = document.getElementById('xunleiUserId');
        if (xunleiUserId) xunleiUserId.value = data.xunlei_user_id || '';
        const guangyaToken = document.getElementById('guangyaToken');
        if (guangyaToken) guangyaToken.value = data.guangya_token || '';
        const wukongCookie = document.getElementById('wukongCookie');
        if (wukongCookie) wukongCookie.value = data.wukong_cookie || '';
        const caiyunToken = document.getElementById('caiyunToken');
        if (caiyunToken) caiyunToken.value = data.caiyun_token || '';
        renderDynamicTransferStatuses(data.dynamic_transfer_statuses, data.dynamic_transfer_summary);
    } catch (error) {
        console.error('加载云盘凭证失败:', error);
    }
}

async function saveCookieConfig() {
    const saveButton = document.getElementById('saveCookieConfigBtn');
    const payload = {
        baidu_cookie: document.getElementById('baiduCookie') ? document.getElementById('baiduCookie').value.trim() : '',
        quark_cookie: document.getElementById('quarkCookie') ? document.getElementById('quarkCookie').value.trim() : '',
        aliyun_token: document.getElementById('aliyunToken') ? document.getElementById('aliyunToken').value.trim() : '',
        uc_cookie: document.getElementById('ucCookie') ? document.getElementById('ucCookie').value.trim() : '',
        xunlei_refresh_token: document.getElementById('xunleiRefreshToken') ? document.getElementById('xunleiRefreshToken').value.trim() : '',
        xunlei_captcha_sign: document.getElementById('xunleiCaptchaSign') ? document.getElementById('xunleiCaptchaSign').value.trim() : '',
        xunlei_user_id: document.getElementById('xunleiUserId') ? document.getElementById('xunleiUserId').value.trim() : '',
        guangya_token: document.getElementById('guangyaToken') ? document.getElementById('guangyaToken').value.trim() : '',
        wukong_cookie: document.getElementById('wukongCookie') ? document.getElementById('wukongCookie').value.trim() : '',
        caiyun_token: document.getElementById('caiyunToken') ? document.getElementById('caiyunToken').value.trim() : '',
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

async function loadSensitiveWordsConfig() {
    try {
        const response = await fetch('/admin/api/sensitive-words-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const inputToggle = document.getElementById('sensitiveWordsInputToggle');
        const outputToggle = document.getElementById('sensitiveWordsOutputToggle');
        const textarea = document.getElementById('sensitiveWordsTextarea');
        const countEl = document.getElementById('sensitiveWordsCount');

        if (inputToggle) inputToggle.checked = Boolean(config.input_enabled ?? true);
        if (outputToggle) outputToggle.checked = Boolean(config.output_enabled ?? true);

        updateSensitiveWordsBodyUiState(
            Boolean(config.input_enabled ?? true),
            Boolean(config.output_enabled ?? true)
        );

        const words = Array.isArray(config.words) ? config.words : [];
        if (textarea) {
            textarea.value = words.join('\n');
        }
        if (countEl) {
            countEl.textContent = String(words.length);
        }
    } catch (error) {
        console.error('加载敏感词配置失败:', error);
        showToast('加载敏感词配置失败，请检查后端日志。', 'danger');
    }
}

async function saveSensitiveWordsConfig() {
    const inputToggle = document.getElementById('sensitiveWordsInputToggle');
    const outputToggle = document.getElementById('sensitiveWordsOutputToggle');
    const textarea = document.getElementById('sensitiveWordsTextarea');
    const saveBtn = document.getElementById('saveSensitiveWordsConfigBtn');

    const wordsRaw = textarea ? textarea.value : '';
    const words = wordsRaw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    const inputEnabled = inputToggle ? inputToggle.checked : true;
    const outputEnabled = outputToggle ? outputToggle.checked : true;

    updateSensitiveWordsBodyUiState(inputEnabled, outputEnabled);

    const payload = {
        enabled: Boolean(inputEnabled || outputEnabled),
        input_enabled: inputEnabled,
        output_enabled: outputEnabled,
        words: words,
    };

    if (saveBtn) saveBtn.disabled = true;
    try {
        const response = await fetch('/admin/api/sensitive-words-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '敏感词配置保存成功', 'success');
        await loadSensitiveWordsConfig();
    } catch (error) {
        console.error('保存敏感词配置失败:', error);
        showToast(`保存敏感词配置失败: ${error.message}`, 'danger');
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

function bindSensitiveWordsTextareaEvents() {
    const textarea = document.getElementById('sensitiveWordsTextarea');
    const countEl = document.getElementById('sensitiveWordsCount');
    if (textarea && countEl) {
        textarea.addEventListener('input', () => {
            const words = textarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
            countEl.textContent = String(words.length);
        });
    }
}

async function loadAdFilterConfig() {
    try {
        const response = await fetch('/admin/api/ad-filter-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const globalToggle = document.getElementById('adFilterGlobalToggle');
        const modeSelect = document.getElementById('titleFilterModeSelect');
        const textarea = document.getElementById('adFilterTextarea');
        const countEl = document.getElementById('adFilterWordsCount');

        if (globalToggle) globalToggle.checked = Boolean(config.enabled ?? false);
        if (modeSelect) modeSelect.value = config.title_filter_mode || 'loose';

        updateAdFilterBodyUiState(Boolean(config.enabled ?? false));

        const keywords = Array.isArray(config.keywords) ? config.keywords : [];
        if (textarea) {
            textarea.value = keywords.join('\n');
        }
        if (countEl) {
            countEl.textContent = String(keywords.length);
        }
    } catch (error) {
        console.error('加载广告过滤配置失败:', error);
        showToast('加载广告过滤配置失败，请检查后端日志。', 'danger');
    }
}

async function saveAdFilterConfig() {
    const globalToggle = document.getElementById('adFilterGlobalToggle');
    const modeSelect = document.getElementById('titleFilterModeSelect');
    const textarea = document.getElementById('adFilterTextarea');

    const keywordsRaw = textarea ? textarea.value : '';
    const keywords = keywordsRaw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    const titleFilterMode = modeSelect ? modeSelect.value : 'loose';
    const isAdFilterEnabled = globalToggle ? globalToggle.checked : false;

    updateAdFilterBodyUiState(isAdFilterEnabled);

    const payload = {
        enabled: isAdFilterEnabled,
        title_filter_mode: titleFilterMode,
        keywords: keywords,
    };

    try {
        const response = await fetch('/admin/api/ad-filter-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '广告过滤与标题匹配配置保存成功', 'success');
        await loadAdFilterConfig();
    } catch (error) {
        console.error('保存广告过滤配置失败:', error);
        showToast(`保存广告过滤配置失败: ${error.message}`, 'danger');
    }
}

function bindAdFilterTextareaEvents() {
    const textarea = document.getElementById('adFilterTextarea');
    const countEl = document.getElementById('adFilterWordsCount');
    if (textarea && countEl) {
        textarea.addEventListener('input', () => {
            const keywords = textarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
            countEl.textContent = String(keywords.length);
        });
    }
}

async function loadCustomAdConfig() {
    try {
        const response = await fetch('/admin/api/custom-ad-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const config = data.config || {};

        const globalToggle = document.getElementById('customAdGlobalToggle');
        const isCustomAdEnabled = Boolean(config.enabled ?? false);
        if (globalToggle) globalToggle.checked = isCustomAdEnabled;

        updateCustomAdUiState(isCustomAdEnabled);

        const adUrls = config.ad_share_urls || {};
        const fieldMap = {
            quark: 'customAdQuarkUrl',
            uc: 'customAdUcUrl',
            baidu: 'customAdBaiduUrl',
            aliyun: 'customAdAliyunUrl',
            xunlei: 'customAdXunleiUrl',
            caiyun: 'customAdCaiyunUrl',
            guangya: 'customAdGuangyaUrl',
            wukong: 'customAdWukongUrl',
        };

        for (const [key, elementId] of Object.entries(fieldMap)) {
            const input = document.getElementById(elementId);
            if (input) {
                input.value = (adUrls[key] || '').trim();
            }
        }
    } catch (error) {
        console.error('加载自定义广告配置失败:', error);
        showToast('加载自定义广告配置失败，请检查后端日志。', 'danger');
    }
}

async function saveCustomAdConfig() {
    const globalToggle = document.getElementById('customAdGlobalToggle');

    const fieldMap = {
        quark: 'customAdQuarkUrl',
        uc: 'customAdUcUrl',
        baidu: 'customAdBaiduUrl',
        aliyun: 'customAdAliyunUrl',
        xunlei: 'customAdXunleiUrl',
        caiyun: 'customAdCaiyunUrl',
        guangya: 'customAdGuangyaUrl',
        wukong: 'customAdWukongUrl',
    };

    const adShareUrls = {};
    for (const [key, elementId] of Object.entries(fieldMap)) {
        const input = document.getElementById(elementId);
        adShareUrls[key] = input ? input.value.trim() : '';
    }

    const isCustomAdEnabled = globalToggle ? globalToggle.checked : false;
    updateCustomAdUiState(isCustomAdEnabled);

    const payload = {
        enabled: isCustomAdEnabled,
        ad_share_urls: adShareUrls,
        ad_share_url: adShareUrls.quark || adShareUrls.uc || '',
    };

    try {
        const response = await fetch('/admin/api/custom-ad-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '8大网盘自定义引流配置保存成功', 'success');
        await loadCustomAdConfig();
    } catch (error) {
        console.error('保存自定义广告配置失败:', error);
        showToast(`保存自定义广告配置失败: ${error.message}`, 'danger');
    }
}


function handleRetentionUnitChange() {
    const unitSelect = document.getElementById('storageRetentionUnitSelect');
    const valueInput = document.getElementById('storageRetentionValueInput');
    const intervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const intervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    if (!unitSelect || !valueInput) return;

    const unit = unitSelect.value;
    if (unit === 'minutes') {
        valueInput.min = '30';
        if (parseInt(valueInput.value || '0', 10) < 30) {
            valueInput.value = '30';
        }
        // 智能对齐：如果保留时长设为了分钟级，且当前扫描周期大于2小时，自动对齐为30分钟
        if (intervalUnitSelect && intervalValueInput) {
            if (intervalUnitSelect.value === 'days' || (intervalUnitSelect.value === 'hours' && parseInt(intervalValueInput.value || '0', 10) > 1)) {
                intervalUnitSelect.value = 'minutes';
                intervalValueInput.value = '30';
                intervalValueInput.min = '15';
            }
        }
    } else {
        valueInput.min = '1';
        if (parseInt(valueInput.value || '0', 10) < 1) {
            valueInput.value = '1';
        }
    }
    saveStorageCleanupConfig();
}

function handleCleanupIntervalUnitChange() {
    const intervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const intervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    if (!intervalUnitSelect || !intervalValueInput) return;

    const unit = intervalUnitSelect.value;
    if (unit === 'minutes') {
        intervalValueInput.min = '15';
        if (parseInt(intervalValueInput.value || '0', 10) < 15) {
            intervalValueInput.value = '30';
        }
    } else {
        intervalValueInput.min = '1';
        if (parseInt(intervalValueInput.value || '0', 10) < 1) {
            intervalValueInput.value = '1';
        }
    }
    saveStorageCleanupConfig();
}

function updateStorageCleanupUiState(enabled) {
    const body = document.getElementById('storageCleanupBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        const inputs = body.querySelectorAll('input:not(#storageCleanupGlobalToggle), select');
        inputs.forEach(input => {
            input.disabled = !enabled;
        });
    }
}

// 广告引流植入总开关 → 置灰 8 大网盘配置区
function updateCustomAdUiState(enabled) {
    const body = document.getElementById('customAdPanelsBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('input, button').forEach(el => { el.disabled = !enabled; });
    }
}

// 广告智能净化开关 → 置灰广告词库区
function updateAdFilterBodyUiState(enabled) {
    const body = document.getElementById('adFilterBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('textarea').forEach(el => { el.disabled = !enabled; });
    }
}

// 搜索输入拦截 + 输出结果净化同时关闭 → 置灰敏感词库区
function updateSensitiveWordsBodyUiState(inputEnabled, outputEnabled) {
    const enabled = inputEnabled || outputEnabled;
    const body = document.getElementById('sensitiveWordsBody');
    if (body) {
        if (!enabled) {
            body.classList.add('opacity-50', 'pointer-events-none');
        } else {
            body.classList.remove('opacity-50', 'pointer-events-none');
        }
        body.querySelectorAll('textarea').forEach(el => { el.disabled = !enabled; });
    }
}

async function loadStorageCleanupConfig() {
    try {
        const response = await fetch('/admin/api/storage-cleanup-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const resData = data.data || {};
        const config = resData.config || {};

        const globalToggle = document.getElementById('storageCleanupGlobalToggle');
        const retentionValueInput = document.getElementById('storageRetentionValueInput');
        const retentionUnitSelect = document.getElementById('storageRetentionUnitSelect');
        const retentionDaysInput = document.getElementById('storageRetentionDaysInput');
        const cleanupIntervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
        const cleanupIntervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
        const cleanupIntervalInput = document.getElementById('storageCleanupIntervalInput');
        const expiredCountEl = document.getElementById('expiredResourcesCount');

        const isEnabled = Boolean(config.enabled ?? true);
        if (globalToggle) globalToggle.checked = isEnabled;

        updateStorageCleanupUiState(isEnabled);

        if (retentionUnitSelect) {
            retentionUnitSelect.value = config.retention_unit || 'days';
        }
        if (retentionValueInput) {
            const val = config.retention_value ?? config.retention_days ?? 15;
            retentionValueInput.value = val;
            if (config.retention_unit === 'minutes') {
                retentionValueInput.min = '30';
            } else {
                retentionValueInput.min = '1';
            }
        }
        if (retentionDaysInput) {
            retentionDaysInput.value = config.retention_days || 15;
        }

        if (cleanupIntervalUnitSelect) {
            cleanupIntervalUnitSelect.value = config.cleanup_interval_unit || 'hours';
        }
        if (cleanupIntervalValueInput) {
            const intervalVal = config.cleanup_interval_value ?? config.auto_cleanup_interval_hours ?? 12;
            cleanupIntervalValueInput.value = intervalVal;
            if (config.cleanup_interval_unit === 'minutes') {
                cleanupIntervalValueInput.min = '15';
            } else {
                cleanupIntervalValueInput.min = '1';
            }
        }
        if (cleanupIntervalInput) cleanupIntervalInput.value = config.auto_cleanup_interval_hours || 12;

        if (expiredCountEl) {
            expiredCountEl.textContent = String(resData.expired_resources_count ?? 0);
        }
    } catch (error) {
        console.error('加载存储清理配置失败:', error);
        showToast('加载存储清理配置失败，请检查后端日志。', 'danger');
    }
}

async function saveStorageCleanupConfig() {
    const globalToggle = document.getElementById('storageCleanupGlobalToggle');
    const retentionValueInput = document.getElementById('storageRetentionValueInput');
    const retentionUnitSelect = document.getElementById('storageRetentionUnitSelect');
    const retentionDaysInput = document.getElementById('storageRetentionDaysInput');
    const cleanupIntervalValueInput = document.getElementById('storageCleanupIntervalValueInput');
    const cleanupIntervalUnitSelect = document.getElementById('storageCleanupIntervalUnitSelect');
    const cleanupIntervalInput = document.getElementById('storageCleanupIntervalInput');

    const unit = retentionUnitSelect?.value || 'days';
    let val = parseInt(retentionValueInput?.value || retentionDaysInput?.value || '15', 10);
    if (unit === 'minutes' && val < 30) {
        val = 30;
        if (retentionValueInput) retentionValueInput.value = '30';
        showToast('为保障访客保存体验与防网盘风控，保留时间最低为 30 分钟。已自动调整为 30 分钟。', 'warning');
    } else if (val < 1) {
        val = 1;
        if (retentionValueInput) retentionValueInput.value = '1';
    }

    const intervalUnit = cleanupIntervalUnitSelect?.value || 'hours';
    let intervalVal = parseInt(cleanupIntervalValueInput?.value || cleanupIntervalInput?.value || '12', 10);
    if (intervalUnit === 'minutes' && intervalVal < 15) {
        intervalVal = 15;
        if (cleanupIntervalValueInput) cleanupIntervalValueInput.value = '15';
        showToast('为保障系统性能与防网盘风控，扫描周期最低为 15 分钟。已自动调整为 15 分钟。', 'warning');
    } else if (intervalVal < 1) {
        intervalVal = 1;
        if (cleanupIntervalValueInput) cleanupIntervalValueInput.value = '1';
    }

    const isEnabled = globalToggle ? globalToggle.checked : true;
    updateStorageCleanupUiState(isEnabled);

    const payload = {
        enabled: isEnabled,
        clean_temp_shares: true,
        clean_old_resources: true,
        retention_unit: unit,
        retention_value: val,
        retention_days: unit === 'days' ? val : Math.max(1, Math.round((unit === 'hours' ? val * 60 : val) / 1440)),
        cleanup_interval_unit: intervalUnit,
        cleanup_interval_value: intervalVal,
        auto_cleanup_interval_hours: intervalUnit === 'hours' ? intervalVal : Math.max(1, Math.round((intervalUnit === 'minutes' ? intervalVal : intervalVal * 1440) / 60)),
    };

    try {
        const response = await fetch('/admin/api/storage-cleanup-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || '存储自动清理配置保存成功', 'success');
        await loadStorageCleanupConfig();
    } catch (error) {
        console.error('保存存储清理配置失败:', error);
        showToast(`保存存储清理配置失败: ${error.message}`, 'danger');
    }
}

async function runStorageCleanupNow() {
    const expiredCount = document.getElementById('expiredResourcesCount')?.textContent || '0';
    const confirmPrompt = `确定要立即按当前策略执行全量存储清理吗？系统将自动回收已失效的临时分享并物理删除超过保留期的转存资源（当前检测到约 ${expiredCount} 条超期资源）。此操作不可撤销。`;

    const ok = window.confirmModal
        ? await window.confirmModal({
            title: '执行存储清理确认',
            message: confirmPrompt,
            confirmText: '立即执行',
            cancelText: '取消',
            type: 'danger'
        })
        : confirm(confirmPrompt);

    if (!ok) return;

    const runBtn = document.getElementById('runStorageCleanupBtn');
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin text-[10px] mr-1"></i> 清理中...';
    }

    try {
        const response = await fetch('/admin/api/storage-cleanup/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        const res = data.result || {};
        showToast(`清理完成: 临时分享清理 ${res.temp_shares_cleaned || 0} 条，过期转存清理 ${res.resources_cleaned || 0} 条`, 'success');
        await loadStorageCleanupConfig();
    } catch (error) {
        console.error('执行存储清理失败:', error);
        showToast(`执行存储清理失败: ${error.message}`, 'danger');
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="fas fa-trash-alt text-[10px] mr-1"></i> 立即执行清理';
        }
    }
}

function updateApiLivePreview() {
    const scopeEl = document.getElementById('searchScopeSelect');
    const limitEl = document.getElementById('searchApiLimitInput');
    const filterBadEl = document.getElementById('searchApiFilterBadToggle');
    const checkStatusEl = document.getElementById('searchApiCheckStatusToggle');

    const scopeLockEl = document.getElementById('searchScopeLockToggle');
    const limitLockEl = document.getElementById('searchLimitLockToggle');
    const filterBadLockEl = document.getElementById('searchFilterBadLockToggle');
    const checkStatusLockEl = document.getElementById('searchCheckStatusLockToggle');

    const previewEl = document.getElementById('apiDefaultLivePreview');

    if (!previewEl) return;

    const scope = scopeEl ? scopeEl.value : 'all';
    const limit = limitEl ? (limitEl.value || '50') : '50';
    const filterBad = filterBadEl ? filterBadEl.checked : false;
    const checkStatus = checkStatusEl ? checkStatusEl.checked : false;

    const scopeLocked = scopeLockEl ? scopeLockEl.checked : false;
    const limitLocked = limitLockEl ? limitLockEl.checked : false;
    const filterBadLocked = filterBadLockEl ? filterBadLockEl.checked : false;
    const checkStatusLocked = checkStatusLockEl ? checkStatusLockEl.checked : false;

    const origin = window.location.origin || (window.location.protocol + '//' + window.location.host);
    const protocolMatch = origin.match(/^(https?:\/\/)/);
    const protocolStr = protocolMatch ? protocolMatch[1] : 'https://';
    const hostPathStr = origin.replace(/^https?:\/\//, '') + '/api/v1/search';

    const renderParam = (name, val, isLocked, valClassNormal, valClassLocked) => {
        if (isLocked) {
            return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 bg-amber-100/90 text-amber-900 border border-amber-300 rounded-md font-extrabold shadow-2xs transition-all my-0.5" title="防护锁已锁定：外部请求无法强制穿透此参数规则">` +
                `<i class="fas fa-lock text-amber-600 text-[10px]"></i>` +
                `<span class="font-black text-amber-950">${name}</span>` +
                `<span class="text-amber-700 font-bold">=</span>` +
                `<span class="${valClassLocked}">${val}</span>` +
                `</span>`;
        }
        return `<span class="text-indigo-600 font-medium">${name}</span>` +
            `<span class="text-slate-400 font-bold px-0.5">=</span>` +
            `<span class="${valClassNormal}">${val}</span>`;
    };

    const scopeHtml = renderParam('scope', scope, scopeLocked, 'text-teal-700 font-medium', 'text-teal-800 font-black');
    const limitHtml = renderParam('limit', limit, limitLocked, 'text-blue-700 font-medium', 'text-blue-800 font-black');

    const filterBadNormal = filterBad ? 'text-emerald-700 font-bold' : 'text-rose-600 font-medium';
    const filterBadLockedStr = filterBad ? 'text-emerald-800 font-black' : 'text-rose-700 font-black';
    const filterBadHtml = renderParam('filter_bad', filterBad, filterBadLocked, filterBadNormal, filterBadLockedStr);

    const checkStatusNormal = checkStatus ? 'text-emerald-700 font-bold' : 'text-rose-600 font-medium';
    const checkStatusLockedStr = checkStatus ? 'text-emerald-800 font-black' : 'text-rose-700 font-black';
    const checkStatusHtml = renderParam('check_status', checkStatus, checkStatusLocked, checkStatusNormal, checkStatusLockedStr);

    previewEl.innerHTML = `<span class="px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 font-bold text-[11px] me-2 border border-sky-200">GET</span>` +
        `<span class="text-emerald-600 font-semibold">${protocolStr}</span>` +
        `<span class="text-slate-900 font-bold me-0.5">${hostPathStr}</span>` +
        `<span class="text-amber-600 font-bold">?</span>` +
        `<span class="text-indigo-600 font-medium">keyword</span><span class="text-slate-400 font-bold px-0.5">=</span><span class="text-amber-700 font-medium bg-amber-50 px-1 py-0.5 rounded border border-amber-200/60 me-0.5">{kw}</span>` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${scopeHtml}` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${limitHtml}` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${filterBadHtml}` +
        `<span class="text-slate-400 font-bold px-0.5">&amp;</span>` +
        `${checkStatusHtml}`;
}

async function loadApiModeConfig() {
    try {
        const response = await fetch('/admin/api/api-mode-config');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const cfg = data.config || {};

        const apiOnlyToggle = document.getElementById('apiOnlyToggle');
        const apiOnlyBadge = document.getElementById('apiOnlyBadge');
        const enableFrontendToggle = document.getElementById('enableFrontendToggle');
        const enableFrontendBadge = document.getElementById('enableFrontendBadge');
        const searchScopeSelect = document.getElementById('searchScopeSelect');
        const searchScopeBadge = document.getElementById('searchScopeBadge');
        const searchApiLimitInput = document.getElementById('searchApiLimitInput');
        const searchApiFilterBadToggle = document.getElementById('searchApiFilterBadToggle');
        const searchApiCheckStatusToggle = document.getElementById('searchApiCheckStatusToggle');

        const searchScopeLockToggle = document.getElementById('searchScopeLockToggle');
        const searchLimitLockToggle = document.getElementById('searchLimitLockToggle');
        const searchFilterBadLockToggle = document.getElementById('searchFilterBadLockToggle');
        const searchCheckStatusLockToggle = document.getElementById('searchCheckStatusLockToggle');

        const transferApiKeyInput = document.getElementById('transferApiKeyInput');
        const transferApiKeyBadge = document.getElementById('transferApiKeyBadge');
        const kpiApiMode = document.getElementById('kpiApiMode');

        if (apiOnlyToggle) apiOnlyToggle.checked = Boolean(cfg.api_only);
        if (apiOnlyBadge) {
            apiOnlyBadge.textContent = cfg.api_only ? '已开启' : '未开启';
            apiOnlyBadge.className = cfg.api_only ? 'badge badge-warning text-[10px]' : 'badge badge-secondary text-[10px]';
        }

        if (enableFrontendToggle) enableFrontendToggle.checked = Boolean(cfg.enable_frontend);
        if (enableFrontendBadge) {
            enableFrontendBadge.textContent = cfg.enable_frontend ? '已开启' : '已禁用';
            enableFrontendBadge.className = cfg.enable_frontend ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
        }

        if (searchScopeSelect) searchScopeSelect.value = cfg.search_scope || 'all';
        if (searchScopeBadge) {
            searchScopeBadge.textContent = (cfg.search_scope === 'all') ? '全网并发聚合' : '仅站长收益库';
            searchScopeBadge.className = (cfg.search_scope === 'all') ? 'badge badge-warning text-[10px]' : 'badge badge-info text-[10px]';
        }

        if (searchApiLimitInput) searchApiLimitInput.value = String(cfg.search_limit || 50);
        if (searchApiFilterBadToggle) searchApiFilterBadToggle.checked = Boolean(cfg.search_filter_bad);
        if (searchApiCheckStatusToggle) searchApiCheckStatusToggle.checked = Boolean(cfg.search_check_status);

        if (searchScopeLockToggle) searchScopeLockToggle.checked = Boolean(cfg.search_scope_lock);
        if (searchLimitLockToggle) searchLimitLockToggle.checked = Boolean(cfg.search_limit_lock);
        if (searchFilterBadLockToggle) searchFilterBadLockToggle.checked = Boolean(cfg.search_filter_bad_lock);
        if (searchCheckStatusLockToggle) searchCheckStatusLockToggle.checked = Boolean(cfg.search_check_status_lock);

        if (transferApiKeyInput) transferApiKeyInput.value = cfg.transfer_api_key || '';
        if (transferApiKeyBadge) {
            const hasKey = Boolean((cfg.transfer_api_key || '').trim());
            transferApiKeyBadge.textContent = hasKey ? '受密钥保护' : '公开调用';
            transferApiKeyBadge.className = hasKey ? 'badge badge-success text-[10px]' : 'badge badge-secondary text-[10px]';
        }

        if (kpiApiMode) {
            kpiApiMode.textContent = cfg.api_only ? 'API 无头' : '标准 Web';
            kpiApiMode.style.color = cfg.api_only ? 'var(--admin-warning-text)' : 'var(--admin-success-text)';
        }

        updateApiLivePreview();
    } catch (error) {
        console.error('加载 API 模式配置失败:', error);
    }
}

async function saveApiModeConfig() {
    const apiOnlyToggle = document.getElementById('apiOnlyToggle');
    const enableFrontendToggle = document.getElementById('enableFrontendToggle');
    const searchScopeSelect = document.getElementById('searchScopeSelect');
    const searchApiLimitInput = document.getElementById('searchApiLimitInput');
    const searchApiFilterBadToggle = document.getElementById('searchApiFilterBadToggle');
    const searchApiCheckStatusToggle = document.getElementById('searchApiCheckStatusToggle');

    const searchScopeLockToggle = document.getElementById('searchScopeLockToggle');
    const searchLimitLockToggle = document.getElementById('searchLimitLockToggle');
    const searchFilterBadLockToggle = document.getElementById('searchFilterBadLockToggle');
    const searchCheckStatusLockToggle = document.getElementById('searchCheckStatusLockToggle');

    const transferApiKeyInput = document.getElementById('transferApiKeyInput');

    updateApiLivePreview();

    const payload = {
        api_only: apiOnlyToggle ? apiOnlyToggle.checked : false,
        enable_frontend: enableFrontendToggle ? enableFrontendToggle.checked : true,
        search_scope: searchScopeSelect ? searchScopeSelect.value : 'all',
        search_limit: searchApiLimitInput ? (parseInt(searchApiLimitInput.value, 10) || 50) : 50,
        search_filter_bad: searchApiFilterBadToggle ? searchApiFilterBadToggle.checked : false,
        search_check_status: searchApiCheckStatusToggle ? searchApiCheckStatusToggle.checked : false,
        search_scope_lock: searchScopeLockToggle ? searchScopeLockToggle.checked : false,
        search_limit_lock: searchLimitLockToggle ? searchLimitLockToggle.checked : false,
        search_filter_bad_lock: searchFilterBadLockToggle ? searchFilterBadLockToggle.checked : false,
        search_check_status_lock: searchCheckStatusLockToggle ? searchCheckStatusLockToggle.checked : false,
        transfer_api_key: transferApiKeyInput ? transferApiKeyInput.value.trim() : '',
    };

    try {
        const response = await fetch('/admin/api/api-mode-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        showToast(data.message || 'API 模式配置保存成功', 'success');
        await loadApiModeConfig();
    } catch (error) {
        console.error('保存 API 模式配置失败:', error);
        showToast(`保存 API 模式配置失败: ${error.message}`, 'danger');
        await loadApiModeConfig();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindSystemTabEvents();
    bindCredentialTabEvents();
    bindFrontendNetdiskCheckboxEvents();
    bindFrontendLinkModeEvents();
    bindSensitiveWordsTextareaEvents();
    bindAdFilterTextareaEvents();
    loadApiModeConfig();
    loadPublicSearchApiConfig();
    loadAllowExcelDownloadConfig();
    loadFrontendLinkCheckConfig();
    loadTransferTargetDirConfig();
    loadFrontendDisplayNetdisks();
    loadFrontendLinkMode();
    loadSensitiveWordsConfig();
    loadAdFilterConfig();
    loadCustomAdConfig();
    loadStorageCleanupConfig();
    loadCookieConfig();
    updateDynamicTransferStatusVisibility();

    [
        'searchScopeSelect', 'searchApiLimitInput', 'searchApiFilterBadToggle', 'searchApiCheckStatusToggle',
        'searchScopeLockToggle', 'searchLimitLockToggle', 'searchFilterBadLockToggle', 'searchCheckStatusLockToggle'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateApiLivePreview);
            el.addEventListener('input', updateApiLivePreview);
        }
    });

    const transferApiKeyInput = document.getElementById('transferApiKeyInput');
    if (transferApiKeyInput) {
        transferApiKeyInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveApiModeConfig();
            }
        });
    }

    const transferTargetDirInput = document.getElementById('transferTargetDirInput');
    if (transferTargetDirInput) {
        transferTargetDirInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveTransferTargetDirConfig();
            }
        });
    }

    const customAdShareUrlInput = document.getElementById('customAdShareUrlInput');
    if (customAdShareUrlInput) {
        customAdShareUrlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveCustomAdConfig();
            }
        });
    }

    const saveCookieConfigBtn = document.getElementById('saveCookieConfigBtn');
    if (saveCookieConfigBtn) {
        saveCookieConfigBtn.addEventListener('click', saveCookieConfig);
    }
});

