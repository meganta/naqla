import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:student_snapshot/features/snapshot/presentation/camera_screen.dart';

class AccessScreen extends StatefulWidget {
  const AccessScreen({super.key});

  @override
  State<AccessScreen> createState() => _AccessScreenState();
}

class _AccessScreenState extends State<AccessScreen> {
  final _formKey = GlobalKey<FormState>();
  final _tenantController = TextEditingController();
  final _studentController = TextEditingController();
  final _storage = const FlutterSecureStorage();
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadSaved();
  }

  Future<void> _loadSaved() async {
    final tenant = await _storage.read(key: 'tenant_id');
    final student = await _storage.read(key: 'student_id');
    if (tenant != null) _tenantController.text = tenant;
    if (student != null) _studentController.text = student;
  }

  Future<void> _proceed() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    await _storage.write(key: 'tenant_id', value: _tenantController.text.trim());
    await _storage.write(key: 'student_id', value: _studentController.text.trim());
    if (!mounted) return;
    setState(() => _loading = false);
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => CameraScreen(
          tenantId: _tenantController.text.trim(),
          studentId: _studentController.text.trim(),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _tenantController.dispose();
    _studentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 32),
                const Text(
                  'نقلة',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                const Text(
                  'مساعدك التعليمي الذكي',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16, color: Colors.grey),
                ),
                const SizedBox(height: 48),
                TextFormField(
                  controller: _tenantController,
                  textDirection: TextDirection.ltr,
                  decoration: const InputDecoration(
                    labelText: 'معرّف المعلم (Tenant ID)',
                    border: OutlineInputBorder(),
                  ),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'يرجى إدخال معرّف المعلم' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _studentController,
                  decoration: const InputDecoration(
                    labelText: 'اسم الطالب (اختياري)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 32),
                FilledButton(
                  onPressed: _loading ? null : _proceed,
                  child: _loading
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
            ),
          ),
        ),
      ),
    );
  }
}
