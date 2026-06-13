import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:student_snapshot/config/app_config.dart';
import 'package:student_snapshot/features/snapshot/presentation/camera_screen.dart';

class TenantInfo {
  final String tenantId;
  final String name;
  final String slug;
  const TenantInfo({required this.tenantId, required this.name, required this.slug});

  factory TenantInfo.fromJson(Map<String, dynamic> json) => TenantInfo(
        tenantId: json['tenant_id'] as String,
        name: json['name'] as String,
        slug: json['slug'] as String,
      );
}

class AccessScreen extends StatefulWidget {
  const AccessScreen({super.key});

  @override
  State<AccessScreen> createState() => _AccessScreenState();
}

class _AccessScreenState extends State<AccessScreen> {
  final _storage = const FlutterSecureStorage();
  final _studentController = TextEditingController();
  final _searchController = TextEditingController();

  List<TenantInfo> _allTenants = [];
  List<TenantInfo> _filteredTenants = [];
  TenantInfo? _selectedTenant;
  bool _loadingTenants = true;
  bool _proceeding = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
    _searchController.addListener(_filterTenants);
  }

  Future<void> _loadData() async {
    // Restore saved student name
    final studentName = await _storage.read(key: 'student_name');
    if (studentName != null) _studentController.text = studentName;

    // Restore saved tenant
    final savedTenantId = await _storage.read(key: 'tenant_id');

    // Fetch tenants from API
    try {
      final response = await http
          .get(Uri.parse('${AppConfig.apiBaseUrl}/mobile/tenants'))
          .timeout(const Duration(seconds: 15));
      if (response.statusCode == 200) {
        final list = jsonDecode(utf8.decode(response.bodyBytes)) as List;
        final tenants = list
            .map((e) => TenantInfo.fromJson(e as Map<String, dynamic>))
            .toList();
        setState(() {
          _allTenants = tenants;
          _filteredTenants = tenants;
          _loadingTenants = false;
          if (savedTenantId != null) {
            _selectedTenant = tenants.firstWhere(
              (t) => t.tenantId == savedTenantId,
              orElse: () => tenants.isNotEmpty ? tenants.first : TenantInfo(tenantId: '', name: '', slug: ''),
            );
            if (_selectedTenant!.tenantId.isEmpty) _selectedTenant = null;
          }
        });
      } else {
        setState(() {
          _error = 'فشل تحميل قائمة المعلمين (${response.statusCode})';
          _loadingTenants = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'تعذر الاتصال بالخادم. تحقق من الإنترنت.';
        _loadingTenants = false;
      });
    }
  }

  void _filterTenants() {
    final query = _searchController.text.trim().toLowerCase();
    setState(() {
      _filteredTenants = query.isEmpty
          ? _allTenants
          : _allTenants
              .where((t) =>
                  t.name.toLowerCase().contains(query) ||
                  t.slug.toLowerCase().contains(query))
              .toList();
    });
  }

  Future<void> _proceed() async {
    if (_selectedTenant == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('يرجى اختيار المعلم أولاً')),
      );
      return;
    }
    setState(() => _proceeding = true);
    await _storage.write(key: 'tenant_id', value: _selectedTenant!.tenantId);
    await _storage.write(key: 'student_name', value: _studentController.text.trim());
    if (!mounted) return;
    setState(() => _proceeding = false);
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => CameraScreen(
          tenantId: _selectedTenant!.tenantId,
          studentId: _studentController.text.trim(),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _studentController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              const Text(
                'نقلة',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text(
                'مساعدك التعليمي الذكي',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, color: Colors.grey),
              ),
              const SizedBox(height: 32),

              // Student name
              TextFormField(
                controller: _studentController,
                decoration: const InputDecoration(
                  labelText: 'اسمك (اختياري)',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 20),

              // Tenant selection
              const Text(
                'اختر معلمك',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                textDirection: TextDirection.rtl,
              ),
              const SizedBox(height: 8),

              if (_loadingTenants)
                const Center(child: CircularProgressIndicator())
              else if (_error != null)
                Column(
                  children: [
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                    TextButton(
                      onPressed: () {
                        setState(() { _loadingTenants = true; _error = null; });
                        _loadData();
                      },
                      child: const Text('إعادة المحاولة'),
                    ),
                  ],
                )
              else ...[
                // Search box
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'ابحث عن معلمك...',
                    prefixIcon: const Icon(Icons.search),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 10,
                    ),
                  ),
                ),
                const SizedBox(height: 8),

                // Tenants list
                Expanded(
                  child: _filteredTenants.isEmpty
                      ? const Center(child: Text('لا يوجد معلمون مطابقون'))
                      : ListView.builder(
                          itemCount: _filteredTenants.length,
                          itemBuilder: (context, i) {
                            final tenant = _filteredTenants[i];
                            final isSelected =
                                _selectedTenant?.tenantId == tenant.tenantId;
                            return Card(
                              margin: const EdgeInsets.only(bottom: 6),
                              color: isSelected
                                  ? Colors.blue.shade50
                                  : null,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                                side: BorderSide(
                                  color: isSelected
                                      ? Colors.blue
                                      : Colors.grey.shade200,
                                  width: isSelected ? 2 : 1,
                                ),
                              ),
                              child: ListTile(
                                title: Text(
                                  tenant.name,
                                  textDirection: TextDirection.rtl,
                                  style: TextStyle(
                                    fontWeight: isSelected
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                                  ),
                                ),
                                trailing: isSelected
                                    ? const Icon(Icons.check_circle,
                                        color: Colors.blue)
                                    : null,
                                onTap: () =>
                                    setState(() => _selectedTenant = tenant),
                              ),
                            );
                          },
                        ),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _proceeding ? null : _proceed,
                  child: _proceeding
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('ابدأ'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
