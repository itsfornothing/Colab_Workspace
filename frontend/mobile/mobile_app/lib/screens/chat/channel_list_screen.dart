import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/chat_models.dart';
import 'messaging_screen.dart';
import 'dm_screen.dart';

class ChannelListScreen extends ConsumerStatefulWidget {
  const ChannelListScreen({super.key});

  @override
  ConsumerState<ChannelListScreen> createState() => _ChannelListScreenState();
}

class _ChannelListScreenState extends ConsumerState<ChannelListScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  final _api = ApiClient();

  List<ChatChannel> _myChannels = [];
  List<DmConversation> _dms = [];
  bool _loadingChannels = true;
  bool _loadingDms = true;
  String? _channelsError;
  String? _dmsError;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
    _loadChannels();
    _loadDms();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadChannels() async {
    setState(() { _loadingChannels = true; _channelsError = null; });
    try {
      final r = await _api.get(AppConstants.channelsUrl);
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((j) => ChatChannel.fromJson(j))
            .toList();
        if (mounted) setState(() {
          _myChannels = list;
          _loadingChannels = false;
        });
      } else {
        if (mounted) setState(() {
          _loadingChannels = false;
          _channelsError = 'Server error (${r.statusCode})';
        });
      }
    } catch (e) {
      if (mounted) setState(() {
        _loadingChannels = false;
        _channelsError = 'Could not connect to chat service';
      });
    }
  }

  Future<void> _loadDms() async {
    setState(() { _loadingDms = true; _dmsError = null; });
    try {
      final r = await _api.get(AppConstants.dmConversationsUrl);
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((j) => DmConversation.fromJson(j))
            .toList();
        if (mounted) setState(() {
          _dms = list;
          _loadingDms = false;
        });
      } else {
        if (mounted) setState(() {
          _loadingDms = false;
          _dmsError = 'Server error (${r.statusCode})';
        });
      }
    } catch (e) {
      if (mounted) setState(() {
        _loadingDms = false;
        _dmsError = 'Could not connect to chat service';
      });
    }
  }

  void _openNewDm() async {
    final result = await showModalBottomSheet<DmConversation>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _UserSearchSheet(),
    );
    if (result != null && mounted) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => DmScreen(conversation: result)),
      ).then((_) => _loadDms());
    }
  }

  void _openCreateChannel() async {
    final created = await showModalBottomSheet<ChatChannel>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _CreateChannelSheet(),
    );
    if (created != null && mounted) {
      setState(() => _myChannels.insert(0, created));
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => MessagingScreen(channel: created)),
      ).then((_) => _loadChannels());
    }
  }

  void _openDiscoverChannels() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _DiscoverChannelsSheet(onJoined: _loadChannels),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Messages', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: _openDiscoverChannels,
            tooltip: 'Discover channels',
          ),
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () {
              if (_tabCtrl.index == 0) {
                _openNewDm();
              } else {
                _openCreateChannel();
              }
            },
            tooltip: 'New',
          ),
        ],
        bottom: TabBar(
          controller: _tabCtrl,
          onTap: (_) => setState(() {}),
          tabs: const [
            Tab(text: 'Direct Messages'),
            Tab(text: 'Channels'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: [
          // DMs tab
          RefreshIndicator(
            onRefresh: _loadDms,
            child: _loadingDms
                ? const Center(child: CircularProgressIndicator())
                : _dmsError != null
                    ? _ErrorState(message: _dmsError!, onRetry: _loadDms)
                    : _dms.isEmpty
                        ? _EmptyState(
                            icon: Icons.chat_outlined,
                            message: 'No direct messages yet',
                            action: 'Start a conversation',
                            onAction: _openNewDm,
                          )
                        : ListView.builder(
                            itemCount: _dms.length,
                            itemBuilder: (_, i) => _DmTile(
                              dm: _dms[i],
                              onTap: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => DmScreen(conversation: _dms[i]),
                                ),
                              ).then((_) => _loadDms()),
                            ),
                          ),
          ),

          // Channels tab
          RefreshIndicator(
            onRefresh: _loadChannels,
            child: _loadingChannels
                ? const Center(child: CircularProgressIndicator())
                : _channelsError != null
                    ? _ErrorState(message: _channelsError!, onRetry: _loadChannels)
                    : _myChannels.isEmpty
                        ? _EmptyState(
                            icon: Icons.tag,
                            message: 'No channels yet',
                            action: 'Create or discover channels',
                            onAction: _openCreateChannel,
                          )
                        : ListView.builder(
                            itemCount: _myChannels.length,
                            itemBuilder: (_, i) => _ChannelTile(
                              channel: _myChannels[i],
                              onTap: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => MessagingScreen(channel: _myChannels[i]),
                                ),
                              ).then((_) => _loadChannels()),
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Tiles
// ─────────────────────────────────────────────

class _DmTile extends StatelessWidget {
  final DmConversation dm;
  final VoidCallback onTap;

  const _DmTile({required this.dm, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: CircleAvatar(
        radius: 22,
        backgroundImage: dm.otherUser.profilePicture != null
            ? NetworkImage(dm.otherUser.profilePicture!)
            : null,
        backgroundColor: AppColors.primary.withOpacity(0.15),
        child: dm.otherUser.profilePicture == null
            ? Text(dm.otherUser.initial,
                style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold))
            : null,
      ),
      title: Text(dm.otherUser.displayName,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: dm.lastMessage != null
          ? Text(dm.lastMessage!, maxLines: 1, overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall)
          : null,
      trailing: dm.lastMessageTime != null
          ? Text(_formatTime(dm.lastMessageTime!), style: theme.textTheme.bodySmall)
          : null,
      onTap: onTap,
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    if (dt.day == now.day && dt.month == now.month) {
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    }
    return '${dt.month}/${dt.day}';
  }
}

class _ChannelTile extends StatelessWidget {
  final ChatChannel channel;
  final VoidCallback onTap;

  const _ChannelTile({required this.channel, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.primary.withOpacity(0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Center(
          child: Icon(
            channel.isPrivate ? Icons.lock_outline : Icons.tag,
            color: AppColors.primary,
            size: 20,
          ),
        ),
      ),
      title: Text(channel.name, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: channel.description.isNotEmpty
          ? Text(channel.description, maxLines: 1, overflow: TextOverflow.ellipsis)
          : null,
      trailing: Text('${channel.memberCount} members',
          style: Theme.of(context).textTheme.bodySmall),
      onTap: onTap,
    );
  }
}

class _EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;
  final String action;
  final VoidCallback onAction;

  const _EmptyState({
    required this.icon,
    required this.message,
    required this.action,
    required this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 64, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Text(message, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 12),
          TextButton(onPressed: onAction, child: Text(action)),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.cloud_off, size: 64, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Text(message, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// User Search Sheet (for new DM)
// ─────────────────────────────────────────────

class _UserSearchSheet extends StatefulWidget {
  const _UserSearchSheet();

  @override
  State<_UserSearchSheet> createState() => _UserSearchSheetState();
}

class _UserSearchSheetState extends State<_UserSearchSheet> {
  final _ctrl = TextEditingController();
  final _api = ApiClient();
  List<ChatUser> _results = [];
  bool _loading = false;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _search(String q) async {
    if (q.trim().isEmpty) {
      setState(() => _results = []);
      return;
    }
    setState(() => _loading = true);
    try {
      final r = await _api.get('${AppConstants.chatUserSearchUrl}?q=${Uri.encodeComponent(q)}');
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List).map((j) => ChatUser.fromJson(j)).toList();
        setState(() => _results = list);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _startDm(ChatUser user) async {
    try {
      final r = await _api.post(AppConstants.startDmUrl, {'user_id': user.id});
      if (r.statusCode == 200 && mounted) {
        final data = jsonDecode(r.body);
        final conv = DmConversation(
          id: data['id'],
          otherUser: ChatUser.fromJson(data['other_user']),
        );
        Navigator.pop(context, conv);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (_, scrollCtrl) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            const SizedBox(height: 8),
            Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            const Text('New Message', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                controller: _ctrl,
                autofocus: true,
                onChanged: _search,
                decoration: const InputDecoration(
                  hintText: 'Search by name or username...',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.builder(
                      controller: scrollCtrl,
                      itemCount: _results.length,
                      itemBuilder: (_, i) {
                        final u = _results[i];
                        return ListTile(
                          leading: CircleAvatar(
                            backgroundImage: u.profilePicture != null
                                ? NetworkImage(u.profilePicture!)
                                : null,
                            backgroundColor: AppColors.primary.withOpacity(0.15),
                            child: u.profilePicture == null
                                ? Text(u.initial,
                                    style: const TextStyle(color: AppColors.primary))
                                : null,
                          ),
                          title: Text(u.displayName),
                          subtitle: Text('@${u.username}'),
                          onTap: () => _startDm(u),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Create Channel Sheet
// ─────────────────────────────────────────────

class _CreateChannelSheet extends StatefulWidget {
  const _CreateChannelSheet();

  @override
  State<_CreateChannelSheet> createState() => _CreateChannelSheetState();
}

class _CreateChannelSheetState extends State<_CreateChannelSheet> {
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _api = ApiClient();
  bool _isPrivate = false;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Channel name is required.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final r = await _api.post(AppConstants.channelsUrl, {
        'name': name,
        'description': _descCtrl.text.trim(),
        'is_private': _isPrivate,
      });
      if (r.statusCode == 201 && mounted) {
        final channel = ChatChannel.fromJson(jsonDecode(r.body));
        Navigator.pop(context, channel);
      } else {
        final err = jsonDecode(r.body);
        setState(() => _error = err['error'] ?? 'Failed to create channel.');
      }
    } catch (_) {
      setState(() => _error = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Create Channel',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 20),
            TextField(
              controller: _nameCtrl,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Channel name',
                prefixText: '# ',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(labelText: 'Description (optional)'),
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Private channel'),
              subtitle: const Text('Only invited members can join'),
              value: _isPrivate,
              onChanged: (v) => setState(() => _isPrivate = v),
              activeColor: AppColors.primary,
            ),
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
                    : const Text('Create Channel'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Discover Channels Sheet
// ─────────────────────────────────────────────

class _DiscoverChannelsSheet extends StatefulWidget {
  final VoidCallback onJoined;
  const _DiscoverChannelsSheet({required this.onJoined});

  @override
  State<_DiscoverChannelsSheet> createState() => _DiscoverChannelsSheetState();
}

class _DiscoverChannelsSheetState extends State<_DiscoverChannelsSheet> {
  final _ctrl = TextEditingController();
  final _api = ApiClient();
  List<ChatChannel> _channels = [];
  bool _loading = false;
  final Set<String> _joining = {};

  @override
  void initState() {
    super.initState();
    _load('');
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _load(String q) async {
    setState(() => _loading = true);
    try {
      final url = q.isEmpty
          ? AppConstants.discoverChannelsUrl
          : '${AppConstants.discoverChannelsUrl}?q=${Uri.encodeComponent(q)}';
      final r = await _api.get(url);
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List).map((j) => ChatChannel.fromJson(j)).toList();
        setState(() => _channels = list);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _join(ChatChannel channel) async {
    setState(() => _joining.add(channel.id));
    try {
      final r = await _api.post(AppConstants.joinChannelUrl(channel.id), {});
      if (r.statusCode == 200 && mounted) {
        widget.onJoined();
        _load(_ctrl.text);
      }
    } catch (_) {}
    setState(() => _joining.remove(channel.id));
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (_, scrollCtrl) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            const SizedBox(height: 8),
            Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            const Text('Discover Channels',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                controller: _ctrl,
                onChanged: (v) => _load(v),
                decoration: const InputDecoration(
                  hintText: 'Search channels...',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.builder(
                      controller: scrollCtrl,
                      itemCount: _channels.length,
                      itemBuilder: (_, i) {
                        final c = _channels[i];
                        return ListTile(
                          leading: Container(
                            width: 40, height: 40,
                            decoration: BoxDecoration(
                              color: AppColors.primary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Center(
                              child: Icon(Icons.tag, color: AppColors.primary, size: 18),
                            ),
                          ),
                          title: Text(c.name),
                          subtitle: Text('${c.memberCount} members'),
                          trailing: c.isJoined
                              ? const Chip(label: Text('Joined'))
                              : _joining.contains(c.id)
                                  ? const SizedBox(width: 20, height: 20,
                                      child: CircularProgressIndicator(strokeWidth: 2))
                                  : ElevatedButton(
                                      onPressed: () => _join(c),
                                      style: ElevatedButton.styleFrom(
                                        padding: const EdgeInsets.symmetric(horizontal: 12),
                                        minimumSize: const Size(0, 32),
                                      ),
                                      child: const Text('Join'),
                                    ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
