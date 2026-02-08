// Auto-refresh Active Tasks List
function refreshActiveTasksList() {
    const container = document.getElementById('active-task-list');
    const badge = document.getElementById('task-count-badge');
    if (!container) return;

    fetch('/api/active-tasks')
        .then(r => r.json())
        .then(data => {
            const tasks = data.tasks || [];

            // Update badge
            if (badge) {
                badge.textContent = `${data.count} TASKS`;
            }

            let html = '';
            if (tasks.length === 0) {
                html = `
                    <div style="text-align: center; color: var(--text-muted); padding: 40px;">
                        No active tasks
                    </div>
                `;
            } else {
                tasks.forEach(task => {
                    const dotClass = task.priority === 'high' ? 'status-dot-red'
                        : task.priority === 'medium' ? 'status-dot-orange'
                            : 'status-dot-green';

                    const status = task.completed ? 'Completed' : 'In Progress';

                    html += `
                        <div class="active-task-item" style="cursor: default;">
                            <div class="task-item-left" onclick="window.location.href='/todos'"
                                style="cursor: pointer; flex: 1;">
                                <div class="task-status-dot ${dotClass}"></div>
                                <div class="task-item-content">
                                    <h4>${task.title}</h4>
                                    <p>${status} • Priority ${task.priority.toUpperCase()}</p>
                                </div>
                            </div>
                            <form action="/todos/${task.id}/toggle" method="POST" style="margin: 0;">
                                <input type="hidden" name="next" value="/dashboard">
                                <button type="submit" class="task-complete-btn" title="Complete Task"
                                    style="background: none; border: none; color: var(--text-muted); cursor: pointer; transition: 0.2s;">
                                    <i class="fa-regular fa-circle-check" style="font-size: 1.2rem;"></i>
                                </button>
                            </form>
                        </div>
                    `;
                });
            }

            // Simple check to avoid unnecessary reflow
            const newClean = html.replace(/\s/g, '');
            const oldClean = container.innerHTML.replace(/\s/g, '');

            if (newClean !== oldClean) {
                container.innerHTML = html;
            }
        })
        .catch(e => console.error("Failed to refresh active tasks", e));
}

// Make it globally accessible
window.refreshActiveTasksList = refreshActiveTasksList;
