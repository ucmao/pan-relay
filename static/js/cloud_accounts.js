// ==================== 网盘账号管理 ====================

let _currentCloudFilter = 'ALL';
let _accountsData = [];
const _testingAccountIds = new Set();

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatBytesParts(bytes) {
    if (!bytes || bytes <= 0) return { val: '0', unit: 'B' };
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const val = parseFloat((bytes / Math.pow(k, i)).toFixed(2));
    return { val, unit: sizes[i] };
}

async function loadCloudAccounts(cloud = null) {
    const tableBody = document.getElementById('accountsTableBody');
    if (!tableBody) return;

    if (cloud !== null) {
        _currentCloudFilter = cloud;
    }

    try {
        const url = _currentCloudFilter && _currentCloudFilter !== 'ALL'
            ? `/admin/api/accounts?cloud_name=${encodeURIComponent(_currentCloudFilter)}`
            : '/admin/api/accounts';
        const res = await fetch(url, { credentials: 'same-origin' });
        const data = await res.json();

        if (!data.success) {
            tableBody.innerHTML = `<tr><td colspan="9" class="p-8 text-center text-red-500 font-medium"><i class="fas fa-triangle-exclamation mr-2"></i>加载失败: ${data.message || '未知错误'}</td></tr>`;
            return;
        }

        _accountsData = data.accounts || [];
        const summary = data.summary || {};

        // 更新头部 KPI
        const totalEl = document.getElementById('statTotalAccounts');
        const validEl = document.getElementById('statValidAccounts');
        const storageEl = document.getElementById('statStorageSpace');
        const transfersEl = document.getElementById('statTransfers');

        if (totalEl) totalEl.textContent = summary.total_count || 0;
        if (validEl) {
            const valid = summary.valid_count || 0;
            const total = summary.total_count || 0;
            validEl.innerHTML = `${valid} <span class="text-xs font-normal text-slate-400 dark:text-slate-500">/ ${total}</span>`;
        }

        if (storageEl) {
            const usedParts = formatBytesParts(summary.used_space_bytes || 0);
            if (summary.total_space_bytes && summary.total_space_bytes > 0) {
                const totalParts = formatBytesParts(summary.total_space_bytes);
                storageEl.innerHTML = `${usedParts.val} <span class="text-xs font-normal text-slate-500 dark:text-slate-400">${usedParts.unit}</span> <span class="text-xs font-normal text-slate-400 dark:text-slate-500 mx-0.5">/</span> <span class="text-xs font-normal text-slate-400 dark:text-slate-500">${totalParts.val} ${totalParts.unit}</span>`;
            } else {
                storageEl.innerHTML = `${usedParts.val} <span class="text-xs font-normal text-slate-500 dark:text-slate-400">${usedParts.unit}</span> <span class="text-xs font-normal text-slate-400 dark:text-slate-500 mx-0.5">/</span> <span class="text-xs font-normal text-slate-400 dark:text-slate-500">不限量</span>`;
            }
        }

        const totalTransfers = _accountsData.reduce((acc, cur) => acc + (cur.transferred_count || 0), 0);
        if (transfersEl) {
            transfersEl.innerHTML = `${totalTransfers} <span class="text-xs font-normal text-slate-500 dark:text-slate-400">次</span>`;
        }

        renderAccountsTable(_accountsData);
    } catch (err) {
        console.error('加载账号池异常:', err);
        tableBody.innerHTML = `<tr><td colspan="9" class="p-8 text-center text-red-500"><i class="fas fa-circle-exclamation mr-2"></i>网络请求异常</td></tr>`;
    }
}

function renderStorageBarHtml(acc) {
    const unsupportedSpaceClouds = ['悟空网盘', '移动云盘', '迅雷网盘', '迅雷'];
    if (unsupportedSpaceClouds.includes(acc.cloud_name)) {
        return `
            <div class="w-40 flex flex-col gap-1.5 py-0.5" title="该网盘平台暂不支持接口探测容量">
                <div class="flex items-center justify-between text-xs leading-tight">
                    <span class="text-slate-400 dark:text-slate-500 font-medium">不支持容量</span>
                    <span class="text-xs text-slate-400">--</span>
                </div>
                <div class="w-full h-1.5 bg-slate-100 dark:bg-slate-700/60 rounded-full overflow-hidden">
                    <div class="h-full bg-slate-200 dark:bg-slate-600/40 rounded-full" style="width: 100%;"></div>
                </div>
            </div>
        `;
    }

    if (!acc.total_space_bytes || acc.total_space_bytes <= 0) {
        return `
            <div class="w-40 flex flex-col gap-1.5 py-0.5" title="尚未成功探测空间，请点击操作栏中的体检按钮">
                <div class="flex items-center justify-between text-xs leading-tight">
                    <span class="text-slate-400 dark:text-slate-500 font-medium">未探测容量</span>
                    <span class="text-xs text-slate-400">--</span>
                </div>
                <div class="w-full h-1.5 bg-slate-100 dark:bg-slate-700/60 rounded-full overflow-hidden">
                    <div class="h-full bg-slate-200 dark:bg-slate-600/30 rounded-full" style="width: 0%;"></div>
                </div>
            </div>
        `;
    }

    const usedStr = formatBytes(acc.used_space_bytes || 0);
    const totalStr = formatBytes(acc.total_space_bytes);
    const pct = Math.min(100, Math.round(((acc.used_space_bytes || 0) / acc.total_space_bytes) * 100));

    let barColorClass = 'bg-indigo-600 dark:bg-indigo-500';
    let textColor = 'text-indigo-600 dark:text-indigo-400';
    if (pct > 90) {
        barColorClass = 'bg-rose-500 dark:bg-rose-500';
        textColor = 'text-rose-600 dark:text-rose-400';
    } else if (pct > 75) {
        barColorClass = 'bg-amber-500 dark:bg-amber-500';
        textColor = 'text-amber-600 dark:text-amber-400';
    }

    return `
        <div class="w-40 flex flex-col gap-1.5 py-0.5" title="已用: ${usedStr} / 总量: ${totalStr} (${pct}%)">
            <div class="flex items-center justify-between text-xs leading-tight">
                <span class="font-semibold text-slate-700 dark:text-slate-200 truncate mr-1.5">${usedStr} <span class="font-normal text-slate-400 dark:text-slate-500 text-xs">/ ${totalStr}</span></span>
                <span class="font-bold text-xs ${textColor} flex-shrink-0">${pct}%</span>
            </div>
            <div class="w-full h-1.5 bg-slate-100 dark:bg-slate-700/80 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-300 ${barColorClass}" style="width: ${pct}%;"></div>
            </div>
        </div>
    `;
}

function renderStorageRingHtml(acc) {
    return renderStorageBarHtml(acc);
}

function renderAccountsTable(accounts) {
    const tableBody = document.getElementById('accountsTableBody');
    if (!tableBody) return;

    if (!accounts || accounts.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="p-12 text-center text-slate-400 dark:text-slate-500">
                    <div class="flex flex-col items-center justify-center gap-2">
                        <i class="fas fa-folder-open text-3xl text-slate-300 dark:text-slate-600 mb-1"></i>
                        <span class="text-sm font-medium">暂无网盘账号</span>
                        <span class="text-xs text-slate-400">点击右上角「添加网盘账号」按钮快速接入账号</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const cloudBadgeMap = {
        '夸克网盘': 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-300',
        '百度网盘': 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300',
        '阿里云盘': 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/40 dark:text-amber-300',
        'UC网盘': 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/40 dark:text-orange-300',
        '迅雷网盘': 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/40 dark:text-sky-300',
        '光鸭云盘': 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-900/40 dark:text-rose-300',
        '悟空网盘': 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/40 dark:text-purple-300',
        '移动云盘': 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300',
    };

    let html = '';
    accounts.forEach(acc => {
        const cloudClass = cloudBadgeMap[acc.cloud_name] || 'bg-slate-50 text-slate-700 border-slate-200';
        const isTesting = _testingAccountIds.has(acc.id);
        const isValid = acc.is_valid === 1;
        const isActive = acc.is_active === 1;

        // 圆形环形空间容量展示
        const spaceHtml = renderStorageRingHtml(acc);

        // 状态徽章
        let statusBadge = '';
        if (isTesting) {
            statusBadge = '<span class="w-16 shrink-0 justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400 flex items-center gap-1"><i class="fas fa-spinner fa-spin text-[9px]"></i>测活中...</span>';
        } else if (!isActive) {
            statusBadge = '<span class="inline-flex items-center w-16 shrink-0 justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400">已停用</span>';
        } else if (isValid) {
            statusBadge = '<span class="w-16 shrink-0 justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>正常</span>';
        } else {
            const reason = acc.invalid_reason ? escapeHtml(acc.invalid_reason) : '凭据失效';
            statusBadge = `<span class="w-16 shrink-0 justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400 flex items-center gap-1 cursor-help" title="${reason}"><span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>失效</span>`;
        }

        html += `
            <tr class="hover:bg-slate-50/60 dark:hover:bg-slate-700/30 transition-colors">
                <td class="p-3.5 pl-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-lg border ${cloudClass} shadow-2xs">
                        ${escapeHtml(acc.cloud_name)}
                    </span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <div class="font-bold text-slate-800 dark:text-white text-xs">${escapeHtml(acc.account_name)}</div>
                </td>
                <td class="p-3.5 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                    ${acc.username ? `<span class="font-medium text-xs">${escapeHtml(acc.username)}</span>` : '<span class="text-slate-400">--</span>'}
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <div class="flex items-center gap-2">
                        ${statusBadge}
                        <label class="plugin-switch" title="切换账号启用/停用">
                            <input type="checkbox" ${isActive ? 'checked' : ''} onchange="toggleAccountActive(${acc.id}, this.checked)">
                            <span class="plugin-switch-slider"></span>
                        </label>
                    </div>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    ${spaceHtml}
                </td>
                <td class="p-3.5 text-slate-500 whitespace-nowrap">
                    <div class="flex flex-col text-xs gap-0.5">
                        <span>优先级: <strong class="text-indigo-600 dark:text-indigo-400">${acc.priority}</strong></span>
                        <span>权  重: <strong>${acc.weight}</strong></span>
                    </div>
                </td>
                <td class="p-3.5 text-center font-bold text-slate-700 dark:text-slate-200 whitespace-nowrap">
                    ${acc.transferred_count || 0}
                </td>
                <td class="p-3.5 text-slate-400 text-xs whitespace-nowrap">
                    <div>用: ${acc.last_used_at ? acc.last_used_at.substring(5, 16) : '未调用'}</div>
                    <div>保: ${acc.last_keepalive_at ? acc.last_keepalive_at.substring(5, 16) : '未保活'}</div>
                </td>
                <td class="p-3.5 pr-4 text-right account-table-sticky-col whitespace-nowrap">
                    <div class="flex items-center justify-end gap-1.5">
                        <button class="btn btn-outline-secondary btn-xs account-test-btn" data-account-id="${acc.id}" onclick="testAccount(${acc.id}, this)" title="${isTesting ? '正在测活与探测容量...' : '测试连通性与空间'}" ${isTesting ? 'disabled' : ''}>
                            <i class="fas ${isTesting ? 'fa-spinner fa-spin text-indigo-600' : 'fa-stethoscope text-indigo-500'}"></i>
                        </button>
                        <button class="btn btn-outline-secondary btn-xs" onclick="openEditAccountModal(${acc.id})" title="编辑账号">
                            <i class="fas fa-pen-to-square"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-xs" onclick="deleteAccount(${acc.id})" title="删除账号">
                            <i class="fas fa-trash-can text-red-500"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function updateModalCredentialHintAndPlaceholder(cloudName) {
    const credInput = document.getElementById('modalCredential');
    const hintEl = document.getElementById('modalCredHint');
    if (!credInput || !hintEl) return;

    if (cloudName === '迅雷网盘') {
        credInput.rows = 5;
        credInput.placeholder = '{\n  "refresh_token": "a1.xxxx...",\n  "client_id": "YBJdb1UyFQJwh_nS",\n  "user_id": "1409868053",\n  "device_id": "2rvk4e3gkdnl7u1kl0k"\n}';
        hintEl.innerHTML = `
            <div class="mt-2 p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-amber-800 dark:text-amber-300 leading-relaxed text-xs">
                <div class="font-bold flex items-center gap-1.5 mb-1">
                    <i class="fas fa-triangle-exclamation text-amber-500"></i>
                    <span>迅雷网盘需填入完整 JSON 凭据</span>
                </div>
                <div class="whitespace-nowrap overflow-x-auto text-slate-600 dark:text-slate-400">
                    建议在终端运行 <code class="bg-amber-100/80 dark:bg-amber-900/60 px-1 py-0.5 rounded text-amber-900 dark:text-amber-200 font-mono select-all">python3 scripts/extract_xunlei_token.py</code> 并粘贴。
                </div>
            </div>
        `;
    } else if (cloudName === '阿里云盘') {
        credInput.rows = 4;
        credInput.placeholder = '请粘贴阿里云盘 Refresh Token...';
        hintEl.innerHTML = '<span class="text-slate-400">系统保存时将自动清洗首尾空白与换行符</span>';
    } else if (cloudName === '光鸭云盘') {
        credInput.rows = 4;
        credInput.placeholder = '请粘贴光鸭云盘 Access Token 或 Refresh Token...';
        hintEl.innerHTML = '<span class="text-slate-400">系统保存时将自动清洗首尾空白与换行符</span>';
    } else if (cloudName === '移动云盘') {
        credInput.rows = 4;
        credInput.placeholder = '请粘贴移动云盘 Authorization 或 Token...';
        hintEl.innerHTML = '<span class="text-slate-400">系统保存时将自动清洗首尾空白与换行符</span>';
    } else {
        credInput.rows = 4;
        credInput.placeholder = '请粘贴网盘 Cookie 或 Refresh Token...';
        hintEl.innerHTML = '<span class="text-slate-400">系统保存时将自动清洗首尾空白与换行符</span>';
    }
}

function openAddAccountModal() {
    const modal = document.getElementById('accountModal');
    const form = document.getElementById('accountForm');
    const title = document.getElementById('accountModalTitle');
    const idInput = document.getElementById('modalAccountId');
    const cloudSelect = document.getElementById('modalCloudName');

    if (!modal || !form) return;

    form.reset();
    idInput.value = '';
    title.innerHTML = '<i class="fas fa-user-plus text-indigo-600"></i> 添加网盘账号';

    if (_currentCloudFilter && _currentCloudFilter !== 'ALL' && cloudSelect) {
        cloudSelect.value = _currentCloudFilter;
    }

    updateModalCredentialHintAndPlaceholder(cloudSelect ? cloudSelect.value : '');

    modal.style.display = 'flex';
}

function openEditAccountModal(accountId) {
    const account = _accountsData.find(a => a.id === accountId);
    if (!account) return;

    const modal = document.getElementById('accountModal');
    const title = document.getElementById('accountModalTitle');
    const idInput = document.getElementById('modalAccountId');
    const cloudSelect = document.getElementById('modalCloudName');
    const nameInput = document.getElementById('modalAccountName');
    const credInput = document.getElementById('modalCredential');
    const priorityInput = document.getElementById('modalPriority');
    const weightInput = document.getElementById('modalWeight');
    const activeCheck = document.getElementById('modalIsActive');

    if (!modal) return;

    idInput.value = account.id;
    title.innerHTML = '<i class="fas fa-user-pen text-indigo-600"></i> 编辑网盘账号';
    if (cloudSelect) cloudSelect.value = account.cloud_name;
    if (nameInput) nameInput.value = account.account_name;
    if (credInput) credInput.value = account.credential;
    if (priorityInput) priorityInput.value = account.priority;
    if (weightInput) weightInput.value = account.weight;
    if (activeCheck) activeCheck.checked = account.is_active === 1;

    updateModalCredentialHintAndPlaceholder(account.cloud_name);

    modal.style.display = 'flex';
}

function closeAccountModal() {
    const modal = document.getElementById('accountModal');
    if (modal) modal.style.display = 'none';
}

async function handleAccountFormSubmit(e) {
    e.preventDefault();

    const id = document.getElementById('modalAccountId').value;
    const cloud_name = document.getElementById('modalCloudName').value;
    const account_name = document.getElementById('modalAccountName').value.trim();
    let credential = document.getElementById('modalCredential').value.trim();

    // 容错处理：若迅雷网盘用户只输入了纯 refresh_token 字符串，自动包装为规范 JSON
    if (cloud_name === '迅雷网盘' && credential && !credential.startsWith('{')) {
        try {
            credential = JSON.stringify({
                refresh_token: credential,
                client_id: 'YBJdb1UyFQJwh_nS',
                user_id: '',
                device_id: ''
            });
        } catch (_) { }
    }

    const priority = parseInt(document.getElementById('modalPriority').value) || 0;
    const weight = parseInt(document.getElementById('modalWeight').value) || 10;
    const is_active = document.getElementById('modalIsActive').checked ? 1 : 0;
    const auto_test = document.getElementById('modalAutoTest').checked;

    const submitBtn = document.getElementById('btnSubmitAccountModal');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 保存中...';
    }

    try {
        const payload = {
            cloud_name,
            account_name,
            credential,
            priority,
            weight,
            is_active,
            auto_test,
        };

        const isEdit = Boolean(id);
        const url = isEdit ? `/admin/api/accounts/${id}` : '/admin/api/accounts';
        const method = isEdit ? 'PUT' : 'POST';

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        });
        const data = await res.json();

        if (data.success) {
            // 立即秒关弹窗，不再等待第三方网盘网络响应
            closeAccountModal();

            const savedAcc = data.account;
            const savedId = savedAcc ? savedAcc.id : (id ? parseInt(id) : null);

            if (auto_test && savedId) {
                _testingAccountIds.add(savedId);
                showToast(data.message || '账号保存成功，已在后台启动自动测活与容量探测', 'info');
                await loadCloudAccounts();
                pollAccountTestResult(savedId);
            } else {
                showToast(data.message || '操作成功', 'success');
                await loadCloudAccounts();
            }
        } else {
            showToast(data.message || '保存失败: 未知错误', 'danger');
        }
    } catch (err) {
        console.error('保存账号异常:', err);
        showToast('网络请求异常: ' + err.message, 'danger');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check"></i> 保存账号';
        }
    }
}

async function toggleAccountActive(accountId, isActive) {
    try {
        const res = await fetch(`/admin/api/accounts/${accountId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: isActive ? 1 : 0 }),
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast(`账号已${isActive ? '启用' : '停用'}`, 'info');
            loadCloudAccounts();
        } else {
            showToast(data.message || '切换账号状态失败', 'danger');
        }
    } catch (err) {
        console.error('切换账号状态异常:', err);
        showToast('切换账号状态异常: ' + err.message, 'danger');
    }
}

async function testAccount(accountId, btnEl = null) {
    if (_testingAccountIds.has(accountId)) return;
    _testingAccountIds.add(accountId);

    // 立即给按钮和该行呈现加载中反馈
    if (!btnEl) {
        btnEl = document.querySelector(`.account-test-btn[data-account-id="${accountId}"]`);
    }
    if (btnEl) {
        btnEl.disabled = true;
        btnEl.setAttribute('title', '正在测活与探测容量...');
        btnEl.innerHTML = '<i class="fas fa-spinner fa-spin text-indigo-600"></i>';
    }
    renderAccountsTable(_accountsData);

    showToast('正在向网盘发起健康自检与容量探测...', 'info');
    try {
        const res = await fetch(`/admin/api/accounts/${accountId}/test`, {
            method: 'POST',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || '测试通过，账号状态健康', 'success');
        } else {
            showToast(data.message || '自测未通过: 连接失败', 'warning');
        }
    } catch (err) {
        showToast('自测请求异常: ' + err.message, 'danger');
    } finally {
        _testingAccountIds.delete(accountId);
        await loadCloudAccounts();
    }
}
window.testAccount = testAccount;

function pollAccountTestResult(accountId, maxAttempts = 8) {
    let attempts = 0;
    const interval = setInterval(async () => {
        attempts++;
        try {
            const res = await fetch('/admin/api/accounts', { credentials: 'same-origin' });
            const data = await res.json();
            if (data.success && Array.isArray(data.accounts)) {
                _accountsData = data.accounts;
                const acc = _accountsData.find(a => a.id === accountId);
                const isTested = acc && (
                    (acc.total_space_bytes && acc.total_space_bytes > 0) ||
                    (acc.is_valid === 0 && acc.invalid_reason) ||
                    (acc.last_keepalive_at || acc.last_used_at)
                );

                if (isTested || attempts >= maxAttempts) {
                    clearInterval(interval);
                    _testingAccountIds.delete(accountId);
                    renderAccountsTable(_accountsData);
                    if (acc) {
                        const isValid = acc.is_valid === 1;
                        showToast(`账号「${acc.account_name}」后台测活完成：${isValid ? '正常就绪' : (acc.invalid_reason || '凭据异常')}`, isValid ? 'success' : 'warning');
                    }
                    return;
                }
                renderAccountsTable(_accountsData);
            }
        } catch (e) {
            console.warn('轮询账号测活状态异常:', e);
        }

        if (attempts >= maxAttempts) {
            clearInterval(interval);
            _testingAccountIds.delete(accountId);
            renderAccountsTable(_accountsData);
        }
    }, 1800);
}

async function deleteAccount(accountId) {
    const acc = _accountsData.find(a => a.id === accountId);
    const name = acc ? acc.account_name : `ID:${accountId}`;
    const cloud = acc ? acc.cloud_name : '网盘';

    const confirmed = window.confirmModal
        ? await window.confirmModal({
            title: '删除网盘账号',
            message: `确定要彻底删除 ${cloud} 账号「${name}」吗？删除后该账号将不再参与任何转存与分流任务。`,
            confirmText: '确认删除',
            cancelText: '取消',
            type: 'danger'
        })
        : true;

    if (!confirmed) return;

    try {
        const res = await fetch(`/admin/api/accounts/${accountId}`, {
            method: 'DELETE',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast('账号已安全删除', 'success');
            loadCloudAccounts();
        } else {
            showToast('删除失败: ' + (data.message || '未知错误'), 'danger');
        }
    } catch (err) {
        showToast('删除请求失败: ' + err.message, 'danger');
    }
}

function openAccountKeepaliveModal() {
    const modal = document.getElementById('accountKeepaliveModal');
    if (!modal) return;

    const resultBox = document.getElementById('keepaliveExecutionResult');
    if (resultBox) {
        resultBox.className = 'hidden';
        resultBox.innerHTML = '';
    }

    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    loadAccountKeepaliveConfig();
}

function closeAccountKeepaliveModal() {
    const modal = document.getElementById('accountKeepaliveModal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
}

async function loadAccountKeepaliveConfig() {
    const toggle = document.getElementById('modalAccountKeepaliveToggle');
    const select = document.getElementById('modalAccountKeepaliveIntervalSelect');
    if (!toggle || !select) return;

    try {
        const res = await fetch('/admin/api/accounts/keepalive-config', { credentials: 'same-origin' });
        const data = await res.json();
        if (data.success && data.config) {
            const cfg = data.config;
            toggle.checked = Boolean(cfg.enabled);
            select.value = String(cfg.interval_hours || 24);
            select.disabled = !toggle.checked;
        }
    } catch (err) {
        console.warn('加载账号池自动保活配置失败:', err);
    }
}

async function saveAccountKeepaliveConfig() {
    const toggle = document.getElementById('modalAccountKeepaliveToggle');
    const select = document.getElementById('modalAccountKeepaliveIntervalSelect');
    if (!toggle || !select) return;

    select.disabled = !toggle.checked;

    const payload = {
        enabled: toggle.checked,
        interval_hours: parseInt(select.value, 10) || 24,
    };

    const saveBtn = document.getElementById('btnSaveKeepaliveConfigModal');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 保存中...';
    }

    try {
        const res = await fetch('/admin/api/accounts/keepalive-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            showToast(payload.enabled ? `已更新后台自动巡检（每 ${payload.interval_hours} 小时）` : '已停用后台自动巡检', 'success');
        } else {
            showToast('保存策略失败: ' + (data.message || '未知异常'), 'warning');
        }
    } catch (err) {
        showToast('保存策略网络异常: ' + err.message, 'danger');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-floppy-disk mr-1"></i> 保存自动策略';
        }
    }
}

async function triggerKeepaliveNowInModal() {
    const btn = document.getElementById('btnTriggerKeepaliveNow');
    const resultBox = document.getElementById('keepaliveExecutionResult');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 续期保活中...';
    }

    if (resultBox) {
        resultBox.className = 'p-3 rounded-xl border border-indigo-200 bg-indigo-50/70 dark:border-indigo-900/50 dark:bg-indigo-950/20 text-xs text-indigo-700 dark:text-indigo-300 flex items-center gap-2';
        resultBox.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在遍历全账号池执行静默续期与容量探测，请稍候...';
    }

    try {
        const res = await fetch('/admin/api/accounts/keepalive', {
            method: 'POST',
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.success) {
            const r = data.result || {};
            const total = r.total_checked || 0;
            const refreshed = r.refreshed || 0;
            const failed = r.failed || 0;

            if (resultBox) {
                if (failed > 0) {
                    resultBox.className = 'p-3 rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20 text-xs text-amber-800 dark:text-amber-300 space-y-1';
                    resultBox.innerHTML = `<div class="font-bold flex items-center gap-1.5"><i class="fas fa-circle-exclamation"></i> 巡检完成（部分异常）</div><div>共自检 <strong>${total}</strong> 个启用账号，成功刷新 <strong>${refreshed}</strong> 个，失败/失效 <strong>${failed}</strong> 个。请检查标红账号凭据。</div>`;
                } else {
                    resultBox.className = 'p-3 rounded-xl border border-emerald-200 bg-emerald-50 dark:border-emerald-900/50 dark:bg-emerald-950/20 text-xs text-emerald-800 dark:text-emerald-300 space-y-1';
                    resultBox.innerHTML = `<div class="font-bold flex items-center gap-1.5"><i class="fas fa-circle-check"></i> 全盘续期成功</div><div>共自检 <strong>${total}</strong> 个启用账号，全部凭证有效，最新存储配额已同步就绪。</div>`;
                }
            }
            showToast(`续期自检完成: 成功 ${refreshed} 个，失败 ${failed} 个`, failed > 0 ? 'warning' : 'success');
            loadCloudAccounts();
        } else {
            if (resultBox) {
                resultBox.className = 'p-3 rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-900/50 dark:bg-rose-950/20 text-xs text-rose-800 dark:text-rose-300';
                resultBox.innerHTML = `<i class="fas fa-circle-xmark mr-1"></i> 保活失败: ${escapeHtml(data.message || '未知异常')}`;
            }
            showToast('保活失败: ' + (data.message || '未知异常'), 'warning');
        }
    } catch (err) {
        if (resultBox) {
            resultBox.className = 'p-3 rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-900/50 dark:bg-rose-950/20 text-xs text-rose-800 dark:text-rose-300';
            resultBox.innerHTML = `<i class="fas fa-circle-xmark mr-1"></i> 网络请求异常: ${escapeHtml(err.message)}`;
        }
        showToast('保活请求异常: ' + err.message, 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-rotate mr-1"></i> 立即全盘续期';
        }
    }
}

async function exportAccountsCsv() {
    const cloud = (_currentCloudFilter && _currentCloudFilter !== 'ALL') ? _currentCloudFilter : '';
    const url = cloud ? `/admin/api/accounts/export-csv?cloud_name=${encodeURIComponent(cloud)}` : '/admin/api/accounts/export-csv';
    const btn = document.getElementById('btnExportAccounts');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 导出中...';
    }
    showToast(`正在导出${cloud ? ` [${cloud}] ` : '全部'}网盘账号配置...`, 'info');

    try {
        const res = await fetch(url, { credentials: 'same-origin' });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            showToast(data.message || '导出失败: 服务器异常', 'danger');
            return;
        }

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;

        // 获取或构建文件名
        let filename = '';
        const disposition = res.headers.get('content-disposition');
        if (disposition && disposition.includes('filename*=')) {
            const parts = disposition.split("filename*=");
            if (parts.length > 1) {
                const encName = parts[1].replace(/UTF-8''/i, '').replace(/["']/g, '').trim();
                try {
                    filename = decodeURIComponent(encName);
                } catch (e) { }
            }
        }
        if (!filename && disposition && disposition.includes('filename=')) {
            const match = disposition.match(/filename="?([^";]+)"?/i);
            if (match && match[1]) filename = match[1].trim();
        }
        if (!filename) {
            const nowStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            const filterStr = cloud ? `_${cloud}` : '';
            filename = `网盘账号池${filterStr}_${nowStr}.csv`;
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();

        setTimeout(() => {
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();
        }, 1000);

        showToast('导出成功，文件已开始下载', 'success');
    } catch (err) {
        console.error('导出异常:', err);
        // Fallback: direct window.open
        window.open(url, '_blank');
        showToast('已唤起浏览器下载', 'info');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-file-export"></i> 导出 CSV';
        }
    }
}

let _selectedCsvFile = null;

function openAccountImportModal() {
    const modal = document.getElementById('accountImportModal');
    const form = document.getElementById('accountImportForm');
    const resultDiv = document.getElementById('accountImportResult');
    const fileInput = document.getElementById('accountCsvFileInput');
    const fileNameEl = document.getElementById('accountCsvFileName');
    const iconEl = document.getElementById('accountCsvIcon');

    if (!modal || !form) return;

    form.reset();
    _selectedCsvFile = null;
    if (fileInput) fileInput.value = '';
    if (fileNameEl) fileNameEl.textContent = '点击选择或将 CSV 文件拖拽至此处';
    if (iconEl) iconEl.className = 'fas fa-cloud-arrow-up text-3xl text-indigo-500 mb-2 block';
    if (resultDiv) {
        resultDiv.className = 'hidden';
        resultDiv.innerHTML = '';
    }

    modal.style.display = 'flex';
}

function closeAccountImportModal() {
    const modal = document.getElementById('accountImportModal');
    if (modal) modal.style.display = 'none';
}

function handleCsvFileSelect(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv') && file.type !== 'text/csv') {
        showToast('请选择 .csv 格式的文件', 'warning');
        return;
    }
    _selectedCsvFile = file;
    const fileNameEl = document.getElementById('accountCsvFileName');
    const iconEl = document.getElementById('accountCsvIcon');
    if (fileNameEl) {
        fileNameEl.innerHTML = `<span class="text-indigo-600 dark:text-indigo-400 font-semibold">${escapeHtml(file.name)}</span> <span class="text-slate-400 text-xs">(${formatBytes(file.size)})</span>`;
    }
    if (iconEl) {
        iconEl.className = 'fas fa-file-csv text-3xl text-emerald-500 mb-2 block';
    }
}

async function handleAccountImportSubmit(e) {
    e.preventDefault();
    if (!_selectedCsvFile) {
        showToast('请先选择要导入的 CSV 文件', 'warning');
        return;
    }

    const autoTest = document.getElementById('accountImportAutoTest')?.checked ?? true;
    const submitBtn = document.getElementById('btnSubmitAccountImport');
    const resultDiv = document.getElementById('accountImportResult');

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 正在导入解析...';
    }
    if (resultDiv) {
        resultDiv.className = 'hidden';
        resultDiv.innerHTML = '';
    }

    const formData = new FormData();
    formData.append('file', _selectedCsvFile);
    formData.append('auto_test', autoTest ? 'true' : 'false');

    try {
        const res = await fetch('/admin/api/accounts/import-csv', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || '导入完成', 'success');
            loadCloudAccounts();

            if (data.errors && data.errors.length > 0) {
                if (resultDiv) {
                    resultDiv.className = 'p-3 rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20 text-xs max-h-40 overflow-y-auto space-y-1';
                    let errHtml = `<div class="font-bold text-amber-800 dark:text-amber-400 flex items-center gap-1.5"><i class="fas fa-triangle-exclamation"></i> 导入报告：成功 ${data.imported} 个，失败/跳过 ${data.failed} 条</div><ul class="list-disc pl-4 space-y-0.5 text-slate-600 dark:text-slate-400">`;
                    data.errors.forEach(err => {
                        errHtml += `<li>第 ${err.row} 行: ${escapeHtml(err.error)}</li>`;
                    });
                    errHtml += '</ul>';
                    resultDiv.innerHTML = errHtml;
                }
            } else {
                setTimeout(() => {
                    closeAccountImportModal();
                }, 800);
            }
        } else {
            showToast(data.message || '导入失败', 'danger');
            if (resultDiv) {
                resultDiv.className = 'p-3 rounded-xl border border-red-200 bg-red-50 dark:border-red-900/40 dark:bg-red-950/20 text-xs max-h-40 overflow-y-auto space-y-1';
                let errHtml = `<div class="font-bold text-red-700 dark:text-red-400"><i class="fas fa-circle-xmark mr-1"></i> ${escapeHtml(data.message || '导入失败')}</div>`;
                if (data.errors && data.errors.length > 0) {
                    errHtml += '<ul class="list-disc pl-4 space-y-0.5 text-slate-600 dark:text-slate-400 mt-1">';
                    data.errors.forEach(err => {
                        errHtml += `<li>第 ${err.row} 行: ${escapeHtml(err.error)}</li>`;
                    });
                    errHtml += '</ul>';
                }
                resultDiv.innerHTML = errHtml;
            }
        }
    } catch (err) {
        console.error('导入账号异常:', err);
        showToast('上传请求异常: ' + err.message, 'danger');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-upload mr-1"></i> 开始导入';
        }
    }
}

function initAccountCsvDropZone() {
    const dropZone = document.getElementById('accountCsvDropZone');
    const fileInput = document.getElementById('accountCsvFileInput');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleCsvFileSelect(e.target.files[0]);
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/30');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/30');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt?.files;
        if (files && files.length > 0) {
            handleCsvFileSelect(files[0]);
        }
    });
}

function initAccountPoolEvents() {
    const btnAdd = document.getElementById('btnAddAccount');
    if (btnAdd) btnAdd.addEventListener('click', openAddAccountModal);

    const btnClose = document.getElementById('btnCloseAccountModal');
    if (btnClose) btnClose.addEventListener('click', closeAccountModal);

    const btnCancel = document.getElementById('btnCancelAccountModal');
    if (btnCancel) btnCancel.addEventListener('click', closeAccountModal);

    const modal = document.getElementById('accountModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeAccountModal();
            }
        });
    }

    const form = document.getElementById('accountForm');
    if (form) form.addEventListener('submit', handleAccountFormSubmit);

    const cloudSelect = document.getElementById('modalCloudName');
    if (cloudSelect) {
        cloudSelect.addEventListener('change', (e) => {
            updateModalCredentialHintAndPlaceholder(e.target.value);
        });
    }

    const btnKeepalive = document.getElementById('btnKeepaliveAccounts');
    if (btnKeepalive) btnKeepalive.addEventListener('click', openAccountKeepaliveModal);

    const btnCloseKeepalive = document.getElementById('btnCloseAccountKeepaliveModal');
    if (btnCloseKeepalive) btnCloseKeepalive.addEventListener('click', closeAccountKeepaliveModal);

    const btnCancelKeepalive = document.getElementById('btnCancelAccountKeepaliveModal');
    if (btnCancelKeepalive) btnCancelKeepalive.addEventListener('click', closeAccountKeepaliveModal);

    const keepaliveModal = document.getElementById('accountKeepaliveModal');
    if (keepaliveModal) {
        keepaliveModal.addEventListener('click', (e) => {
            if (e.target === keepaliveModal) {
                closeAccountKeepaliveModal();
            }
        });
    }

    const modalToggle = document.getElementById('modalAccountKeepaliveToggle');
    if (modalToggle) {
        modalToggle.addEventListener('change', () => {
            const sel = document.getElementById('modalAccountKeepaliveIntervalSelect');
            if (sel) sel.disabled = !modalToggle.checked;
        });
    }

    const btnSaveKeepalive = document.getElementById('btnSaveKeepaliveConfigModal');
    if (btnSaveKeepalive) btnSaveKeepalive.addEventListener('click', saveAccountKeepaliveConfig);

    const btnTriggerKeepalive = document.getElementById('btnTriggerKeepaliveNow');
    if (btnTriggerKeepalive) btnTriggerKeepalive.addEventListener('click', triggerKeepaliveNowInModal);

    // 导出与导入 CSV 按钮
    const btnExport = document.getElementById('btnExportAccounts');
    if (btnExport) btnExport.addEventListener('click', exportAccountsCsv);

    const btnImport = document.getElementById('btnImportAccounts');
    if (btnImport) btnImport.addEventListener('click', openAccountImportModal);

    const btnCloseImport = document.getElementById('btnCloseAccountImportModal');
    if (btnCloseImport) btnCloseImport.addEventListener('click', closeAccountImportModal);

    const btnCancelImport = document.getElementById('btnCancelAccountImportModal');
    if (btnCancelImport) btnCancelImport.addEventListener('click', closeAccountImportModal);

    const importModal = document.getElementById('accountImportModal');
    if (importModal) {
        importModal.addEventListener('click', (e) => {
            if (e.target === importModal) {
                closeAccountImportModal();
            }
        });
    }

    const importForm = document.getElementById('accountImportForm');
    if (importForm) importForm.addEventListener('submit', handleAccountImportSubmit);

    initAccountCsvDropZone();

    // 平台过滤胶囊标签点击
    const filterContainer = document.getElementById('accountPlatformFilter');
    if (filterContainer) {
        filterContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.account-filter-btn');
            if (!btn) return;
            filterContainer.querySelectorAll('.account-filter-btn').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            const cloud = btn.getAttribute('data-cloud');
            loadCloudAccounts(cloud);
        });
    }

    loadCloudAccounts();
}

document.addEventListener('DOMContentLoaded', initAccountPoolEvents);
