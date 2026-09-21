// resource.js - 私有资源管理

// ==========================================
// 1. 全局变量与配置
// ==========================================
let currentPage = 1;
let pageSize = 50;
let totalPages = 1;
let totalCount = 0;
let resourcesData = [];
const selectedResourceMap = new Map();

// 网盘凭证配置就绪状态
let netdiskCredentialsMap = {
    "夸克网盘": { status: 'missing', title: '未配置凭证', key: 'quark' },
    "百度网盘": { status: 'missing', title: '未配置凭证', key: 'baidu' },
    "阿里云盘": { status: 'missing', title: '未配置凭证', key: 'aliyun' },
    "迅雷网盘": { status: 'missing', title: '未配置凭证', key: 'xunlei' },
    "UC网盘": { status: 'missing', title: '未配置凭证', key: 'uc' }
};

// ==========================================
// 2. DOM 元素获取
// ==========================================
const searchInput = document.getElementById('searchInput');
const resourcesTableBody = document.getElementById('resourcesTableBody');
const pagination = document.getElementById('pagination');
const pageSizeSelect = document.getElementById('pageSizeSelect');
const jumpPageInput = document.getElementById('jumpPageInput');
const jumpPageBtn = document.getElementById('jumpPageBtn');
const resourceTotalCount = document.getElementById('resourceTotalCount');
const resourceBatchToolbar = document.getElementById('resourceBatchToolbar');
const selectedResourceCount = document.getElementById('selectedResourceCount');
const selectCurrentPageCheckbox = document.getElementById('selectCurrentPageCheckbox');
const selectCurrentPageBtn = document.getElementById('selectCurrentPageBtn');
const selectAllResourcesBtn = document.getElementById('selectAllResourcesBtn');
const clearSelectionBtn = document.getElementById('clearSelectionBtn');
const exportSelectedBtn = document.getElementById('exportSelectedBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
const auditAllResourcesBtn = document.getElementById('auditAllResourcesBtn');
const cleanupDeadResourcesBtn = document.getElementById('cleanupDeadResourcesBtn');
const auditSelectedBtn = document.getElementById('auditSelectedBtn');
const kpiHealthStats = document.getElementById('kpiHealthStats');

// 模态框与表单
const addResourceForm = document.getElementById('addResourceForm');
const editResourceForm = document.getElementById('editResourceForm');
const batchAddResourceForm = document.getElementById('batchAddResourceForm');
const batchAddResourceModal = document.getElementById('batchAddResourceModal');
const batchAddResourceModalLabel = document.getElementById('batchAddResourceModalLabel');
const batchTransferOptions = document.getElementById('batchTransferOptions');

// 按钮
const saveResourceBtn = document.getElementById('saveResourceBtn');
const updateResourceBtn = document.getElementById('updateResourceBtn');
const batchSaveResourceBtn = document.getElementById('batchSaveResourceBtn');
const batchImportResourceBtn = document.getElementById('batchImportResourceBtn');
const batchTransferResourceBtn = document.getElementById('batchTransferResourceBtn');

// ==========================================
// 3. 核心工具函数
// ==========================================

// 网盘匹配函数
function matchNetdiskLink(link) {
    if (!link) return "其他";
    const netdiskRules = [
        // 国内主流网盘
        ["百度网盘", /(?:https?:\/\/)?(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)\//i],
        ["夸克网盘", /(?:https?:\/\/)?pan\.quark\.cn\//i],
        ["阿里云盘", /(?:https?:\/\/)?(?:drive\.aliyun\.com|aliyundrive\.com|alipan\.com)\//i],
        ["迅雷网盘", /(?:https?:\/\/)?pan\.xunlei\.com\//i],
        ["UC网盘", /(?:https?:\/\/)?(?:pan\.uc\.cn|drive\.uc\.cn)\//i],
        ["123云盘", /(?:https?:\/\/)?(?:123pan\.(?:com|cn)|123\d{3}\.(?:com|cn))\//i],
        ["115网盘", /(?:https?:\/\/)?(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)\//i],
        // 运营商云盘
        ["天翼云盘", /(?:https?:\/\/)?cloud\.189\.cn\//i],
        ["移动云盘", /(?:https?:\/\/)?(?:pan\.10086\.cn|caiyun\.139\.com|yun\.139\.com|caiyun\.feixin\.10086\.cn)\//i],
        ["联通云盘", /(?:https?:\/\/)?pan\.wo\.cn\//i],
        // 国内特色/小众网盘
        ["蓝奏云", /(?:https?:\/\/)?(?:www\.)?(?:lanzou[uixys]*|lan[zs]o[ux])\.(?:com|net|org)\//i],
        ["城通网盘", /(?:https?:\/\/)?(?:www\.)?(?:ctfile|pipipan|400gb|t004)\.(?:com|cn)\//i],
        ["腾讯微云", /(?:https?:\/\/)?(?:www\.)?weiyun\.com\//i],
        ["坚果云", /(?:https?:\/\/)?(?:www\.)?jianguoyun\.com\//i],
        ["悟空网盘", /(?:https?:\/\/)?pan\.wkbrowser\.com\//i],
        ["快兔网盘", /(?:https?:\/\/)?(?:diskyun\.com|www\.diskyun\.com)\//i],
        ["光鸭云盘", /(?:https?:\/\/)?(?:www\.)?guangyapan\.com\//i],
        // 海外及跨境网盘
        ["TeraBox", /(?:https?:\/\/)?(?:www\.)?(?:terabox|teraboxapp|1024tera|freeterabox)\.(?:com|app)\//i],
        ["Google Drive", /(?:https?:\/\/)?(?:drive|docs)\.google\.com\//i],
        ["MEGA", /(?:https?:\/\/)?mega\.(?:nz|co\.nz)\//i],
        ["GoFile", /(?:https?:\/\/)?(?:www\.)?gofile\.io\//i],
        ["OneDrive", /(?:https?:\/\/)?(?:1drv\.ms|(?:[\w-]+\.)?onedrive\.live\.com|[\w-]+\.sharepoint\.com)\//i],
        ["PikPak", /(?:https?:\/\/)?(?:www\.)?(?:pikpak|mypikpak|pikpakdrive)\.com\//i],
        // P2P 下载与协议链接
        ["磁力链接", /^magnet:\?xt=urn:btih:/i],
        ["迅雷链接", /thunder:\/\/[A-Za-z0-9+\/=]+/i],
        ["电驴链接", /^ed2k:\/\//i]
    ];

    const linkLower = link.trim().toLowerCase();
    for (const [name, pattern] of netdiskRules) {
        if (pattern.test(linkLower)) {
            return name;
        }
    }
    return "其他";
}

// 网盘凭证检测与状态渲染
async function loadNetdiskCredentials() {
    try {
        const response = await fetch('/admin/api/credential-config');
        const data = await response.json();
        if (data && data.dynamic_transfer_statuses) {
            data.dynamic_transfer_statuses.forEach(item => {
                if (netdiskCredentialsMap[item.cloud_name]) {
                    netdiskCredentialsMap[item.cloud_name].status = item.status || 'missing';
                    netdiskCredentialsMap[item.cloud_name].title = item.title || '未配置凭证';
                }
            });
        }
    } catch (err) {
        console.warn('获取网盘凭证状态失败:', err);
    } finally {
        renderBatchReadySummary();
        updateSingleLinkTransferHint();
    }
}

function renderBatchReadySummary() {
    const summaryEl = document.getElementById('batchReadyCloudsSummary');
    if (!summaryEl) return;

    const clouds = [
        { name: "夸克网盘", key: "quark", short: "夸克" },
        { name: "百度网盘", key: "baidu", short: "百度" },
        { name: "阿里云盘", key: "aliyun", short: "阿里" },
        { name: "迅雷网盘", key: "xunlei", short: "迅雷" },
        { name: "UC网盘", key: "uc", short: "UC" }
    ];

    const readyClouds = clouds.filter(c => netdiskCredentialsMap[c.name]?.status === 'enabled');
    const invalidClouds = clouds.filter(c => netdiskCredentialsMap[c.name]?.status === 'invalid');

    if (readyClouds.length === 0) {
        summaryEl.innerHTML = `
            <span class="text-slate-500 font-medium">就绪转存平台：</span>
            <span class="text-amber-600 font-normal">暂无网盘就绪（未配置有效凭证）</span>
        `;
        return;
    }

    const readyBadges = readyClouds.map(c => `<span class="px-1.5 py-0.5 rounded-md bg-emerald-100/80 text-emerald-700 font-medium text-[11px]">${c.name}</span>`).join(' ');
    const extraHint = invalidClouds.length > 0 ? `<span class="text-amber-600 text-[10px] ml-1">(${invalidClouds.map(c => c.short).join('、')}凭证失效)</span>` : '';

    summaryEl.innerHTML = `
        <span class="text-slate-600 font-medium whitespace-nowrap">就绪转存平台 (${readyClouds.length}/5)：</span>
        <div class="flex items-center gap-1 flex-wrap">${readyBadges}${extraHint}</div>
    `;
}

// 单条分享链接自动转存匹配实时提示 (方案A：未输入静默隐藏，输入后即显)
function updateSingleLinkTransferHint() {
    const opts = document.getElementById('singleTransferOptions');
    const hintEl = document.getElementById('singleLinkTransferHint');
    if (!opts || !hintEl) return;

    const linkInput = document.getElementById('resourceShareLink');
    const link = linkInput ? linkInput.value.trim() : '';
    const toggle = document.getElementById('singleResourceTransferToggle');
    const isTransferEnabled = toggle ? toggle.checked : false;

    // 未开启转存 或 尚未输入有效链接：静默隐藏，保持卡片极致精简
    if (!isTransferEnabled || !link) {
        opts.classList.add('d-none');
        hintEl.innerHTML = '';
        return;
    }

    const cloudName = matchNetdiskLink(link);
    const cred = netdiskCredentialsMap[cloudName];

    if (!cred || cloudName === '其他') {
        hintEl.className = 'text-xs p-2.5 rounded-lg bg-amber-50/90 text-amber-800 border border-amber-200/80 flex items-center gap-1.5';
        hintEl.innerHTML = `<i class="fas fa-exclamation-triangle text-amber-500 flex-shrink-0"></i> <span>当前识别为「${cloudName}」，暂不支持自动转存，将按原始链接直接入库。</span>`;
        opts.classList.remove('d-none');
    } else if (cred.status === 'enabled') {
        hintEl.className = 'text-xs p-2.5 rounded-lg bg-emerald-50/90 text-emerald-800 border border-emerald-200/80 flex items-center gap-1.5';
        hintEl.innerHTML = `<i class="fas fa-check-circle text-emerald-500 flex-shrink-0"></i> <span>已识别到 <strong>${cloudName}</strong> 链接，且凭证已就绪。提交后将自动转存生成专属链接。</span>`;
        opts.classList.remove('d-none');
    } else {
        hintEl.className = 'text-xs p-2.5 rounded-lg bg-rose-50/90 text-rose-800 border border-rose-200/80 flex items-center justify-between gap-1.5';
        hintEl.innerHTML = `
            <div class="flex items-center gap-1.5 truncate">
                <i class="fas fa-info-circle text-rose-500 flex-shrink-0"></i>
                <span class="truncate">已识别到 <strong>${cloudName}</strong> 链接，但未配置可用凭证，将按原始链接入库。</span>
            </div>
            <a href="/admin/system-config" target="_blank" class="text-rose-700 underline font-medium text-xs whitespace-nowrap ml-2 flex-shrink-0">去配置凭证 &rarr;</a>
        `;
        opts.classList.remove('d-none');
    }
}

// ==========================================
// 4. 数据加载与渲染
// ==========================================

function renderHealthStatusBadge(status, message, checkedAt) {
    status = status || 'unknown';
    let badgeClass = 'bg-slate-100 text-slate-600';
    let icon = 'fas fa-question-circle';
    let text = '未检测';
    if (status === 'ok') {
        badgeClass = 'bg-emerald-100 text-emerald-700';
        icon = 'fas fa-check-circle';
        text = '有效';
    } else if (status === 'bad') {
        badgeClass = 'bg-rose-100 text-rose-700';
        icon = 'fas fa-times-circle';
        text = '失效';
    } else if (status === 'locked') {
        badgeClass = 'bg-amber-100 text-amber-700';
        icon = 'fas fa-key';
        text = '需提取码';
    } else if (status === 'uncertain') {
        badgeClass = 'bg-slate-100 text-slate-600';
        icon = 'fas fa-info-circle';
        text = '未知';
    }
    const tip = message ? `${text} (${message})` : (checkedAt ? `${text} (检测于: ${checkedAt})` : text);
    const safeTip = String(tip).replace(/"/g, '&quot;');
    return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${badgeClass}" title="${safeTip}"><i class="${icon}"></i> ${text}</span>`;
}

// 加载资源列表
async function loadResources() {
    const searchKeyword = searchInput ? searchInput.value.trim() : '';

    try {
        const response = await fetch(`/admin/api/resources?page=${currentPage}&page_size=${pageSize}&search=${encodeURIComponent(searchKeyword)}`);
        const data = await response.json();

        if (data.success) {
            resourcesData = data.data.items;
            totalPages = Math.max(1, data.data.total_pages || 1);
            totalCount = data.data.total_count || 0;

            if (currentPage > totalPages) {
                currentPage = totalPages;
                await loadResources();
                return;
            }

            renderTable();
            renderPagination();
            updatePaginationControls();
            updateSelectionUI();
            loadHealthStats();
        } else {
            showToast('加载资源失败: ' + (data.message || '未知错误'), 'danger');
        }
    } catch (error) {
        console.error('加载资源失败:', error);
        showToast('网络请求失败，请检查服务状态', 'danger');
    }
}

// 渲染表格
function renderTable() {
    if (!resourcesTableBody) return;
    resourcesTableBody.innerHTML = '';

    if (!resourcesData || resourcesData.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="9" class="text-center">暂无数据</td>';
        resourcesTableBody.appendChild(emptyRow);
        return;
    }

    resourcesData.forEach(resource => {
        const row = document.createElement('tr');
        const isSelected = selectedResourceMap.has(resource.id);
        row.innerHTML = `
            <td>
                <input class="form-check-input resource-row-checkbox" type="checkbox" data-id="${resource.id}" ${isSelected ? 'checked' : ''} aria-label="选择资源 ${resource.id}">
            </td>
            <td>${resource.id}</td>
            <td title="${resource.name}">${resource.name}</td>
            <td><a href="${resource.share_link}" target="_blank" class="text-truncate d-inline-block" style="max-width: 250px;">${resource.share_link}</a></td>
            <td>${resource.cloud_name || '-'}</td>
            <td>${resource.type || '-'}</td>
            <td>${renderHealthStatusBadge(resource.health_status, resource.health_message, resource.checked_at)}</td>
            <td>${resource.is_replaced ? '<span class="status-synced">已同步</span>' : '-'}</td>
            <td class="action-buttons d-flex justify-content-center align-items-center">
                <button class="btn btn-secondary btn-sm copy-btn" data-id="${resource.id}" title="复制链接">
                    <i class="fas fa-copy"></i> 复制
                </button>
                <div class="dropdown">
                    <button class="btn btn-sm btn-secondary dropdown-toggle" type="button"
                        data-ui-dropdown-toggle aria-expanded="false" title="更多操作">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li>
                            <a class="dropdown-item check-health-btn" href="javascript:void(0)" data-id="${resource.id}">
                                <i class="fas fa-heartbeat me-2 text-info"></i> 检测健康
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item edit-btn" href="javascript:void(0)" data-id="${resource.id}">
                                <i class="fas fa-edit me-2"></i> 编辑
                            </a>
                        </li>
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <a class="dropdown-item text-danger delete-btn" href="javascript:void(0)" data-id="${resource.id}">
                                <i class="fas fa-trash me-2"></i> 删除
                            </a>
                        </li>
                    </ul>
                </div>
            </td>
        `;
        resourcesTableBody.appendChild(row);
    });

    // 重新绑定事件监听器
    bindActionEvents();
}

// 渲染分页
function renderPagination() {
    if (!pagination) return;
    pagination.innerHTML = '';

    // 上一页
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    prevLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage - 1}">&laquo;</a>`;
    pagination.appendChild(prevLi);

    // 页码逻辑
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, startPage + 4);

    if (startPage > 1) {
        pagination.appendChild(createPageItem(1));
        if (startPage > 2) pagination.appendChild(createEllipsis());
    }

    for (let i = startPage; i <= endPage; i++) {
        pagination.appendChild(createPageItem(i));
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) pagination.appendChild(createEllipsis());
        pagination.appendChild(createPageItem(totalPages));
    }

    // 下一页
    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${currentPage === totalPages || totalPages === 0 ? 'disabled' : ''}`;
    nextLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage + 1}">&raquo;</a>`;
    pagination.appendChild(nextLi);
}

function updatePaginationControls() {
    if (resourceTotalCount) {
        resourceTotalCount.textContent = `共 ${totalCount} 条`;
    }
    const kpiTotalEl = document.getElementById('kpiResourceTotal');
    if (kpiTotalEl) {
        kpiTotalEl.textContent = `${totalCount} 条`;
    }

    if (jumpPageInput) {
        jumpPageInput.value = String(currentPage);
        jumpPageInput.max = String(totalPages);
        jumpPageInput.disabled = totalPages <= 1;
    }

    if (jumpPageBtn) {
        jumpPageBtn.disabled = totalPages <= 1;
    }

    if (pageSizeSelect) {
        pageSizeSelect.value = String(pageSize);
    }
}

function jumpToPage() {
    if (!jumpPageInput) return;

    const rawPage = parseInt(jumpPageInput.value, 10);
    if (Number.isNaN(rawPage)) {
        showToast('请输入有效页码', 'warning');
        jumpPageInput.value = String(currentPage);
        return;
    }

    const targetPage = Math.min(Math.max(rawPage, 1), totalPages);
    jumpPageInput.value = String(targetPage);

    if (targetPage === currentPage) return;

    currentPage = targetPage;
    loadResources();
}

function createPageItem(page) {
    const li = document.createElement('li');
    li.className = `page-item ${page === currentPage ? 'active' : ''}`;
    li.innerHTML = `<a class="page-link" href="#" data-page="${page}">${page}</a>`;
    return li;
}

function createEllipsis() {
    const li = document.createElement('li');
    li.className = 'page-item disabled';
    li.innerHTML = '<span class="page-link">...</span>';
    return li;
}

// ==========================================
// 5. 交互事件处理 (编辑/删除/复制)
// ==========================================

function bindActionEvents() {
    // 选择
    document.querySelectorAll('.resource-row-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', () => toggleResourceSelection(parseInt(checkbox.getAttribute('data-id'), 10), checkbox.checked));
    });
    // 检测健康
    document.querySelectorAll('.check-health-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const btnEl = e.currentTarget;
            checkResourceHealth(parseInt(btnEl.getAttribute('data-id'), 10), btnEl);
        });
    });
    // 编辑
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => editResource(parseInt(btn.getAttribute('data-id'))));
    });
    // 删除
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteResource(parseInt(btn.getAttribute('data-id'))));
    });
    // 复制
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const btnEl = e.currentTarget;
            copyResource(parseInt(btnEl.getAttribute('data-id'), 10), btnEl);
        });
    });
}

function toggleResourceSelection(resourceId, checked) {
    const resource = resourcesData.find(r => r.id === resourceId);
    if (!resource) return;

    if (checked) {
        selectedResourceMap.set(resourceId, resource);
    } else {
        selectedResourceMap.delete(resourceId);
    }

    updateSelectionUI();
}

function updateSelectionUI() {
    const selectedCount = selectedResourceMap.size;

    if (resourceBatchToolbar) {
        resourceBatchToolbar.classList.toggle('show', selectedCount > 0);
    }

    if (selectedResourceCount) {
        selectedResourceCount.textContent = String(selectedCount);
    }

    if (selectCurrentPageCheckbox) {
        const currentPageIds = resourcesData.map(resource => resource.id);
        const selectedOnPage = currentPageIds.filter(id => selectedResourceMap.has(id)).length;
        selectCurrentPageCheckbox.checked = currentPageIds.length > 0 && selectedOnPage === currentPageIds.length;
        selectCurrentPageCheckbox.indeterminate = selectedOnPage > 0 && selectedOnPage < currentPageIds.length;
    }

    if (exportSelectedBtn) {
        exportSelectedBtn.disabled = selectedCount === 0;
    }

    if (deleteSelectedBtn) {
        deleteSelectedBtn.disabled = selectedCount === 0;
    }
}

function selectCurrentPageResources() {
    resourcesData.forEach(resource => selectedResourceMap.set(resource.id, resource));
    document.querySelectorAll('.resource-row-checkbox').forEach(checkbox => {
        checkbox.checked = true;
    });
    updateSelectionUI();
}

function clearResourceSelection() {
    selectedResourceMap.clear();
    document.querySelectorAll('.resource-row-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    updateSelectionUI();
}

// 复制资源信息
async function copyResource(id, buttonEl) {
    const resource = resourcesData.find(r => r.id === id);
    if (!resource) return;

    // 格式化复制内容：优先提供干净链接与提取码，支持直接打开或客户端自动识别
    let copyContent = resource.share_link || '';
    if (resource.code && resource.code !== '无' && resource.code.trim() !== '') {
        copyContent = `${resource.share_link} 提取码: ${resource.code}`;
    }

    const success = await copyTextToClipboard(copyContent);

    if (success) {
        showToast('已复制到剪贴板', 'success');
        if (buttonEl) {
            const originalHtml = buttonEl.innerHTML;
            buttonEl.innerHTML = '<i class="fas fa-check text-emerald-500"></i> 已复制';
            buttonEl.disabled = true;
            setTimeout(() => {
                buttonEl.innerHTML = originalHtml;
                buttonEl.disabled = false;
            }, 1500);
        }
    } else {
        showToast('复制失败，请手动选择复制', 'danger');
    }
}

// 单条检测资源健康状态
async function checkResourceHealth(id, btnEl) {
    if (!id) return;
    const originalHtml = btnEl ? btnEl.innerHTML : '';
    if (btnEl) {
        btnEl.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> 检测中...';
    }
    try {
        const response = await fetch(`/admin/api/resources/${id}/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success && data.data) {
            const state = data.data.health_status;
            const msg = data.data.health_message || '';
            const statusText = state === 'ok' ? '有效' : (state === 'bad' ? '失效' : (state === 'locked' ? '需提取码' : '未知'));
            showToast(`资源 [${id}] 检测完成: ${statusText}${msg ? ' (' + msg + ')' : ''}`, state === 'ok' ? 'success' : (state === 'bad' ? 'danger' : 'warning'));
            loadResources();
        } else {
            showToast(data.message || '检测失败', 'danger');
        }
    } catch (err) {
        showToast('检测请求失败: ' + err.message, 'danger');
    } finally {
        if (btnEl) {
            btnEl.innerHTML = originalHtml;
        }
    }
}

// 加载资源健康状态汇总统计
async function loadHealthStats() {
    try {
        const response = await fetch('/admin/api/resources/health-stats');
        const data = await response.json();
        if (data.success && data.data) {
            const s = data.data;
            if (kpiHealthStats) {
                kpiHealthStats.innerHTML = `<span class="text-emerald-600 font-bold">${s.ok || 0}</span> / <span class="text-rose-600 font-bold">${s.bad || 0}</span>`;
            }
        }
    } catch (e) {
        console.warn('获取资源健康度统计失败:', e);
    }
}

// 删除资源
async function deleteResource(id) {
    if (await showConfirm('确定要删除这条资源吗？此操作不可恢复。', 'danger')) {
        try {
            const response = await fetch(`/admin/api/resources/${id}`, { method: 'DELETE' });
            const data = await response.json();

            if (data.success) {
                showToast('删除成功');
                selectedResourceMap.delete(id);
                updateSelectionUI();
                loadResources();
            } else {
                showToast(data.message || '删除失败', 'danger');
            }
        } catch (error) {
            showToast('删除请求失败', 'danger');
        }
    }
}

// 获取详情并打开编辑框
async function editResource(id) {
    try {
        const response = await fetch(`/admin/api/resources/${id}`);
        const data = await response.json();

        if (data.success) {
            const res = data.data;
            document.getElementById('editResourceId').value = res.id;
            document.getElementById('editResourceName').value = res.name;
            document.getElementById('editResourceShareLink').value = res.share_link;
            document.getElementById('editResourceCloudName').value = res.cloud_name || '';
            document.getElementById('editResourceType').value = res.type || '';
            document.getElementById('editResourceRemarks').value = res.remarks || '';

            window.AppUI.openModal('editResourceModal');
        } else {
            showToast(data.message, 'danger');
        }
    } catch (error) {
        showToast('获取详情失败', 'danger');
    }
}

// 单条添加转存切换
function toggleSingleTransferOptions(enabled) {
    const saveBtn = document.getElementById('saveResourceBtn');
    if (saveBtn) {
        saveBtn.innerHTML = enabled
            ? '<i class="fas fa-cloud-upload-alt me-1"></i> 转存并入库'
            : '<i class="fas fa-save me-1"></i> 直接入库';
    }
    updateSingleLinkTransferHint();
}

function getActiveTransferNetdiskConfig() {
    return {
        quark: netdiskCredentialsMap["夸克网盘"]?.status === 'enabled',
        baidu: netdiskCredentialsMap["百度网盘"]?.status === 'enabled',
        aliyun: netdiskCredentialsMap["阿里云盘"]?.status === 'enabled',
        xunlei: netdiskCredentialsMap["迅雷网盘"]?.status === 'enabled',
        uc: netdiskCredentialsMap["UC网盘"]?.status === 'enabled',
    };
}

function getSingleTransferNetdiskConfig() {
    const toggle = document.getElementById('singleResourceTransferToggle');
    if (!toggle || !toggle.checked) {
        return {};
    }
    return getActiveTransferNetdiskConfig();
}

// 保存单个资源
async function saveResource() {
    if (!addResourceForm.checkValidity()) {
        addResourceForm.reportValidity();
        return;
    }

    const shareLink = document.getElementById('resourceShareLink').value.trim();
    const cloudName = matchNetdiskLink(shareLink);
    const saveToNetdisk = getSingleTransferNetdiskConfig();
    const isTransfer = Object.values(saveToNetdisk).some(Boolean);

    const payload = {
        name: document.getElementById('resourceName').value.trim(),
        share_link: shareLink,
        cloud_name: cloudName,
        type: document.getElementById('resourceType').value,
        remarks: document.getElementById('resourceRemarks').value.trim(),
        save_to_netdisk: saveToNetdisk
    };

    // 状态切换
    saveResourceBtn.disabled = true;
    saveResourceBtn.innerHTML = isTransfer 
        ? '<span class="spinner-border spinner-border-sm"></span> 正在转存并入库...' 
        : '<span class="spinner-border spinner-border-sm"></span> 保存中...';

    try {
        const response = await fetch('/admin/api/resources', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.success) {
            showToast(data.message || (isTransfer ? '资源转存并入库成功' : '资源已直接入库'));
            window.AppUI.closeModal('addResourceModal');
            addResourceForm.reset();
            const singleToggle = document.getElementById('singleResourceTransferToggle');
            if (singleToggle) singleToggle.checked = false;
            toggleSingleTransferOptions(false);
            loadResources();
        } else {
            showToast(data.message || '添加失败', 'danger');
        }
    } catch (error) {
        console.error(error);
        showToast('请求失败，请检查网络', 'danger');
    } finally {
        saveResourceBtn.disabled = false;
        const currentToggle = document.getElementById('singleResourceTransferToggle');
        const isCurrentTransfer = currentToggle ? currentToggle.checked : false;
        saveResourceBtn.innerHTML = isCurrentTransfer 
            ? '<i class="fas fa-cloud-upload-alt me-1"></i> 转存并入库' 
            : '<i class="fas fa-save me-1"></i> 直接入库';
    }
}

// 更新资源
async function updateResource() {
    if (!editResourceForm.checkValidity()) {
        editResourceForm.reportValidity();
        return;
    }

    const id = document.getElementById('editResourceId').value;
    const shareLink = document.getElementById('editResourceShareLink').value.trim();
    const cloudName = matchNetdiskLink(shareLink);

    const payload = {
        name: document.getElementById('editResourceName').value.trim(),
        share_link: shareLink,  // 添加分享链接字段
        cloud_name: cloudName,
        type: document.getElementById('editResourceType').value,
        remarks: document.getElementById('editResourceRemarks').value.trim()
    };

    updateResourceBtn.disabled = true;
    updateResourceBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 更新中...';

    try {
        const response = await fetch(`/admin/api/resources/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.success) {
            showToast('更新成功');
            window.AppUI.closeModal('editResourceModal');
            loadResources();
        } else {
            showToast(data.message || '更新失败', 'danger');
        }
    } catch (error) {
        showToast('更新请求异常', 'danger');
    } finally {
        updateResourceBtn.disabled = false;
        updateResourceBtn.innerHTML = '<i class="fas fa-save"></i> 保存修改';
    }
}

// 批量添加解析逻辑
function parseBatchResources(content) {
    const resources = [];
    const lines = content.split('\n');
    let currentResource = {};
    let hasStructuredField = false;

    lines.forEach(line => {
        line = line.trim();
        if (!line) return;

        // 匹配标题 (支持中英文冒号)
        const titleMatch = line.match(/^(?:标题|name)[:：]\s*(.+)$/i);
        if (titleMatch) {
            hasStructuredField = true;
            if (currentResource.name && currentResource.share_link) {
                resources.push(currentResource);
                currentResource = {};
            }
            currentResource.name = titleMatch[1].trim();
            return;
        }

        // 匹配链接
        const linkMatch = line.match(/^(?:链接|分享链接|share_link)[:：]\s*(.+)$/i);
        if (linkMatch) {
            hasStructuredField = true;
            currentResource.share_link = linkMatch[1].trim();
            if (!currentResource.cloud_name) {
                currentResource.cloud_name = matchNetdiskLink(currentResource.share_link);
            }
            return;
        }

        // 匹配云盘名称
        const cloudMatch = line.match(/^(?:云盘|网盘|云盘名称|网盘名称|cloud|cloud_name)[:：]\s*(.+)$/i);
        if (cloudMatch) {
            hasStructuredField = true;
            currentResource.cloud_name = cloudMatch[1].trim();
            return;
        }

        // 匹配类型
        const typeMatch = line.match(/^(?:类型|type)[:：]\s*(.+)$/i);
        if (typeMatch) {
            hasStructuredField = true;
            currentResource.type = typeMatch[1].trim();
            return;
        }
        
        // 匹配备注
        const remarkMatch = line.match(/^(?:备注|remark|remarks)[:：]\s*(.+)$/i);
        if (remarkMatch) {
            hasStructuredField = true;
            currentResource.remarks = remarkMatch[1].trim();
            return;
        }
    });

    // 推送最后一条
    if (currentResource.name && currentResource.share_link) {
        resources.push(currentResource);
    }

    if (resources.length > 0 || hasStructuredField) {
        return resources;
    }

    return content
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => line.split(/\t|,/).map(part => part.trim()))
        .filter(parts => parts.length >= 2 && parts[0] && parts[1])
        .map(parts => ({
            name: parts[0],
            share_link: parts[1],
            cloud_name: matchNetdiskLink(parts[1]),
            type: parts[2] || '',
            remarks: parts.slice(3).join(' ') || '',
        }));
}

function toggleBatchTransferOptions(enabled) {
    const opts = document.getElementById('batchTransferOptions');
    const saveBtn = document.getElementById('batchSaveResourceBtn');
    if (opts) {
        opts.classList.toggle('d-none', !enabled);
    }
    if (saveBtn) {
        saveBtn.innerHTML = enabled
            ? '<i class="fas fa-cloud-upload-alt me-1"></i> 开始转存并入库'
            : '<i class="fas fa-save me-1"></i> 开始导入';
    }
    if (enabled) {
        renderBatchReadySummary();
    }
}

function getBatchTransferNetdiskConfig() {
    const toggle = document.getElementById('batchResourceTransferToggle');
    if (!toggle || !toggle.checked) {
        return {};
    }
    return getActiveTransferNetdiskConfig();
}

let isBatchSavingInProgress = false;

// 批量保存
async function batchSaveResources() {
    const saveBtn = document.getElementById('batchSaveResourceBtn');
    if (isBatchSavingInProgress) return;

    const content = document.getElementById('batchResourceContent')?.value?.trim() || '';
    if (!content) {
        showToast('请输入内容', 'warning');
        return;
    }

    const resources = parseBatchResources(content);
    if (resources.length === 0) {
        showToast('未能解析出有效资源，请检查格式', 'danger');
        return;
    }

    const transferToggle = document.getElementById('batchResourceTransferToggle');
    const isTransferMode = transferToggle ? transferToggle.checked : false;

    if (isTransferMode && resources.length > 10) {
        showToast('批量转存建议单次不超过10条', 'warning');
        return;
    }

    if (!isTransferMode && resources.length > 500) {
        showToast('批量导入建议单次不超过500条', 'warning');
        return;
    }

    const commonType = document.getElementById('batchResourceType')?.value || '';
    const commonRemarks = document.getElementById('batchResourceRemarks')?.value?.trim() || '';

    const saveToNetdisk = getBatchTransferNetdiskConfig();
    const actionText = isTransferMode ? '转存入库' : '导入';

    isBatchSavingInProgress = true;
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 正在${actionText}...`;
    }
    let successCount = 0;

    try {
        for (let i = 0; i < resources.length; i++) {
            const res = resources[i];
            if (saveBtn) {
                saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 正在${actionText} ${i + 1}/${resources.length}`;
            }

            const payload = {
                name: res.name,
                share_link: res.share_link,
                cloud_name: res.cloud_name || matchNetdiskLink(res.share_link),
                type: res.type || commonType,
                remarks: res.remarks || commonRemarks,
                save_to_netdisk: saveToNetdisk
            };

            const response = await fetch('/admin/api/resources', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (data.success) successCount++;
        }

        showToast(`批量${actionText}完成：成功 ${successCount}，失败 ${resources.length - successCount}`, successCount > 0 ? 'success' : 'warning');
        
        window.AppUI.closeModal('batchAddResourceModal');
        const batchForm = document.getElementById('batchAddResourceForm');
        if (batchForm) batchForm.reset();
        if (transferToggle) transferToggle.checked = false;
        toggleBatchTransferOptions(false);
        loadResources();

    } catch (error) {
        console.error('批量处理异常:', error);
        showToast('批量处理过程中断', 'danger');
    } finally {
        isBatchSavingInProgress = false;
        if (saveBtn) {
            saveBtn.disabled = false;
        }
        const currentToggle = document.getElementById('batchResourceTransferToggle');
        toggleBatchTransferOptions(currentToggle ? currentToggle.checked : false);
    }
}

// ==========================================
// 7. 导出功能 (CSV)
// ==========================================

function convertToCSV(data) {
    if (data.length === 0) return '';
    const headers = ['ID', '标题', '链接', '云盘名称', '类型', '备注'];
    const csvContent = [headers.join(',')];

    data.forEach(resource => {
        const row = [
            resource.id,
            `"${(resource.name || '').replace(/"/g, '""')}"`,
            `"${(resource.share_link || '').replace(/"/g, '""')}"`,
            `"${(resource.cloud_name || '').replace(/"/g, '""')}"`,
            `"${(resource.type || '').replace(/"/g, '""')}"`,
            `"${(resource.remarks || '').replace(/"/g, '""')}"`
        ];
        csvContent.push(row.join(','));
    });
    return "\uFEFF" + csvContent.join('\n'); // 添加 BOM 防止乱码
}

function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function fetchAllResourcesForCurrentSearch() {
    const searchKeyword = searchInput ? searchInput.value.trim() : '';
    const firstResponse = await fetch(`/admin/api/resources?page=1&page_size=${pageSize}&search=${encodeURIComponent(searchKeyword)}`);
    const firstData = await firstResponse.json();

    if (!firstData.success) {
        throw new Error(firstData.message || '获取资源失败');
    }

    let allItems = [...firstData.data.items];
    const totalP = firstData.data.total_pages || 1;

    if (totalP > 1) {
        const promises = [];
        for (let i = 2; i <= totalP; i++) {
            promises.push(
                fetch(`/admin/api/resources?page=${i}&page_size=${pageSize}&search=${encodeURIComponent(searchKeyword)}`)
                    .then(response => response.json())
                    .then(data => data.success ? data.data.items : [])
            );
        }

        const results = await Promise.all(promises);
        results.forEach(items => {
            allItems = allItems.concat(items);
        });
    }

    return allItems;
}

async function selectAllResources() {
    if (!selectAllResourcesBtn) return;

    const originalText = selectAllResourcesBtn.innerHTML;
    selectAllResourcesBtn.disabled = true;
    selectAllResourcesBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 选择中';

    try {
        const allItems = await fetchAllResourcesForCurrentSearch();
        allItems.forEach(resource => selectedResourceMap.set(resource.id, resource));
        document.querySelectorAll('.resource-row-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });
        updateSelectionUI();
        showToast(`已选择 ${allItems.length} 条资源`, 'success');
    } catch (error) {
        showToast('选择全部失败: ' + error.message, 'danger');
    } finally {
        selectAllResourcesBtn.disabled = false;
        selectAllResourcesBtn.innerHTML = originalText;
    }
}

function exportSelectedResources() {
    const selectedResources = Array.from(selectedResourceMap.values());
    if (selectedResources.length === 0) {
        showToast('请先选择要导出的资源', 'warning');
        return;
    }

    const csv = convertToCSV(selectedResources);
    downloadCSV(csv, `资源列表_已选${selectedResources.length}条_${new Date().toISOString().slice(0, 10)}.csv`);
    showToast(`成功导出 ${selectedResources.length} 条资源`, 'success');
}

async function deleteSelectedResources() {
    const selectedIds = Array.from(selectedResourceMap.keys());
    if (selectedIds.length === 0) {
        showToast('请先选择要删除的资源', 'warning');
        return;
    }

    if (!await showConfirm(`确定删除已选择的 ${selectedIds.length} 条资源吗？此操作不可撤销。`, 'danger')) {
        return;
    }

    const originalText = deleteSelectedBtn ? deleteSelectedBtn.innerHTML : '';
    if (deleteSelectedBtn) {
        deleteSelectedBtn.disabled = true;
        deleteSelectedBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 删除中';
    }

    let successCount = 0;

    try {
        for (const id of selectedIds) {
            const response = await fetch(`/admin/api/resources/${id}`, { method: 'DELETE' });
            const data = await response.json();
            if (response.ok && data.success) {
                successCount++;
                selectedResourceMap.delete(id);
            }
        }

        showToast(`删除完成：成功 ${successCount} 条，失败 ${selectedIds.length - successCount} 条`, successCount === selectedIds.length ? 'success' : 'warning');
        await loadResources();
    } catch (error) {
        showToast('批量删除失败: ' + error.message, 'danger');
    } finally {
        if (deleteSelectedBtn) {
            deleteSelectedBtn.disabled = false;
            deleteSelectedBtn.innerHTML = originalText;
        }
        updateSelectionUI();
    }
}

// ==========================================
// 8. 初始化入口 (统一)
// ==========================================

function initResourcePage() {
    // 初始加载
    loadResources();
    loadNetdiskCredentials();
    setBatchResourceMode('import');

    // 监听分享链接输入以实时刷新转存识别提示
    const shareLinkEl = document.getElementById('resourceShareLink');
    if (shareLinkEl) {
        ['input', 'change', 'paste', 'blur'].forEach(evt => {
            shareLinkEl.addEventListener(evt, () => {
                setTimeout(updateSingleLinkTransferHint, 50);
            });
        });
    }

    // 绑定分页点击事件 (委托)
    if (pagination) {
        pagination.addEventListener('click', (e) => {
            e.preventDefault();
            const target = e.target.closest('a');
            if (target) {
                const page = parseInt(target.getAttribute('data-page'));
                if (!isNaN(page) && page >= 1 && page <= totalPages && page !== currentPage) {
                    currentPage = page;
                    loadResources();
                }
            }
        });
    }

    if (selectCurrentPageCheckbox) {
        selectCurrentPageCheckbox.addEventListener('change', () => {
            if (selectCurrentPageCheckbox.checked) {
                selectCurrentPageResources();
            } else {
                resourcesData.forEach(resource => selectedResourceMap.delete(resource.id));
                document.querySelectorAll('.resource-row-checkbox').forEach(checkbox => {
                    checkbox.checked = false;
                });
                updateSelectionUI();
            }
        });
    }

    if (selectCurrentPageBtn) selectCurrentPageBtn.addEventListener('click', selectCurrentPageResources);
    if (selectAllResourcesBtn) selectAllResourcesBtn.addEventListener('click', selectAllResources);
    if (clearSelectionBtn) clearSelectionBtn.addEventListener('click', clearResourceSelection);
    if (exportSelectedBtn) exportSelectedBtn.addEventListener('click', exportSelectedResources);
    if (deleteSelectedBtn) deleteSelectedBtn.addEventListener('click', deleteSelectedResources);

    if (auditAllResourcesBtn) {
        auditAllResourcesBtn.addEventListener('click', async function () {
            if (this.disabled) return;
            const originalHtml = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin text-[10px]"></i> 正在巡检...';
            showToast('已启动全盘资源健康巡检，请稍候...', 'info');

            try {
                const resp = await fetch('/admin/api/resources/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ limit: 100 })
                });
                const data = await resp.json();
                if (data.success && data.data) {
                    const d = data.data;
                    showToast(`巡检完成: 共检测 ${d.total} 条，有效 ${d.ok_count} 条，失效 ${d.bad_count} 条，需提取码 ${d.locked_count} 条`, 'success');
                    loadResources();
                } else {
                    showToast(data.message || '巡检失败', 'danger');
                }
            } catch (err) {
                showToast('巡检请求异常: ' + err.message, 'danger');
            } finally {
                this.disabled = false;
                this.innerHTML = originalHtml;
            }
        });
    }

    if (auditSelectedBtn) {
        auditSelectedBtn.addEventListener('click', async function () {
            const selectedIds = Array.from(selectedResourceMap.keys());
            if (selectedIds.length === 0) {
                showToast('请先选择需要巡检的资源', 'warning');
                return;
            }

            const originalHtml = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 巡检中...';

            try {
                const resp = await fetch('/admin/api/resources/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids: selectedIds })
                });
                const data = await resp.json();
                if (data.success && data.data) {
                    const d = data.data;
                    showToast(`所选巡检完成: 检测 ${d.total} 条，有效 ${d.ok_count} 条，失效 ${d.bad_count} 条`, 'success');
                    loadResources();
                } else {
                    showToast(data.message || '巡检失败', 'danger');
                }
            } catch (err) {
                showToast('巡检请求异常: ' + err.message, 'danger');
            } finally {
                this.disabled = false;
                this.innerHTML = originalHtml;
            }
        });
    }

    if (cleanupDeadResourcesBtn) {
        cleanupDeadResourcesBtn.addEventListener('click', async function () {
            if (!confirm('确定要清理资源库中所有检测为失效 (bad) 的死链资源吗？此操作将同时清理网盘物理文件并删除数据库记录。')) {
                return;
            }

            const originalHtml = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin text-[10px]"></i> 正在清理...';

            try {
                const resp = await fetch('/admin/api/resources/cleanup-dead', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ limit: 200 })
                });
                const data = await resp.json();
                if (data.success) {
                    showToast(data.message || '清理完成', 'success');
                    loadResources();
                } else {
                    showToast(data.message || '清理失败', 'danger');
                }
            } catch (err) {
                showToast('清理请求失败: ' + err.message, 'danger');
            } finally {
                this.disabled = false;
                this.innerHTML = originalHtml;
            }
        });
    }

    if (batchImportResourceBtn) {
        batchImportResourceBtn.addEventListener('click', () => {
            const batchToggle = document.getElementById('batchResourceTransferToggle');
            if (batchToggle) batchToggle.checked = false;
            toggleBatchTransferOptions(false);
        });
    }

    const addResourceModal = document.getElementById('addResourceModal');
    if (addResourceModal) {
        addResourceModal.addEventListener('hidden.bs.modal', () => {
            if (addResourceForm) addResourceForm.reset();
            const singleToggle = document.getElementById('singleResourceTransferToggle');
            if (singleToggle) singleToggle.checked = false;
            toggleSingleTransferOptions(false);
        });
    }

    if (batchAddResourceModal) {
        batchAddResourceModal.addEventListener('hidden.bs.modal', () => {
            if (batchAddResourceForm) batchAddResourceForm.reset();
            const batchToggle = document.getElementById('batchResourceTransferToggle');
            if (batchToggle) batchToggle.checked = false;
            toggleBatchTransferOptions(false);
        });
    }

    if (pageSizeSelect) {
        pageSizeSelect.value = String(pageSize);
        pageSizeSelect.addEventListener('change', () => {
            pageSize = parseInt(pageSizeSelect.value, 10) || 50;
            currentPage = 1;
            loadResources();
        });
    }

    if (jumpPageBtn) {
        jumpPageBtn.addEventListener('click', jumpToPage);
    }

    if (jumpPageInput) {
        jumpPageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                jumpToPage();
            }
        });
    }

    // 绑定搜索
    if (searchInput) {
        let timeout = null;
        searchInput.addEventListener('input', () => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                clearResourceSelection();
                currentPage = 1;
                loadResources();
            }, 300); // 防抖
        });
    }

    // 绑定按钮事件
    if (saveResourceBtn) saveResourceBtn.addEventListener('click', saveResource);
    if (updateResourceBtn) updateResourceBtn.addEventListener('click', updateResource);
    if (batchSaveResourceBtn) batchSaveResourceBtn.addEventListener('click', batchSaveResources);
}

// 暴露全局方法确保模态框与内联事件始终可用
window.batchSaveResources = batchSaveResources;
window.saveResource = saveResource;
window.updateResource = updateResource;
window.toggleSingleTransferOptions = toggleSingleTransferOptions;
window.toggleBatchTransferOptions = toggleBatchTransferOptions;
window.initResourcePage = initResourcePage;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initResourcePage);
} else {
    initResourcePage();
}
