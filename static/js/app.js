

/* ============================================================
   1. TRANG UPLOAD — index.html
   ============================================================ */

function initUploadPage() {
    const dropZone   = document.getElementById('dropZone');
    const fileInput  = document.getElementById('fileInput');
    const uploadBtn  = document.getElementById('uploadBtn');
    if (!dropZone) return; 

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) applySelectedFile(file);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) applySelectedFile(fileInput.files[0]);
    });

    uploadBtn.addEventListener('click', handleUpload);

    function applySelectedFile(file) {
        const allowedExt = ['.mp4', '.avi', '.mov', '.mkv'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExt.includes(ext)) {
            showUploadError('Định dạng không hỗ trợ: ' + ext + '. Chỉ chấp nhận: mp4, avi, mov, mkv');
            return;
        }
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;

        document.getElementById('dropDefault').style.display = 'none';
        document.getElementById('dropSelected').style.display = 'block';
        document.getElementById('selectedFileName').textContent = file.name;
        document.getElementById('selectedFileSize').textContent = formatFileSize(file.size);
        dropZone.classList.add('has-file');
        uploadBtn.disabled = false;
        hideUploadError();
    }

    function handleUpload() {
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        uploadBtn.disabled = true;
        document.getElementById('uploadProgress').style.display = 'block';
        hideUploadError();

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                document.getElementById('progressBar').style.width = pct + '%';
                document.getElementById('progressPercent').textContent = pct + '%';
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                window.location.href = '/view/' + data.job_id;
            } else {
                let errMsg = 'Upload thất bại.';
                try { errMsg = JSON.parse(xhr.responseText).detail || errMsg; } catch {}
                showUploadError(errMsg);
                uploadBtn.disabled = false;
                document.getElementById('uploadProgress').style.display = 'none';
            }
        };

        xhr.onerror = () => {
            showUploadError('Không thể kết nối đến server. Kiểm tra server đã chạy chưa.');
            uploadBtn.disabled = false;
        };

        xhr.send(formData);
    }

    function showUploadError(msg) {
        const el = document.getElementById('uploadError');
        el.textContent = msg;
        el.style.display = 'block';
    }
    function hideUploadError() {
        document.getElementById('uploadError').style.display = 'none';
    }
}


/* ============================================================
   2. TRANG VIEW — view.html
   ============================================================ */

function initViewPage() {
    const jobId = window.CURRENT_JOB_ID;
    if (!jobId) return;

    let violationCount = 0;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/${jobId}`);

    ws.onopen = () => {
        console.log('[WS] Đã kết nối: job ' + jobId);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'frame') {
            handleFrame(msg.data);
        } else if (msg.type === 'violation') {
            handleViolation(msg.data);
        } else if (msg.type === 'done') {
            handleDone(msg.total);
        } else if (msg.type === 'error') {
            handleError(msg.message);
        }
    };

    ws.onerror = (e) => {
        console.error('[WS] Lỗi WebSocket:', e);
    };

    ws.onclose = () => {
        console.log('[WS] WebSocket đã đóng.');
    };

    function handleFrame(base64Data) {
        const img = document.getElementById('videoFeed');
        const placeholder = document.getElementById('videoPlaceholder');
        const fpsIndicator = document.getElementById('fpsIndicator');

        if (img.style.display === 'none') {
            placeholder.style.display = 'none';
            img.style.display = 'block';
            fpsIndicator.style.display = 'inline-block';
        }
        img.src = 'data:image/jpeg;base64,' + base64Data;
    }

    function handleViolation(violation) {
        violationCount++;
        document.getElementById('totalCount').textContent = violationCount;
        document.getElementById('violationCount').textContent = violationCount;

        document.getElementById('noViolationMsg').style.display = 'none';

        const rawFile        = getBasename(violation.image_raw);
        const annotatedFile  = getBasename(violation.image_annotated);
        const confPct        = (violation.confidence * 100).toFixed(1);
        const timeStr        = formatTimestamp(violation.timestamp);

        const card = document.createElement('div');
        card.className = 'card v-card mb-2';
        card.id = 'vcard-' + violation.id;
        card.innerHTML = `
            <div class="card-header bg-danger bg-opacity-10 py-2 d-flex justify-content-between align-items-center">
                <span class="small fw-semibold text-danger">Vi Phạm #${violationCount}</span>
                <span class="text-muted small">${timeStr}</span>
            </div>
            <div class="card-body p-2">
                <p class="small text-muted mb-2">ID Xe: <strong>${violation.bike_id}</strong> &nbsp;|&nbsp; Độ tin cậy: <strong>${confPct}%</strong></p>
                <div class="row g-1 mb-2">
                    <div class="col-6">
                        <p class="text-muted mb-1" style="font-size:0.7rem;">Ảnh gốc</p>
                        <img id="img-raw-${violation.id}"
                             class="w-100 rounded border" alt="Đang tải...">
                    </div>
                    <div class="col-6">
                        <p class="text-muted mb-1" style="font-size:0.7rem;">Ảnh khoanh vùng</p>
                        <img id="img-ann-${violation.id}"
                             class="w-100 rounded border" alt="Đang tải...">
                    </div>
                </div>
                <div class="d-flex gap-1" id="actions-${violation.id}">
                    <button class="btn btn-success btn-sm flex-fill"
                            onclick="confirmFromView(${violation.id})">
                        Xác Nhận
                    </button>
                    <button class="btn btn-outline-secondary btn-sm flex-fill"
                            onclick="rejectFromView(${violation.id})">
                        Hủy Bỏ
                    </button>
                </div>
                <div id="actionResult-${violation.id}" class="mt-1 text-center small" style="display:none;"></div>
            </div>
        `;

        const panel = document.getElementById('violationsPanel');
        panel.insertBefore(card, panel.querySelector('.card') || null);
        panel.scrollTop = 0;

        // Load ảnh với cơ chế retry — dự phòng nếu server chưa kịp ghi file
        // Retry tối đa 5 lần, mỗi lần cách 600ms (tổng cộng 3 giây chờ tối đa)
        loadImgWithRetry(
            document.getElementById('img-raw-' + violation.id),
            `/api/images/${rawFile}`
        );
        loadImgWithRetry(
            document.getElementById('img-ann-' + violation.id),
            `/api/images/${annotatedFile}`
        );
    }

    function handleDone(total) {
        document.getElementById('statusBadge').className = 'badge bg-success fs-6 px-3 py-2';
        document.getElementById('statusBadge').textContent = 'Hoàn tất';

        const doneAlert = document.getElementById('doneAlert');
        document.getElementById('doneSummary').textContent =
            `Tìm thấy ${total} trường hợp vi phạm trong video.`;
        doneAlert.style.display = 'flex';

        document.getElementById('fpsIndicator').style.display = 'none';
    }

    function handleError(message) {
        document.getElementById('statusBadge').className = 'badge bg-danger fs-6 px-3 py-2';
        document.getElementById('statusBadge').textContent = 'Lỗi';
        console.error('[WS] Lỗi từ server:', message);
    }
}

async function confirmFromView(id) {
    const result = await apiUpdateStatus(id, 'confirm');
    if (result) updateViewCard(id, 'confirmed');
}

async function rejectFromView(id) {
    const result = await apiUpdateStatus(id, 'reject');
    if (result) updateViewCard(id, 'rejected');
}

function updateViewCard(id, status) {
    const actions = document.getElementById('actions-' + id);
    const result  = document.getElementById('actionResult-' + id);
    if (actions) actions.style.display = 'none';
    if (result) {
        result.style.display = 'block';
        if (status === 'confirmed') {
            result.innerHTML = '<span class="badge bg-success">Đã xác nhận vi phạm</span>';
        } else {
            result.innerHTML = '<span class="badge bg-secondary">Đã hủy bỏ</span>';
        }
    }
    const card = document.getElementById('vcard-' + id);
    if (card) {
        card.classList.remove('v-card');
        card.classList.add(status === 'confirmed' ? 'confirmed' : 'rejected');
        card.style.borderLeftColor = status === 'confirmed' ? '#198754' : '#6c757d';
    }
}


/* ============================================================
   3. TRANG DASHBOARD — dashboard.html
   ============================================================ */

let currentFilter = '';         
let allViolations = [];         
let evidenceModal = null;       

function initDashboardPage() {
    if (!document.getElementById('violationsTableBody')) return;

    evidenceModal = new bootstrap.Modal(document.getElementById('evidenceModal'));

    // Bắt sự kiện lọc theo trạng thái
    document.querySelectorAll('#filterBtns button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#filterBtns button').forEach(b => {
                b.classList.remove('active', 'btn-dark');
                b.classList.add('btn-outline-dark');
            });
            btn.classList.add('active', 'btn-dark');
            btn.classList.remove('btn-outline-dark');
            currentFilter = btn.dataset.filter;
            loadDashboard();
        });
    });

    // Bắt sự kiện tìm kiếm tức thời
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            handleLiveSearch();
        });
    }

    loadDashboard();
}

function handleLiveSearch() {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    const term = (searchInput ? searchInput.value : '').trim().toLowerCase();

    if (clearBtn) {
        clearBtn.style.display = term ? 'inline-block' : 'none';
    }

    if (!term) {
        renderTable(allViolations);
        return;
    }

    const filtered = allViolations.filter(v => {
        const bikeIdStr = String(v.bike_id).toLowerCase();
        const videoNameStr = String(v.video_name || '').toLowerCase();
        const idStr = String(v.id).toLowerCase();
        return bikeIdStr.includes(term) || videoNameStr.includes(term) || idStr.includes(term);
    });

    renderTable(filtered, true);
}

function clearSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.value = '';
    }
    handleLiveSearch();
}

async function loadDashboard() {
    await Promise.all([loadStats(), loadViolations()]);
}

async function loadStats() {
    const stats = await apiFetch('/api/stats');
    if (!stats) return;
    document.getElementById('statTotal').textContent     = stats.total;
    document.getElementById('statPending').textContent   = stats.pending;
    document.getElementById('statConfirmed').textContent = stats.confirmed;
    document.getElementById('statRejected').textContent  = stats.rejected;
}

async function loadViolations() {
    document.getElementById('tableLoading').style.display = 'block';
    document.getElementById('tableWrapper').style.display = 'none';
    document.getElementById('tableEmpty').style.display   = 'none';
    
    // Clear bảng cũ tránh hiển thị đè dữ liệu cũ khi đang tải
    document.getElementById('violationsTableBody').innerHTML = '';

    const url = currentFilter ? `/api/violations?status=${currentFilter}` : '/api/violations';
    const data = await apiFetch(url);
    document.getElementById('tableLoading').style.display = 'none';

    if (!data) {
        document.getElementById('tableEmpty').style.display = 'block';
        return;
    }
    allViolations = data.violations;

    if (allViolations.length === 0) {
        document.getElementById('tableEmpty').style.display = 'block';
        return;
    }

    // Nếu đang có từ khóa tìm kiếm thì áp dụng tìm kiếm luôn
    const searchInput = document.getElementById('searchInput');
    if (searchInput && searchInput.value.trim()) {
        handleLiveSearch();
    } else {
        renderTable(allViolations);
    }
}

function renderTable(violations, isFiltered = false) {
    const tbody = document.getElementById('violationsTableBody');
    const tableWrapper = document.getElementById('tableWrapper');
    const tableEmpty = document.getElementById('tableEmpty');
    const emptyMsg = document.getElementById('emptyMessage');

    tbody.innerHTML = '';

    if (violations.length === 0) {
        tableWrapper.style.display = 'none';
        tableEmpty.style.display = 'block';
        if (emptyMsg) {
            emptyMsg.textContent = isFiltered 
                ? 'Không tìm thấy kết quả phù hợp với từ khóa tìm kiếm.' 
                : 'Chưa có vi phạm nào trong danh mục này.';
        }
        return;
    }

    tableEmpty.style.display = 'none';
    tableWrapper.style.display = 'block';

    violations.forEach(v => {
        const confPct  = (v.confidence * 100).toFixed(1);
        const timeStr  = formatTimestamp(v.timestamp);
        const badgeHtml = statusBadge(v.status);
        
        let actionButtons = '';
        if (v.status === 'pending') {
            actionButtons = `
                <button class="btn btn-success btn-sm py-0 px-2 me-1" title="Xác nhận" onclick="dashConfirm(${v.id}, event)">Duyệt</button>
                <button class="btn btn-outline-secondary btn-sm py-0 px-2 me-1" title="Hủy" onclick="dashReject(${v.id}, event)">Hủy</button>
            `;
        }
        actionButtons += `<button class="btn btn-outline-danger btn-sm py-0 px-2" title="Xóa vi phạm" onclick="dashDelete(${v.id}, event)">Xóa</button>`;

        const tr = document.createElement('tr');
        tr.id = 'row-' + v.id;
        tr.innerHTML = `
            <td class="ps-3 text-muted small">#${v.id}</td>
            <td class="small">${timeStr}</td>
            <td><strong>${v.bike_id}</strong></td>
            <td>
                <div class="progress" style="height:6px; width:80px;">
                    <div class="progress-bar bg-danger" style="width:${confPct}%"></div>
                </div>
                <small class="text-muted">${confPct}%</small>
            </td>
            <td class="small text-muted" style="max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                title="${v.video_name}">${v.video_name}</td>
            <td id="badge-${v.id}">${badgeHtml}</td>
            <td class="text-center" id="action-${v.id}">${actionButtons}</td>
        `;
        tr.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            openEvidenceModal(v);
        });
        tbody.appendChild(tr);
    });
}

async function dashConfirm(id, event) {
    if (event) event.stopPropagation();
    const result = await apiUpdateStatus(id, 'confirm');
    if (result) {
        // Cập nhật mảng local
        const item = allViolations.find(x => x.id === id);
        if (item) item.status = 'confirmed';
        
        const badgeEl = document.getElementById('badge-' + id);
        const actionEl = document.getElementById('action-' + id);
        if (badgeEl) badgeEl.innerHTML = statusBadge('confirmed');
        if (actionEl) actionEl.innerHTML = `<button class="btn btn-outline-danger btn-sm py-0 px-2" title="Xóa" onclick="dashDelete(${id}, event)">Xóa</button>`;
        
        await loadStats(); 
    }
}

async function dashReject(id, event) {
    if (event) event.stopPropagation();
    const result = await apiUpdateStatus(id, 'reject');
    if (result) {
        // Cập nhật mảng local
        const item = allViolations.find(x => x.id === id);
        if (item) item.status = 'rejected';

        const badgeEl = document.getElementById('badge-' + id);
        const actionEl = document.getElementById('action-' + id);
        if (badgeEl) badgeEl.innerHTML = statusBadge('rejected');
        if (actionEl) actionEl.innerHTML = `<button class="btn btn-outline-danger btn-sm py-0 px-2" title="Xóa" onclick="dashDelete(${id}, event)">Xóa</button>`;
        
        await loadStats();
    }
}

async function dashDelete(id, event) {
    if (event) event.stopPropagation();
    if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn vi phạm #${id}?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/violations/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        // Xóa khỏi bảng giao diện
        allViolations = allViolations.filter(x => x.id !== id);
        const row = document.getElementById('row-' + id);
        if (row) row.remove();

        await loadStats();

        if (allViolations.length === 0) {
            document.getElementById('tableWrapper').style.display = 'none';
            document.getElementById('tableEmpty').style.display = 'block';
        }
    } catch (e) {
        console.error('[API] Lỗi khi xóa vi phạm ID=' + id, e);
        alert('Lỗi: Không thể xóa vi phạm.');
    }
}

async function confirmClearData(mode) {
    const isAll = mode === 'all';
    const msg = isAll 
        ? 'CẢNH BÁO: Thao tác này sẽ XÓA TOÀN BỘ lịch sử vi phạm khỏi hệ thống. Bạn có chắc chắn muốn tiếp tục?' 
        : 'Bạn có chắc chắn muốn xóa toàn bộ các mục có trạng thái "Đã Hủy"?';
    
    if (!confirm(msg)) return;

    try {
        const url = isAll ? '/api/violations/clear' : '/api/violations/clear?status=rejected';
        const res = await fetch(url, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        alert(data.message || 'Dọn dẹp dữ liệu thành công.');
        loadDashboard();
    } catch (e) {
        console.error('[API] Lỗi khi dọn dẹp dữ liệu', e);
        alert('Lỗi: Không thể dọn dẹp dữ liệu.');
    }
}

function openEvidenceModal(v) {
    const rawFile        = getBasename(v.image_raw);
    const annotatedFile  = getBasename(v.image_annotated);
    const confPct        = (v.confidence * 100).toFixed(1);

    document.getElementById('modalTitle').textContent = `Vi Phạm #${v.id} — Xe ID ${v.bike_id}`;
    document.getElementById('modalImgRaw').src        = `/api/images/${rawFile}`;
    document.getElementById('modalImgAnnotated').src  = `/api/images/${annotatedFile}`;
    document.getElementById('modalInfo').innerHTML    = `
        <div class="row small text-muted">
            <div class="col-auto"><strong>Thời gian:</strong> ${formatTimestamp(v.timestamp)}</div>
            <div class="col-auto"><strong>Độ tin cậy:</strong> ${confPct}%</div>
            <div class="col-auto"><strong>Video:</strong> ${v.video_name}</div>
            <div class="col-auto"><strong>Trạng thái:</strong> ${statusBadge(v.status)}</div>
        </div>
    `;

    const footer = document.getElementById('modalActions');
    let actionsHtml = `<button class="btn btn-outline-danger me-auto" onclick="dashDeleteModal(${v.id})">Xóa Hồ Sơ</button>`;
    
    if (v.status === 'pending') {
        actionsHtml += `
            <button class="btn btn-success" onclick="dashConfirmModal(${v.id})">Xác Nhận Vi Phạm</button>
            <button class="btn btn-outline-secondary" onclick="dashRejectModal(${v.id})">Hủy Bỏ</button>
        `;
    } else {
        actionsHtml += `<span class="align-self-center">${statusBadge(v.status)}</span>`;
    }

    footer.innerHTML = actionsHtml;
    evidenceModal.show();
}

async function dashConfirmModal(id) {
    const result = await apiUpdateStatus(id, 'confirm');
    if (result) {
        evidenceModal.hide();
        loadDashboard();
    }
}

async function dashRejectModal(id) {
    const result = await apiUpdateStatus(id, 'reject');
    if (result) {
        evidenceModal.hide();
        loadDashboard();
    }
}

async function dashDeleteModal(id) {
    if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn vi phạm #${id}?`)) {
        return;
    }
    try {
        const res = await fetch(`/api/violations/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        evidenceModal.hide();
        loadDashboard();
    } catch (e) {
        console.error('[API] Lỗi khi xóa vi phạm ID=' + id, e);
        alert('Lỗi: Không thể xóa vi phạm.');
    }
}


/* ============================================================
   4. HÀM DÙNG CHUNG (SHARED)
   ============================================================ */

/**

 *
 * @param {HTMLImageElement} imgEl   - Thẻ <img> cần load
 * @param {string}           src     - URL gốc của ảnh
 * @param {number}           maxTries - Số lần thử tối đa (default: 5)
 * @param {number}           delay   - Khoảng cách giữa mỗi lần thử ms (default: 600)
 */
function loadImgWithRetry(imgEl, src, maxTries = 5, delay = 600) {
    let attempts = 0;

    function tryLoad() {
        imgEl.onload = null;
        imgEl.onerror = null;

        imgEl.onload = function () {
            // Load thành công — xóa timestamp khỏi alt text
            imgEl.alt = '';
        };

        imgEl.onerror = function () {
            attempts++;
            if (attempts < maxTries) {
                // Thêm ?t=timestamp để bypass browser cache
                setTimeout(() => {
                    imgEl.src = src + '?t=' + Date.now();
                    tryLoad();
                }, delay);
            } else {
                imgEl.alt = 'Không tải được ảnh';
                imgEl.style.border = '1px dashed #ccc';
            }
        };

        // Lần đầu dùng URL gốc, các lần retry thêm cache-buster
        if (attempts === 0) {
            imgEl.src = src;
        }
    }

    tryLoad();
}

async function apiFetch(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('[API] Lỗi khi gọi', url, e);
        return null;
    }
}

async function apiUpdateStatus(id, action) {
    try {
        const res = await fetch(`/api/violations/${id}/${action}`, { method: 'PATCH' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('[API] Không thể cập nhật trạng thái ID=' + id, e);
        alert('Lỗi: Không thể cập nhật trạng thái. Kiểm tra kết nối server.');
        return null;
    }
}

function getBasename(path) {
    if (!path) return '';
    return path.split(/[/\\]/).pop();
}

function formatTimestamp(ts) {
    if (!ts) return '—';
    try {
        const match = ts.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
        if (!match) return ts;
        const [, y, mo, d, h, mi, s] = match;
        return `${d}/${mo}/${y} ${h}:${mi}:${s}`;
    } catch {
        return ts;
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024)        return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function statusBadge(status) {
    const map = {
        'pending'  : '<span class="badge badge-pending">Chờ duyệt</span>',
        'confirmed': '<span class="badge badge-confirmed text-white">Xác nhận</span>',
        'rejected' : '<span class="badge badge-rejected text-white">Đã hủy</span>',
    };
    return map[status] || `<span class="badge bg-secondary">${status}</span>`;
}
