/**
 * TaskFlow AI - Modern Task Management & RAG Assistant JavaScript
 */

// ==========================================
// 1. Helper Functions & Global State
// ==========================================

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function getAuthHeader() {
    const token = getCookie('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function logout() {
    // Expire cookies
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i];
        const eqPos = cookie.indexOf("=");
        const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
    }
    window.location.href = '/auth/login-page';
}

function refreshIcons() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// Toast Notification Manager
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white shadow-emerald-500/20',
        error: 'bg-rose-600 text-white shadow-rose-500/20',
        warning: 'bg-amber-600 text-white shadow-amber-500/20',
        info: 'bg-slate-900 text-white shadow-slate-900/20'
    };

    const icons = {
        success: 'check-circle-2',
        error: 'alert-circle',
        warning: 'alert-triangle',
        info: 'info'
    };

    toast.className = `pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl text-xs font-semibold shadow-lg transition-all transform translate-y-2 opacity-0 ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <i data-lucide="${icons[type] || 'info'}" class="w-4 h-4 shrink-0"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    refreshIcons();

    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    // Remove after 3.5s
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}


// ==========================================
// 2. Authentication Handlers
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    refreshIcons();

    // Login Form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('loginSubmitBtn');
            if (submitBtn) submitBtn.disabled = true;

            const formData = new FormData(loginForm);
            const payload = new URLSearchParams();
            for (const [key, value] of formData.entries()) {
                payload.append(key, value);
            }

            try {
                const response = await fetch('/auth/token', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: payload.toString()
                });

                if (response.ok) {
                    const data = await response.json();
                    document.cookie = `access_token=${data.access_token}; path=/`;
                    showToast('Login successful! Redirecting...', 'success');
                    setTimeout(() => {
                        window.location.href = '/todos/todo-page';
                    }, 500);
                } else {
                    const error = await response.json();
                    showToast(error.detail || 'Invalid username or password', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Unable to connect to authentication server', 'error');
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    }

    // Register Form
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(registerForm);
            const data = Object.fromEntries(formData.entries());

            if (data.password !== data.password2) {
                showToast('Passwords do not match', 'warning');
                return;
            }

            const payload = {
                email: data.email,
                username: data.username,
                first_name: data.firstname,
                last_name: data.lastname,
                role: data.role || 'Member',
                phone_number: data.phone_number,
                password: data.password
            };

            try {
                const response = await fetch('/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    showToast('Account registered successfully! Please sign in.', 'success');
                    setTimeout(() => {
                        window.location.href = '/auth/login-page';
                    }, 800);
                } else {
                    const error = await response.json();
                    showToast(error.detail || error.message || 'Registration failed', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('An error occurred during registration', 'error');
            }
        });
    }
});


// ==========================================
// 3. Task Management & Board Controls
// ==========================================

let currentStatusFilter = 'all';

function setStatusFilter(status) {
    currentStatusFilter = status;
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('bg-white', 'text-slate-900', 'shadow-sm');
        tab.classList.add('text-slate-600');
    });

    const activeTab = document.getElementById(`filter-tab-${status}`);
    if (activeTab) {
        activeTab.classList.add('bg-white', 'text-slate-900', 'shadow-sm');
        activeTab.classList.remove('text-slate-600');
    }

    filterTasks();
}

function filterTasks() {
    const searchVal = (document.getElementById('taskSearchInput')?.value || '').toLowerCase().trim();
    const priorityVal = document.getElementById('priorityFilter')?.value || 'all';

    const cards = document.querySelectorAll('.task-card');
    let visibleCount = 0;

    cards.forEach(card => {
        const title = card.getAttribute('data-title') || '';
        const desc = card.getAttribute('data-desc') || '';
        const complete = card.getAttribute('data-complete') === 'true';
        const priority = parseInt(card.getAttribute('data-priority') || '1');

        // Status match
        let matchesStatus = true;
        if (currentStatusFilter === 'pending') matchesStatus = !complete;
        if (currentStatusFilter === 'completed') matchesStatus = complete;

        // Priority match
        let matchesPriority = true;
        if (priorityVal === 'high') matchesPriority = (priority >= 4);
        else if (priorityVal === 'medium') matchesPriority = (priority === 3);
        else if (priorityVal === 'low') matchesPriority = (priority <= 2);

        // Search match
        const matchesSearch = !searchVal || title.includes(searchVal) || desc.includes(searchVal);

        if (matchesStatus && matchesPriority && matchesSearch) {
            card.classList.remove('hidden');
            visibleCount++;
        } else {
            card.classList.add('hidden');
        }
    });

    const emptyState = document.getElementById('noTasksState');
    if (emptyState) {
        if (visibleCount === 0) emptyState.classList.remove('hidden');
        else emptyState.classList.add('hidden');
    }
}

// Quick Toggle Task Complete
async function toggleTaskComplete(taskId) {
    try {
        const response = await fetch(`/todos/todo/${taskId}/toggle`, {
            method: 'PATCH',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            const card = document.getElementById(`task-card-${taskId}`);
            if (card) {
                card.setAttribute('data-complete', data.complete ? 'true' : 'false');
                const titleEl = card.querySelector('.task-title');
                const statusLabel = card.querySelector('.task-status-label');

                if (data.complete) {
                    titleEl?.classList.add('strike-through-text');
                    card.classList.add('opacity-75', 'bg-slate-50/70');
                    if (statusLabel) statusLabel.textContent = 'Completed';
                    showToast(`Task #${taskId} marked completed`, 'success');
                } else {
                    titleEl?.classList.remove('strike-through-text');
                    card.classList.remove('opacity-75', 'bg-slate-50/70');
                    if (statusLabel) statusLabel.textContent = 'In Progress';
                    showToast(`Task #${taskId} marked in progress`, 'info');
                }
                updateDashboardStats();
                filterTasks();
            }
        } else {
            showToast('Failed to update task status', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Error communicating with server', 'error');
    }
}

function updateDashboardStats() {
    const allCards = document.querySelectorAll('.task-card');
    let total = allCards.length;
    let completed = 0;
    let urgent = 0;

    allCards.forEach(c => {
        const isComplete = c.getAttribute('data-complete') === 'true';
        const p = parseInt(c.getAttribute('data-priority') || '1');
        if (isComplete) completed++;
        else if (p >= 4) urgent++;
    });

    const pending = total - completed;

    const totalEl = document.getElementById('stat-total');
    const pendingEl = document.getElementById('stat-pending');
    const compEl = document.getElementById('stat-completed');
    const urgentEl = document.getElementById('stat-urgent');

    if (totalEl) totalEl.textContent = total;
    if (pendingEl) pendingEl.textContent = pending;
    if (compEl) compEl.textContent = completed;
    if (urgentEl) urgentEl.textContent = urgent;
}

// Modal Handlers
function openCreateModal() {
    const modal = document.getElementById('createTaskModal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('new_task_title')?.focus();
        hideDuplicateAlert();
    }
}

function closeCreateModal() {
    const modal = document.getElementById('createTaskModal');
    if (modal) modal.classList.add('hidden');
    document.getElementById('createTaskForm')?.reset();
    hideDuplicateAlert();
}

function openEditModal(id, title, description, priority, complete) {
    const modal = document.getElementById('editTaskModal');
    if (!modal) return;

    document.getElementById('edit_task_id').value = id;
    document.getElementById('edit_task_title').value = title;
    document.getElementById('edit_task_description').value = description;
    document.getElementById('edit_task_priority').value = priority;
    document.getElementById('edit_task_complete').checked = complete;

    modal.classList.remove('hidden');
}

function closeEditModal() {
    const modal = document.getElementById('editTaskModal');
    if (modal) modal.classList.add('hidden');
}

// Create Task
async function handleCreateTask(e) {
    e.preventDefault();
    const title = document.getElementById('new_task_title').value.trim();
    const description = document.getElementById('new_task_description').value.trim();
    const priority = parseInt(document.getElementById('new_task_priority').value);

    const payload = {
        title: title,
        description: description,
        priority: priority,
        complete: false
    };

    try {
        const response = await fetch('/todos/todo', {
            method: 'POST',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showToast('Task created and indexed in vector store!', 'success');
            closeCreateModal();
            setTimeout(() => window.location.reload(), 400);
        } else {
            const err = await response.json();
            showToast(err.detail || 'Failed to create task', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Error saving task', 'error');
    }
}

// Standalone Create Page
async function handleStandaloneCreate(e) {
    e.preventDefault();
    const form = document.getElementById('standaloneAddTodoForm');
    const formData = new FormData(form);
    const payload = {
        title: formData.get('title'),
        description: formData.get('description'),
        priority: parseInt(formData.get('priority')),
        complete: false
    };

    try {
        const response = await fetch('/todos/todo', {
            method: 'POST',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            window.location.href = '/todos/todo-page';
        } else {
            const err = await response.json();
            showToast(err.detail || 'Error creating task', 'error');
        }
    } catch (err) {
        showToast('Error creating task', 'error');
    }
}

// Edit Task
async function handleEditTask(e) {
    e.preventDefault();
    const id = document.getElementById('edit_task_id').value;
    const title = document.getElementById('edit_task_title').value.trim();
    const description = document.getElementById('edit_task_description').value.trim();
    const priority = parseInt(document.getElementById('edit_task_priority').value);
    const complete = document.getElementById('edit_task_complete').checked;

    const payload = {
        title: title,
        description: description,
        priority: priority,
        complete: complete
    };

    try {
        const response = await fetch(`/todos/todo/${id}`, {
            method: 'PUT',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showToast('Task updated & vector store synced!', 'success');
            closeEditModal();
            setTimeout(() => window.location.reload(), 400);
        } else {
            const err = await response.json();
            showToast(err.detail || 'Failed to update task', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Error updating task', 'error');
    }
}

// Standalone Edit Page
async function handleStandaloneEdit(e, id) {
    e.preventDefault();
    const form = document.getElementById('standaloneEditTodoForm');
    const formData = new FormData(form);
    const payload = {
        title: formData.get('title'),
        description: formData.get('description'),
        priority: parseInt(formData.get('priority')),
        complete: formData.get('complete') === 'on' || formData.get('complete') === 'true'
    };

    try {
        const response = await fetch(`/todos/todo/${id}`, {
            method: 'PUT',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            window.location.href = '/todos/todo-page';
        } else {
            const err = await response.json();
            showToast(err.detail || 'Error editing task', 'error');
        }
    } catch (err) {
        showToast('Error editing task', 'error');
    }
}

// Delete Task
async function deleteTaskPrompt(taskId) {
    if (!confirm(`Are you sure you want to delete task #${taskId}?`)) return;

    try {
        const response = await fetch(`/todos/todo/${taskId}`, {
            method: 'DELETE',
            headers: { ...getAuthHeader() }
        });

        if (response.ok) {
            showToast(`Task #${taskId} deleted and vector removed`, 'success');
            const card = document.getElementById(`task-card-${taskId}`);
            if (card) {
                card.remove();
                updateDashboardStats();
                filterTasks();
            } else {
                window.location.href = '/todos/todo-page';
            }
        } else {
            showToast('Failed to delete task', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Error deleting task', 'error');
    }
}

function deleteFromEditModal() {
    const id = document.getElementById('edit_task_id').value;
    if (id) {
        closeEditModal();
        deleteTaskPrompt(id);
    }
}


// ==========================================
// 4. Real-Time AI Duplicate Detection
// ==========================================

let duplicateCheckTimeout = null;

function debounceDuplicateCheck() {
    clearTimeout(duplicateCheckTimeout);
    duplicateCheckTimeout = setTimeout(runDuplicateCheck, 400);
}

async function runDuplicateCheck() {
    const titleInput = document.getElementById('new_task_title');
    const descInput = document.getElementById('new_task_description');
    const priorityInput = document.getElementById('new_task_priority');

    if (!titleInput) return;
    const title = titleInput.value.trim();
    const desc = descInput ? descInput.value.trim() : '';
    const priority = priorityInput ? parseInt(priorityInput.value) : 1;

    if (title.length < 3) {
        hideDuplicateAlert();
        return;
    }

    try {
        const response = await fetch('/api/v1/ai/detect-duplicates', {
            method: 'POST',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title,
                description: desc,
                priority: priority
            })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.is_duplicate) {
                showDuplicateAlert(data.message, data.highest_similarity);
            } else {
                hideDuplicateAlert();
            }
        }
    } catch (err) {
        console.debug('Duplicate check error:', err);
    }
}

function showDuplicateAlert(message, similarity) {
    const banner = document.getElementById('duplicateAlertBanner');
    const msgEl = document.getElementById('duplicateAlertMsg');
    const titleEl = document.getElementById('duplicateAlertTitle');

    if (banner && msgEl) {
        if (titleEl) titleEl.textContent = `Potential Duplicate Warning (${Math.round(similarity * 100)}% Match)`;
        msgEl.textContent = message;
        banner.classList.remove('hidden');
        refreshIcons();
    }
}

function hideDuplicateAlert() {
    const banner = document.getElementById('duplicateAlertBanner');
    if (banner) banner.classList.add('hidden');
}


// ==========================================
// 5. AI Copilot Drawer & Chat System
// ==========================================

function toggleAiDrawer() {
    const drawer = document.getElementById('aiDrawer');
    const overlay = document.getElementById('aiDrawerOverlay');
    if (!drawer || !overlay) return;

    const isClosed = drawer.classList.contains('translate-x-full');
    if (isClosed) {
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        document.getElementById('aiQueryInput')?.focus();
    } else {
        drawer.classList.add('translate-x-full');
        overlay.classList.add('hidden');
    }
    refreshIcons();
}

function sendQuickPrompt(promptText) {
    const input = document.getElementById('aiQueryInput');
    if (input) {
        input.value = promptText;
        const form = document.getElementById('aiChatForm');
        if (form) {
            form.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    }
}

async function handleAiChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('aiQueryInput');
    const sendBtn = document.getElementById('aiSendBtn');
    if (!input) return;

    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    appendChatMessage('user', query);

    const loadingId = appendChatLoading();
    if (sendBtn) sendBtn.disabled = true;

    try {
        const response = await fetch('/api/v1/ai/ask', {
            method: 'POST',
            headers: {
                ...getAuthHeader(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        });

        removeChatLoading(loadingId);

        if (response.ok) {
            const data = await response.json();
            appendChatMessage('ai', data.answer, data.referenced_task_ids);
        } else {
            const err = await response.json();
            appendChatMessage('ai', `⚠️ Error: ${err.detail || 'Could not process query.'}`);
        }
    } catch (err) {
        console.error(err);
        removeChatLoading(loadingId);
        appendChatMessage('ai', '⚠️ Failed to connect to AI assistant service.');
    } finally {
        if (sendBtn) sendBtn.disabled = false;
    }
}

function appendChatMessage(sender, text, referencedIds = []) {
    const chatContainer = document.getElementById('aiChatMessages');
    if (!chatContainer) return;

    const msgWrapper = document.createElement('div');
    msgWrapper.className = 'flex items-start gap-2.5';

    if (sender === 'user') {
        msgWrapper.className += ' justify-end';
        msgWrapper.innerHTML = `
            <div class="bg-brand-600 text-white p-3 rounded-2xl rounded-tr-sm shadow-xs max-w-[85%] leading-relaxed">
                ${escapeHtml(text)}
            </div>
            <div class="w-6 h-6 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 text-[10px] font-bold">
                You
            </div>
        `;
    } else {
        // Format markdown using marked if available
        let formattedHtml = text;
        if (window.marked) {
            formattedHtml = marked.parse(text);
        }

        let refBadgesHtml = '';
        if (referencedIds && referencedIds.length > 0) {
            refBadgesHtml = `
                <div class="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5">
                    <span class="text-[10px] font-semibold text-slate-400">Referenced:</span>
                    ${referencedIds.map(id => `
                        <button onclick="highlightTaskCard(${id})" class="text-[10px] font-bold px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-colors">
                            #Task ${id}
                        </button>
                    `).join('')}
                </div>
            `;
        }

        msgWrapper.innerHTML = `
            <div class="w-6 h-6 rounded-lg bg-brand-600 text-white flex items-center justify-center shrink-0 text-[10px] font-bold shadow-xs">
                AI
            </div>
            <div class="bg-white p-3 rounded-2xl rounded-tl-sm border border-slate-200/80 shadow-xs max-w-[88%] text-slate-800 leading-relaxed prose prose-xs prose-slate">
                ${formattedHtml}
                ${refBadgesHtml}
            </div>
        `;
    }

    chatContainer.appendChild(msgWrapper);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    refreshIcons();
}

function appendChatLoading() {
    const chatContainer = document.getElementById('aiChatMessages');
    if (!chatContainer) return null;

    const id = 'loading_' + Date.now();
    const loadingWrapper = document.createElement('div');
    loadingWrapper.id = id;
    loadingWrapper.className = 'flex items-start gap-2.5';
    loadingWrapper.innerHTML = `
        <div class="w-6 h-6 rounded-lg bg-brand-600 text-white flex items-center justify-center shrink-0 text-[10px] font-bold">
            AI
        </div>
        <div class="bg-white p-3 rounded-2xl rounded-tl-sm border border-slate-200/80 shadow-xs flex items-center gap-2 text-slate-500">
            <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-brand-600"></i>
            <span class="text-xs">Searching tasks & reasoning...</span>
        </div>
    `;
    chatContainer.appendChild(loadingWrapper);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    refreshIcons();
    return id;
}

function removeChatLoading(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
}

function highlightTaskCard(taskId) {
    const card = document.getElementById(`task-card-${taskId}`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('ring-4', 'ring-brand-500/50', 'scale-[1.02]');
        setTimeout(() => {
            card.classList.remove('ring-4', 'ring-brand-500/50', 'scale-[1.02]');
        }, 2000);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// ==========================================
// 6. Executive Daily Briefing
// ==========================================

let cachedBriefingMarkdown = '';

async function triggerBriefingModal() {
    const modal = document.getElementById('briefingModal');
    const content = document.getElementById('briefingModalContent');
    const heroCard = document.getElementById('briefing-hero-card');
    const heroContent = document.getElementById('briefing-hero-content');

    if (modal) modal.classList.remove('hidden');

    try {
        const response = await fetch('/api/v1/ai/briefing', {
            method: 'GET',
            headers: { ...getAuthHeader() }
        });

        if (response.ok) {
            const data = await response.json();
            cachedBriefingMarkdown = data.summary;

            let html = data.summary;
            if (window.marked) {
                html = marked.parse(data.summary);
            }

            if (content) content.innerHTML = html;
            if (heroContent) heroContent.innerHTML = html;
            if (heroCard) heroCard.classList.remove('hidden');
        } else {
            if (content) content.innerHTML = '<p class="text-rose-600">Failed to generate daily briefing.</p>';
        }
    } catch (err) {
        console.error(err);
        if (content) content.innerHTML = '<p class="text-rose-600">Error generating briefing.</p>';
    }
    refreshIcons();
}

function closeBriefingModal() {
    const modal = document.getElementById('briefingModal');
    if (modal) modal.classList.add('hidden');
}

function copyBriefingContent() {
    if (!cachedBriefingMarkdown) {
        showToast('No briefing content to copy', 'warning');
        return;
    }
    navigator.clipboard.writeText(cachedBriefingMarkdown).then(() => {
        showToast('Briefing copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy to clipboard', 'error');
    });
}