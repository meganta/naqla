import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:student_snapshot/features/snapshot/data/snapshot_models.dart';
import 'package:student_snapshot/features/snapshot/domain/snapshot_provider.dart';
import 'package:student_snapshot/features/evidence/presentation/evidence_card.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SnapshotProvider>();

    if (provider.state == SnapshotState.loading) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('جارٍ البحث في قاعدة المعرفة...'),
            ],
          ),
        ),
      );
    }

    if (provider.state == SnapshotState.error) {
      return Scaffold(
        appBar: AppBar(title: const Text('حدث خطأ')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 64, color: Colors.red),
                const SizedBox(height: 16),
                Text(
                  provider.errorMessage ?? 'حدث خطأ غير متوقع',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('حاول مجدداً'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final result = provider.result;
    if (result == null) return const SizedBox.shrink();

    return Scaffold(
      appBar: AppBar(
        title: const Text('النتائج'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'سؤال جديد',
            onPressed: () {
              provider.reset();
              Navigator.of(context).popUntil((r) => r.isFirst);
            },
          ),
        ],
      ),
      body: Builder(builder: (context) {
        if (result.warnings.isNotEmpty && result.detectedQuestions.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.warning_amber_rounded, size: 64, color: Colors.orange),
                  const SizedBox(height: 16),
                  ...result.warnings.map(
                    (w) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(w, textAlign: TextAlign.center),
                    ),
                  ),
                  const SizedBox(height: 24),
                  OutlinedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('إعادة التقاط'),
                  ),
                ],
              ),
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: result.detectedQuestions.length,
          itemBuilder: (context, i) {
            final q = result.detectedQuestions[i];
            return _QuestionAnswerCard(question: q);
          },
        );
      }),
    );
  }
}

class _QuestionAnswerCard extends StatelessWidget {
  final DetectedQuestion question;

  const _QuestionAnswerCard({required this.question});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Question
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                question.questionText,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                textDirection: TextDirection.rtl,
              ),
            ),
            const SizedBox(height: 12),
            // Answer
            if (question.hasAnswer) ...[
              Text(
                question.answer,
                style: const TextStyle(fontSize: 15),
                textDirection: TextDirection.rtl,
              ),
            ] else ...[
              Row(
                children: [
                  const Icon(Icons.warning_amber, color: Colors.orange, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      question.answer,
                      style: const TextStyle(color: Colors.orange),
                      textDirection: TextDirection.rtl,
                    ),
                  ),
                ],
              ),
            ],
            // Evidence
            if (question.evidence.isNotEmpty) ...[
              const Divider(height: 24),
              const Text(
                '📖 المصادر المستخدمة',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                textDirection: TextDirection.rtl,
              ),
              const SizedBox(height: 8),
              ...question.evidence.map((ev) => EvidenceCard(evidence: ev)),
            ],
          ],
        ),
      ),
    );
  }
}
