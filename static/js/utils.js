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
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-ui-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    // 计算当前显示的toast数量，设置适当的bottom偏移量
    const visibleToasts = document.querySelectorAll('.toast.show');
    const toastHeight = 60; // 大概估算每个toast的高度（包括margin）
    const bottomOffset = visibleToasts.length * toastHeight + 10; // 10px为初始底部边距
    toast.style.bottom = `${bottomOffset}px`;

    toastContainer.appendChild(toast);
    toast.classList.add('show');
    toast.style.display = 'block';

    const hideToast = () => {
        toast.classList.remove('show');
        toast.style.display = 'none';
        toast.remove();

        const remainingToasts = document.querySelectorAll('.toast.show');
        remainingToasts.forEach((t, index) => {
            t.style.bottom = `${index * toastHeight + 10}px`;
        });
    };

    const autoHideTimer = window.setTimeout(hideToast, delay);
    const closeButton = toast.querySelector('[data-ui-dismiss="toast"]');
    closeButton?.addEventListener('click', () => {
        window.clearTimeout(autoHideTimer);
        hideToast();
    }, { once: true });
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
                        <button type="button" class="btn-close" data-ui-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary" style="line-height: 1.7; word-break: break-word;">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-${type === 'info' ? 'primary' : type} btn-sm px-3" data-ui-dismiss="modal">${escapeHtml(confirmText)}</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const dismissButtons = modalContainer.querySelectorAll('[data-ui-dismiss="modal"]');

        let settled = false;
        const cleanup = () => {
            if (settled) return;
            settled = true;
            document.removeEventListener('keydown', onKeyDown);
            window.AppUI.closeModal(modalContainer);
            modalContainer.remove();
            resolve();
        };

        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                cleanup();
            }
        };
        document.addEventListener('keydown', onKeyDown);

        dismissButtons.forEach((button) => {
            button.addEventListener('click', cleanup, { once: true });
        });

        modalContainer.addEventListener('click', (event) => {
            if (event.target === modalContainer) {
                cleanup();
            }
        }, { once: true });

        window.AppUI.openModal(modalContainer);
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
        let confirmed = false;
        let settled = false;
        
        // 创建模态框容器
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal fade';
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
                        <button type="button" class="btn-close" data-ui-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-light btn-sm px-3" data-ui-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-${type} btn-sm px-3" id="confirmActionBtn">确认</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const confirmBtn = modalContainer.querySelector('#confirmActionBtn');
        const cancelButtons = modalContainer.querySelectorAll('[data-ui-dismiss="modal"]');

        const cleanup = (result) => {
            if (settled) return;
            settled = true;
            document.removeEventListener('keydown', onKeyDown);
            if (typeof result === 'boolean') {
                resolve(result);
            }
            window.AppUI.closeModal(modalContainer);
            modalContainer.remove();
        };

        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                cleanup(false);
            }
        };
        document.addEventListener('keydown', onKeyDown);

        // 核心逻辑：点击确认返回 true
        confirmBtn.onclick = () => {
            confirmed = true;
            cleanup(true);
        };

        cancelButtons.forEach((button) => {
            button.addEventListener('click', () => {
                cleanup(confirmed ? true : false);
            }, { once: true });
        });

        modalContainer.addEventListener('click', (event) => {
            if (event.target === modalContainer) {
                cleanup(confirmed ? true : false);
            }
        }, { once: true });

        window.AppUI.openModal(modalContainer);
    });
}
