import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:student_snapshot/features/snapshot/domain/snapshot_provider.dart';
import 'package:student_snapshot/features/snapshot/presentation/result_screen.dart';

class ConfirmImageScreen extends StatelessWidget {
  final String tenantId;
  final String studentId;

  const ConfirmImageScreen({
    super.key,
    required this.tenantId,
    required this.studentId,
  });

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SnapshotProvider>();
    final image = provider.selectedImage;

    if (image == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => Navigator.pop(context));
      return const SizedBox.shrink();
    }

    return Scaffold(
      appBar: AppBar(title: const Text('تأكيد الصورة')),
      body: Column(
        children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(image, fit: BoxFit.contain),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.refresh),
                    label: const Text('إعادة التقاط'),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: provider.state == SnapshotState.loading
                        ? null
                        : () async {
                            await provider.submitSnapshot(
                              tenantId: tenantId,
                              studentId: studentId.isEmpty ? null : studentId,
                            );
                            if (!context.mounted) return;
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => const ResultScreen(),
                              ),
                            );
                          },
                    icon: provider.state == SnapshotState.loading
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.search),
                    label: const Text('ابحث عن الإجابة'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
