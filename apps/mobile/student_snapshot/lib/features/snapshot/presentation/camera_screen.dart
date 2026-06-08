import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:student_snapshot/features/snapshot/domain/snapshot_provider.dart';
import 'package:student_snapshot/features/snapshot/presentation/confirm_image_screen.dart';

class CameraScreen extends StatefulWidget {
  final String tenantId;
  final String studentId;

  const CameraScreen({
    super.key,
    required this.tenantId,
    required this.studentId,
  });

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  final _picker = ImagePicker();
  bool _picking = false;

  Future<void> _capture(ImageSource source) async {
    if (_picking) return;
    setState(() => _picking = true);

    try {
      final picked = await _picker.pickImage(
        source: source,
        imageQuality: 90,
        maxWidth: 2048,
      );
      if (picked == null) {
        setState(() => _picking = false);
        return;
      }

      final cropped = await ImageCropper().cropImage(
        sourcePath: picked.path,
        uiSettings: [
          AndroidUiSettings(
            toolbarTitle: 'اقتصاص الصورة',
            lockAspectRatio: false,
          ),
        ],
      );

      if (!mounted) return;
      final file = File(cropped?.path ?? picked.path);
      context.read<SnapshotProvider>().setSelectedImage(file);

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ConfirmImageScreen(
            tenantId: widget.tenantId,
            studentId: widget.studentId,
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('التقاط سؤال')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.camera_alt, size: 80, color: Colors.blue),
            const SizedBox(height: 24),
            const Text(
              'التقط صورة لسؤال أو صفحة من الكتاب',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18),
            ),
            const SizedBox(height: 40),
            FilledButton.icon(
              onPressed: _picking ? null : () => _capture(ImageSource.camera),
              icon: const Icon(Icons.camera_alt),
              label: const Text('فتح الكاميرا'),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _picking ? null : () => _capture(ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: const Text('اختيار من المعرض'),
            ),
            if (_picking)
              const Padding(
                padding: EdgeInsets.only(top: 24),
                child: Center(child: CircularProgressIndicator()),
              ),
          ],
        ),
      ),
    );
  }
}
