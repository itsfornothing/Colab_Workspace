import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../providers/workspace_provider.dart';
import '../../services/notification_service.dart';

class Task {
  final String id;
  final String workspaceId;
  final String title;
  final String description;
  final String status;
  final String priority;
  final String? assigneeId;
  final String? dueDate;
  final DateTime createdAt;

  const Task({
    required this.id,
    required this.workspaceId,
    required this.title,
    this.description = '',
    required this.status,
    required this.priority,
    this.assigneeId,
    this.dueDate,
    required this.createdAt,
  });

  factory Task.fromJson(Map<String, dynamic> j) => Task(
        id: j['id']?.toString() ?? '',
        workspaceId: j['workspace_id']?.toString() ?? '',
        title: j['title'] ?? '',
        description: j['description'] ?? '',
        status: j['status'] ?? 'todo',
        priority: j['priority'] ?? 'medium',
        assigneeId: j['assignee_id']?.toString(),
        dueDate: j['due_date'],
        createdAt: DateTime.tryParse(j['created_at'] ?? '') ?? DateTime.now(),
      );
}

class TasksScreen extends ConsumerStatefulWidget {
  const TasksScreen({super.key});

  @override
  ConsumerState<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends ConsumerState<TasksScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  final _api = ApiClient();
  List<Task> _tasks = [];
  bool _loading = true;
  String _filterStatus = 'all';
  String? _lastLoadedWorkspaceId;
  bool _wasVisible = true;

  static const _statuses = ['all', 'todo', 'in_progress', 'review', 'done'];

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: _statuses.length, vsync: this);
    _tabCtrl.addListener(() {
      setState(() => _filterStatus = _statuses[_tabCtrl.index]);
    });
    // Listen for workspace ID changes to handle both the race condition
    // (workspace resolves after mount) and stale list (workspace changes
    // on tab re-focus). listenManual is safe to call in initState.
    ref.listenManual<WorkspaceState>(
      workspaceProvider,
      (previous, next) {
        final wsId = next.currentWorkspaceId;
        if (wsId != null && wsId != _lastLoadedWorkspaceId) {
          _lastLoadedWorkspaceId = wsId;
          _load();
        }
      },
      fireImmediately: true,
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Register as a dependent on Visibility (used by IndexedStack) so that
    // didChangeDependencies is called when the tab becomes visible again.
    final isVisible = Visibility.of(context);
    final wsId = ref.read(workspaceProvider).currentWorkspaceId;
    if (wsId != null && wsId != _lastLoadedWorkspaceId) {
      _lastLoadedWorkspaceId = wsId;
      _load();
    } else if (wsId != null && isVisible && !_wasVisible) {
      // Tab became visible again — re-fetch to avoid stale list.
      _load();
    }
    _wasVisible = isVisible;
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final wsId = ref.read(workspaceProvider).currentWorkspaceId;
    if (wsId == null) {
      // Keep _loading = true; didChangeDependencies will re-trigger when wsId arrives
      return;
    }
    setState(() => _loading = true);
    try {
      final r = await _api.get('${AppConstants.tasksUrl}?workspace_id=$wsId');
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List).map((j) => Task.fromJson(j)).toList();
        setState(() => _tasks = list);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  List<Task> get _filtered {
    if (_filterStatus == 'all') return _tasks;
    return _tasks.where((t) => t.status == _filterStatus).toList();
  }

  Future<void> _updateStatus(Task task, String newStatus) async {
    try {
      final r = await _api.patch(AppConstants.taskUrl(task.id), {'status': newStatus});
      if (r.statusCode == 200) {
        setState(() {
          final idx = _tasks.indexWhere((t) => t.id == task.id);
          if (idx != -1) {
            _tasks[idx] = Task(
              id: task.id,
              workspaceId: task.workspaceId,
              title: task.title,
              description: task.description,
              status: newStatus,
              priority: task.priority,
              assigneeId: task.assigneeId,
              dueDate: task.dueDate,
              createdAt: task.createdAt,
            );
          }
        });
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Tasks', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showCreateTask(context),
          ),
        ],
        bottom: TabBar(
          controller: _tabCtrl,
          isScrollable: true,
          tabs: _statuses.map((s) => Tab(text: _statusLabel(s))).toList(),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _filtered.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.task_outlined,
                            size: 64, color: Colors.grey.shade400),
                        const SizedBox(height: 12),
                        Text('No tasks', style: theme.textTheme.bodyLarge),
                        const SizedBox(height: 12),
                        ElevatedButton.icon(
                          onPressed: () => _showCreateTask(context),
                          icon: const Icon(Icons.add),
                          label: const Text('Create Task'),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _filtered.length,
                    itemBuilder: (_, i) => _TaskCard(
                      task: _filtered[i],
                      onStatusChange: _updateStatus,
                      onTap: () => _showTaskDetail(context, _filtered[i]),
                    ),
                  ),
      ),
    );
  }

  String _statusLabel(String s) {
    switch (s) {
      case 'all': return 'All';
      case 'todo': return 'To Do';
      case 'in_progress': return 'In Progress';
      case 'review': return 'Review';
      case 'done': return 'Done';
      default: return s;
    }
  }

  void _showCreateTask(BuildContext context) async {
    final wsId = ref.read(workspaceProvider).currentWorkspaceId;
    if (wsId == null) return;
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _CreateTaskSheet(workspaceId: wsId),
    );
    if (created == true) _load();
  }

  void _showTaskDetail(BuildContext context, Task task) async {
    final updated = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _TaskDetailSheet(task: task),
    );
    if (updated == true) _load();
  }
}

// ─────────────────────────────────────────────
// Task Card
// ─────────────────────────────────────────────

class _TaskCard extends StatelessWidget {
  final Task task;
  final Function(Task, String) onStatusChange;
  final VoidCallback onTap;

  const _TaskCard({
    required this.task,
    required this.onStatusChange,
    required this.onTap,
  });

  Color _priorityColor() {
    switch (task.priority) {
      case 'urgent': return Colors.red;
      case 'high': return Colors.orange;
      case 'medium': return Colors.blue;
      default: return Colors.grey;
    }
  }

  Color _statusColor() {
    switch (task.status) {
      case 'done': return AppColors.success;
      case 'in_progress': return Colors.blue;
      case 'review': return Colors.orange;
      default: return Colors.grey;
    }
  }

  bool _isOverdue() {
    if (task.dueDate == null || task.status == 'done') return false;
    final due = DateTime.tryParse(task.dueDate!);
    return due != null && due.isBefore(DateTime.now());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: _priorityColor(),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      task.title,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        decoration: task.status == 'done'
                            ? TextDecoration.lineThrough
                            : null,
                      ),
                    ),
                  ),
                  _StatusDropdown(
                    status: task.status,
                    onChanged: (s) => onStatusChange(task, s),
                  ),
                ],
              ),
              if (task.description.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  task.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall,
                ),
              ],
              if (task.dueDate != null) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Icon(Icons.calendar_today_outlined,
                        size: 12,
                        color: _isOverdue()
                            ? AppColors.danger
                            : theme.colorScheme.onSurface.withOpacity(0.5)),
                    const SizedBox(width: 4),
                    Text(
                      task.dueDate!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontSize: 11,
                        color: _isOverdue() ? AppColors.danger : null,
                        fontWeight: _isOverdue() ? FontWeight.w600 : null,
                      ),
                    ),
                    if (_isOverdue()) ...[
                      const SizedBox(width: 4),
                      Text(
                        'Overdue',
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontSize: 10,
                          color: AppColors.danger,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusDropdown extends StatelessWidget {
  final String status;
  final Function(String) onChanged;

  const _StatusDropdown({required this.status, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return DropdownButton<String>(
      value: status,
      underline: const SizedBox(),
      isDense: true,
      style: const TextStyle(fontSize: 12),
      items: const [
        DropdownMenuItem(value: 'todo', child: Text('To Do')),
        DropdownMenuItem(value: 'in_progress', child: Text('In Progress')),
        DropdownMenuItem(value: 'review', child: Text('Review')),
        DropdownMenuItem(value: 'done', child: Text('Done')),
      ],
      onChanged: (v) { if (v != null) onChanged(v); },
    );
  }
}

// ─────────────────────────────────────────────
// Create Task Sheet
// ─────────────────────────────────────────────

class _CreateTaskSheet extends ConsumerStatefulWidget {
  final String workspaceId;
  const _CreateTaskSheet({required this.workspaceId});

  @override
  ConsumerState<_CreateTaskSheet> createState() => _CreateTaskSheetState();
}

class _CreateTaskSheetState extends ConsumerState<_CreateTaskSheet> {
  final _titleCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _api = ApiClient();
  String _priority = 'medium';
  DateTime? _dueDate;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDueDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now().add(const Duration(days: 1)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
    );
    if (picked != null) setState(() => _dueDate = picked);
  }

  Future<void> _create() async {
    final title = _titleCtrl.text.trim();
    if (title.isEmpty) {
      setState(() => _error = 'Title is required.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final body = {
        'workspace_id': widget.workspaceId,
        'title': title,
        'description': _descCtrl.text.trim(),
        'priority': _priority,
        if (_dueDate != null)
          'due_date': _dueDate!.toIso8601String().split('T').first, // YYYY-MM-DD
      };
      final r = await _api.post(AppConstants.tasksUrl, body);
      if (r.statusCode == 201 && mounted) {
        ref.read(notiServiceProvider).showNotification(
          title: 'Task Created',
          body: title,
        );
        Navigator.pop(context, true);
      } else {
        setState(() => _error = 'Failed to create task.');
      }
    } catch (_) {
      setState(() => _error = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: theme.scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('New Task',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            TextField(
              controller: _titleCtrl,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Task title'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descCtrl,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Description (optional)'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _priority,
              decoration: const InputDecoration(labelText: 'Priority'),
              items: const [
                DropdownMenuItem(value: 'low', child: Text('Low')),
                DropdownMenuItem(value: 'medium', child: Text('Medium')),
                DropdownMenuItem(value: 'high', child: Text('High')),
                DropdownMenuItem(value: 'urgent', child: Text('Urgent')),
              ],
              onChanged: (v) => setState(() => _priority = v ?? 'medium'),
            ),
            const SizedBox(height: 12),
            // Due date picker
            InkWell(
              onTap: _pickDueDate,
              borderRadius: BorderRadius.circular(8),
              child: InputDecorator(
                decoration: const InputDecoration(
                  labelText: 'Due date (optional)',
                  suffixIcon: Icon(Icons.calendar_today_outlined, size: 18),
                ),
                child: Text(
                  _dueDate == null
                      ? 'No due date'
                      : '${_dueDate!.year}-${_dueDate!.month.toString().padLeft(2, '0')}-${_dueDate!.day.toString().padLeft(2, '0')}',
                  style: TextStyle(
                    color: _dueDate == null
                        ? theme.colorScheme.onSurface.withOpacity(0.5)
                        : theme.colorScheme.onSurface,
                  ),
                ),
              ),
            ),
            if (_dueDate != null) ...[
              const SizedBox(height: 4),
              GestureDetector(
                onTap: () => setState(() => _dueDate = null),
                child: Text(
                  'Clear due date',
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.primary,
                  ),
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loading ? null : _create,
                child: _loading
                    ? const SizedBox(width: 20, height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('Create Task'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Task Detail Sheet
// ─────────────────────────────────────────────

class _TaskDetailSheet extends StatefulWidget {
  final Task task;
  const _TaskDetailSheet({required this.task});

  @override
  State<_TaskDetailSheet> createState() => _TaskDetailSheetState();
}

class _TaskDetailSheetState extends State<_TaskDetailSheet> {
  final _api = ApiClient();
  late String _status;
  late String _priority;
  DateTime? _dueDate;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _status = widget.task.status;
    _priority = widget.task.priority;
    if (widget.task.dueDate != null) {
      _dueDate = DateTime.tryParse(widget.task.dueDate!);
    }
  }

  Future<void> _pickDueDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now().add(const Duration(days: 1)),
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
    );
    if (picked != null) setState(() => _dueDate = picked);
  }

  Future<void> _save() async {
    setState(() => _loading = true);
    try {
      final body = {
        'status': _status,
        'priority': _priority,
        'due_date': _dueDate != null
            ? '${_dueDate!.year}-${_dueDate!.month.toString().padLeft(2, '0')}-${_dueDate!.day.toString().padLeft(2, '0')}'
            : null,
      };
      final r = await _api.patch(AppConstants.taskUrl(widget.task.id), body);
      if (r.statusCode == 200 && mounted) {
        Navigator.pop(context, true);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _delete() async {
    try {
      await _api.delete(AppConstants.taskUrl(widget.task.id));
      if (mounted) Navigator.pop(context, true);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.4,
      maxChildSize: 0.9,
      builder: (_, scrollCtrl) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(24),
        child: ListView(
          controller: scrollCtrl,
          children: [
            Text(widget.task.title,
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            if (widget.task.description.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(widget.task.description),
            ],
            const SizedBox(height: 20),
            DropdownButtonFormField<String>(
              value: _status,
              decoration: const InputDecoration(labelText: 'Status'),
              items: const [
                DropdownMenuItem(value: 'todo', child: Text('To Do')),
                DropdownMenuItem(value: 'in_progress', child: Text('In Progress')),
                DropdownMenuItem(value: 'review', child: Text('Review')),
                DropdownMenuItem(value: 'done', child: Text('Done')),
              ],
              onChanged: (v) => setState(() => _status = v ?? _status),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _priority,
              decoration: const InputDecoration(labelText: 'Priority'),
              items: const [
                DropdownMenuItem(value: 'low', child: Text('Low')),
                DropdownMenuItem(value: 'medium', child: Text('Medium')),
                DropdownMenuItem(value: 'high', child: Text('High')),
                DropdownMenuItem(value: 'urgent', child: Text('Urgent')),
              ],
              onChanged: (v) => setState(() => _priority = v ?? _priority),
            ),
            const SizedBox(height: 12),
            // Due date picker
            InkWell(
              onTap: _pickDueDate,
              borderRadius: BorderRadius.circular(8),
              child: InputDecorator(
                decoration: const InputDecoration(
                  labelText: 'Due date',
                  suffixIcon: Icon(Icons.calendar_today_outlined, size: 18),
                ),
                child: Text(
                  _dueDate == null
                      ? 'No due date'
                      : '${_dueDate!.year}-${_dueDate!.month.toString().padLeft(2, '0')}-${_dueDate!.day.toString().padLeft(2, '0')}',
                  style: TextStyle(
                    color: _dueDate == null
                        ? Theme.of(context).colorScheme.onSurface.withOpacity(0.5)
                        : (_dueDate!.isBefore(DateTime.now()) && _status != 'done'
                            ? AppColors.danger
                            : Theme.of(context).colorScheme.onSurface),
                  ),
                ),
              ),
            ),
            if (_dueDate != null) ...[
              const SizedBox(height: 4),
              GestureDetector(
                onTap: () => setState(() => _dueDate = null),
                child: Text(
                  'Clear due date',
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _loading ? null : _save,
                    child: const Text('Save'),
                  ),
                ),
                const SizedBox(width: 12),
                OutlinedButton(
                  onPressed: _delete,
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppColors.danger),
                  ),
                  child: const Text('Delete',
                      style: TextStyle(color: AppColors.danger)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
