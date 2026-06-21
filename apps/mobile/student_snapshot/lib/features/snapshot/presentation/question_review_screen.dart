import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:student_snapshot/features/snapshot/domain/snapshot_provider.dart';
import 'package:student_snapshot/features/snapshot/presentation/result_screen.dart';

class QuestionReviewScreen extends StatefulWidget {
  const QuestionReviewScreen({super.key});

  @override
  State<QuestionReviewScreen> createState() => _QuestionReviewScreenState();
}

class _QuestionReviewScreenState extends State<QuestionReviewScreen> {
  @override
  void initState() {
    super.initState();
    // Select all questions by default on first entry
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SnapshotProvider>().initQuestionSelection();
    });
  }

  void _showEditDialog(BuildContext context, String questionId, String currentText) {
    final controller = TextEditingController(text: currentText);
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('تعديل السؤال', textDirection: TextDirection.rtl),
        content: TextField(
          controller: controller,
          textDirection: TextDirection.rtl,
          maxLines: 4,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'نص السؤال...',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () {
              // Note: editing question text is display-only — answers already generated
              // Future enhancement: re-submit edited question to backend
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('تعديل النص لا يعيد توليد الإجابة في هذا الإصدار.'),
                  duration: Duration(seconds: 3),
                ),
              );
            },
            child: const Text('حفظ'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SnapshotProvider>();
    final result = provider.result;

    if (result == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => Navigator.pop(context));
      return const SizedBox.shrink();
    }

    final questions = result.detectedQuestions;
    final selectedIds = provider.selectedQuestionIds;
    final hasSelection = selectedIds.isNotEmpty;

    return Scaffold(
      appBar: AppBar(
        title: const Text('مراجعة الأسئلة'),
        actions: [
          TextButton(
            onPressed: provider.selectAllQuestions,
            child: const Text('تحديد الكل'),
          ),
        ],
      ),
      body: Column(
        children: [
          // Header info
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: Colors.blue.shade50,
            child: Text(
              'تم اكتشاف ${questions.length} سؤال. اختر الأسئلة التي تريد إجابتها.',
              textDirection: TextDirection.rtl,
              style: const TextStyle(fontSize: 14, color: Colors.black87),
            ),
          ),
          // Question list
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: questions.length,
              itemBuilder: (context, i) {
                final q = questions[i];
                final isSelected = selectedIds.contains(q.questionId);
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                    side: BorderSide(
                      color: isSelected ? Colors.blue : Colors.grey.shade300,
                      width: isSelected ? 1.5 : 1,
                    ),
                  ),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => provider.toggleQuestion(q.questionId),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Edit button
                          IconButton(
                            icon: const Icon(Icons.edit_outlined, size: 20),
                            tooltip: 'تعديل السؤال',
                            onPressed: () =>
                                _showEditDialog(context, q.questionId, q.questionText),
                            padding: EdgeInsets.zero,
                            constraints: const BoxConstraints(),
                          ),
                          const SizedBox(width: 8),
                          // Question text
                          Expanded(
                            child: Text(
                              q.questionText,
                              textDirection: TextDirection.rtl,
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight:
                                    isSelected ? FontWeight.w600 : FontWeight.normal,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          // Checkbox
                          Checkbox(
                            value: isSelected,
                            onChanged: (_) => provider.toggleQuestion(q.questionId),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          // Bottom action
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            child: FilledButton.icon(
              onPressed: hasSelection
                  ? () {
                      Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const ResultScreen()),
                      );
                    }
                  : null,
              icon: const Icon(Icons.check_circle_outline),
              label: Text(
                hasSelection
                    ? 'عرض إجابة ${selectedIds.length} سؤال'
                    : 'اختر سؤالاً على الأقل',
              ),
              style: FilledButton.styleFrom(
                minimumSize: const Size(double.infinity, 52),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
