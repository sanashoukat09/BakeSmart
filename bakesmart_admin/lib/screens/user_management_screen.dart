import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../services/admin_service.dart';
import '../models/user_model.dart';

final userFilterProvider = StateProvider<String>((ref) => 'All');
final userSearchProvider = StateProvider<String>((ref) => '');

class UserManagementScreen extends ConsumerWidget {
  const UserManagementScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersAsync = ref.watch(allUsersProvider);
    final currentFilter = ref.watch(userFilterProvider);
    final search = ref.watch(userSearchProvider);

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 24),
          color: Colors.white,
          child: Row(
            children: [
              _buildFilterTab(ref, 'All', currentFilter),
              _buildFilterTab(ref, 'Bakers', currentFilter),
              _buildFilterTab(ref, 'Customers', currentFilter),
              _buildFilterTab(ref, 'Suspended', currentFilter),
              const Spacer(),
              SizedBox(
                width: 300,
                child: TextField(
                  onChanged: (val) => ref.read(userSearchProvider.notifier).state = val,
                  decoration: InputDecoration(
                    hintText: 'Search by name or email...',
                    prefixIcon: const Icon(Icons.search),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: usersAsync.when(
            data: (users) {
              final filtered = users.where((u) {
                final matchesSearch = u.name.toLowerCase().contains(search.toLowerCase()) || 
                                     u.email.toLowerCase().contains(search.toLowerCase());
                
                bool matchesTab = true;
                if (currentFilter == 'Bakers') matchesTab = u.role == 'baker';
                if (currentFilter == 'Customers') matchesTab = u.role == 'customer';
                if (currentFilter == 'Suspended') matchesTab = u.isSuspended;
                
                return matchesSearch && matchesTab;
              }).toList();

              return SingleChildScrollView(
                padding: const EdgeInsets.all(40),
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFEEEEEE)),
                  ),
                  child: Theme(
                    data: Theme.of(context).copyWith(dividerColor: const Color(0xFFEEEEEE)),
                    child: PaginatedDataTable(
                      header: Text('User Records (${filtered.length})', style: const TextStyle(fontWeight: FontWeight.bold)),
                      columns: const [
                        DataColumn(label: Text('Name', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Email', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Role', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Verification', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Joined Date', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Status', style: TextStyle(fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Actions', style: TextStyle(fontWeight: FontWeight.bold))),
                      ],
                      source: _UserDataSource(filtered, ref),
                      rowsPerPage: 10,
                      showCheckboxColumn: false,
                    ),
                  ),
                ),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
          ),
        ),
      ],
    );
  }

  Widget _buildFilterTab(WidgetRef ref, String label, String current) {
    final isSelected = current == label;
    return Padding(
      padding: const EdgeInsets.only(right: 16),
      child: ChoiceChip(
        label: Text(label),
        selected: isSelected,
        onSelected: (val) => ref.read(userFilterProvider.notifier).state = label,
        selectedColor: Colors.brown[100],
        labelStyle: TextStyle(color: isSelected ? Colors.brown[900] : Colors.grey[600]),
      ),
    );
  }
}

class _UserDataSource extends DataTableSource {
  final List<UserModel> users;
  final WidgetRef ref;

  _UserDataSource(this.users, this.ref);

  @override
  DataRow? getRow(int index) {
    if (index >= users.length) return null;
    final user = users[index];

    return DataRow(cells: [
      DataCell(Text(user.name)),
      DataCell(Text(user.email)),
      DataCell(Text(user.role.toUpperCase())),
      DataCell(Text(user.role == 'baker' ? (user.verificationStatus?.toUpperCase() ?? 'UNVERIFIED') : 'N/A')),
      DataCell(Text(DateFormat('MMM dd, yyyy').format(user.createdAt))),
      DataCell(_buildStatusChip(user.isSuspended)),
      DataCell(Row(
        children: [
          IconButton(
            onPressed: () => ref.read(adminServiceProvider).toggleUserSuspension(user.uid, !user.isSuspended),
            icon: Icon(user.isSuspended ? Icons.play_arrow : Icons.block, color: user.isSuspended ? Colors.green : Colors.orange),
            tooltip: user.isSuspended ? 'Unsuspend' : 'Suspend',
          ),
          IconButton(
            onPressed: () => _confirmDelete(user.uid),
            icon: const Icon(Icons.delete_outline, color: Colors.red),
            tooltip: 'Delete User',
          ),
        ],
      )),
    ]);
  }

  void _confirmDelete(String uid) {
    // Note: In real app, show a confirmation dialog here.
    // For now we'll call the service directly or assume dev usage.
    ref.read(adminServiceProvider).deleteUser(uid);
  }

  Widget _buildStatusChip(bool isSuspended) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: (isSuspended ? Colors.red : Colors.green).withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        isSuspended ? 'Suspended' : 'Active',
        style: TextStyle(color: isSuspended ? Colors.red : Colors.green, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }

  @override
  bool get isRowCountApproximate => false;
  @override
  int get rowCount => users.length;
  @override
  int get selectedRowCount => 0;
}
