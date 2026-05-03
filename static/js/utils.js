// 通用工具函数

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatModalMessage(message) {
    return escapeHtml(message).replace(/\n/g, '<br>');
}

/**
 * 显示提示消息
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型：success, danger, warning, info
 * @param {number} delay - 自动关闭延迟时间（毫秒）
 */
function showToast(message, type = 'success', delay = 3000) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    // 创建 Toast 元素
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0 position-fixed end-0 m-3`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.style.zIndex = '1060'; // 确保在最上层

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    // 计算当前显示的toast数量，设置适当的bottom偏移量
    const visibleToasts = document.querySelectorAll('.toast.show');
    const toastHeight = 60; // 大概估算每个toast的高度（包括margin）
    const bottomOffset = visibleToasts.length * toastHeight + 10; // 10px为初始底部边距
    toast.style.bottom = `${bottomOffset}px`;

    toastContainer.appendChild(toast);
    const bootstrapToast = new bootstrap.Toast(toast, { delay });
    bootstrapToast.show();

    // 自动移除元素，避免DOM堆积
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
        // 重新计算并调整剩余toast的位置
        const remainingToasts = document.querySelectorAll('.toast.show');
        remainingToasts.forEach((t, index) => {
            t.style.bottom = `${index * toastHeight + 10}px`;
        });
    });
}

/**
 * 显示提示对话框：替代浏览器原生 alert 的统一模态框
 * @param {string} message - 提示内容
 * @param {string} type - 对话框类型：primary, danger, warning, success, info
 * @param {string} title - 对话框标题
 * @param {string} confirmText - 确认按钮文案
 * @returns {Promise<void>}
 */
function showAlertModal(message, type = 'primary', title = '提示', confirmText = '我知道了') {
    return new Promise((resolve) => {
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal fade';
        modalContainer.setAttribute('tabindex', '-1');

        const iconMap = {
            danger: '<i class="fas fa-circle-xmark text-danger me-2"></i>',
            warning: '<i class="fas fa-triangle-exclamation text-warning me-2"></i>',
            success: '<i class="fas fa-circle-check text-success me-2"></i>',
            info: '<i class="fas fa-circle-info text-primary me-2"></i>',
            primary: '<i class="fas fa-circle-info text-primary me-2"></i>'
        };

        modalContainer.innerHTML = `
            <div class="modal-dialog modal-dialog-centered alert-modal-dialog">
                <div class="modal-content shadow border-0">
                    <div class="modal-header border-0 pb-0">
                        <h5 class="modal-title" style="font-size: 1.1rem; font-weight: 600;">
                            ${iconMap[type] || iconMap.primary}${escapeHtml(title)}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary" style="line-height: 1.7; word-break: break-word;">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-${type === 'info' ? 'primary' : type} btn-sm px-3" data-bs-dismiss="modal">${escapeHtml(confirmText)}</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const bsModal = new bootstrap.Modal(modalContainer);

        modalContainer.addEventListener('hidden.bs.modal', () => {
            modalContainer.remove();
            resolve();
        }, { once: true });

        bsModal.show();
    });
}

/**
 * 显示确认对话框：支持异步与样式的通用确认对话框
 * @param {string} message - 确认消息内容
 * @param {string} type - 对话框类型：primary, danger, warning（可选，默认"primary"）
 * @param {string} title - 对话框标题（可选，默认"确认操作"）
 * @returns {Promise<boolean>} - 确认返回true，取消返回false
 */
function showConfirm(message, type = 'primary', title = '确认操作') {
    return new Promise((resolve) => {
        const modalId = 'dynamicConfirmModal';
        
        // 创建模态框容器
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal fade';
        modalContainer.id = modalId;
        modalContainer.setAttribute('tabindex', '-1');

        // 映射图标样式
        const iconMap = {
            danger: '<i class="fas fa-exclamation-circle text-danger me-2"></i>',
            warning: '<i class="fas fa-exclamation-triangle text-warning me-2"></i>',
            primary: '<i class="fas fa-info-circle text-primary me-2"></i>'
        };

        modalContainer.innerHTML = `
            <div class="modal-dialog modal-dialog-centered modal-sm">
                <div class="modal-content shadow border-0">
                    <div class="modal-header border-0 pb-0">
                        <h5 class="modal-title" style="font-size: 1.1rem; font-weight: 600;">
                            ${iconMap[type] || ''}${escapeHtml(title)}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-light btn-sm px-3" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-${type} btn-sm px-3" id="confirmActionBtn">确认</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const bsModal = new bootstrap.Modal(modalContainer);

        const confirmBtn = modalContainer.querySelector('#confirmActionBtn');

        // 核心逻辑：点击确认返回 true
        confirmBtn.onclick = () => {
            bsModal.hide();
            resolve(true);
        };

        // 隐藏即销毁：无论点击背景、取消、还是确认，最终都会触发 hidden
        modalContainer.addEventListener('hidden.bs.modal', () => {
            resolve(false); // 如果 resolve 已经触发过 true，这里再次 resolve 不会生效
            modalContainer.remove();
        });

        bsModal.show();
    });
}
