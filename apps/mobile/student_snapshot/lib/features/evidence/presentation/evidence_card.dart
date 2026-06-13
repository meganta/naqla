import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:student_snapshot/features/snapshot/data/snapshot_models.dart';

// Source type priority order (matches backend reranker)
const _SOURCE_PRIORITY = [
  EvidenceType.youtube,
  EvidenceType.video,
  EvidenceType.audio,
  EvidenceType.pptx,
  EvidenceType.pdf,
  EvidenceType.docx,
  EvidenceType.text,
  EvidenceType.manual,
  EvidenceType.unknown,
];

int evidenceSortOrder(EvidenceItem ev) => _SOURCE_PRIORITY.indexOf(ev.sourceType);

class EvidenceCard extends StatelessWidget {
  final EvidenceItem evidence;

  const EvidenceCard({super.key, required this.evidence});

  IconData get _icon {
    switch (evidence.sourceType) {
      case EvidenceType.youtube:
        return Icons.play_circle_filled;
      case EvidenceType.video:
        return Icons.videocam;
      case EvidenceType.audio:
        return Icons.headphones;
      case EvidenceType.pdf:
        return Icons.picture_as_pdf;
      case EvidenceType.pptx:
        return Icons.slideshow;
      case EvidenceType.docx:
        return Icons.description;
      default:
        return Icons.article;
    }
  }

  Color get _iconColor {
    switch (evidence.sourceType) {
      case EvidenceType.youtube:
        return Colors.red;
      case EvidenceType.video:
        return Colors.purple;
      case EvidenceType.audio:
        return Colors.teal;
      case EvidenceType.pdf:
        return Colors.orange;
      case EvidenceType.pptx:
        return Colors.deepOrange;
      case EvidenceType.docx:
        return Colors.blue;
      default:
        return Colors.blueGrey;
    }
  }

  Future<void> _openPlayback(BuildContext context) async {
    final url = evidence.playbackUrl;
    if (url == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('رابط التشغيل غير متاح')),
      );
      return;
    }

    final uri = Uri.parse(url);

    // Try YouTube app first, then browser
    if (evidence.sourceType == EvidenceType.youtube) {
      final youtubeVideoId = evidence.youtubeVideoId;
      final startSecs = evidence.startMs != null ? evidence.startMs! ~/ 1000 : 0;

      // Try YouTube app URI scheme
      if (youtubeVideoId != null) {
        final appUri = Uri.parse('vnd.youtube:$youtubeVideoId?t=$startSecs');
        if (await canLaunchUrl(appUri)) {
          await launchUrl(appUri, mode: LaunchMode.externalNonBrowserApplication);
          return;
        }
      }
    }

    // Fallback to browser
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تعذر فتح الرابط: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(_icon, color: _iconColor, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  evidence.sourceTitle,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  textDirection: TextDirection.rtl,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (evidence.pageNumber != null)
                Text(
                  'ص ${evidence.pageNumber}',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            evidence.excerpt,
            style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
            textDirection: TextDirection.rtl,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
          if (evidence.isMedia) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (evidence.startMs != null)
                  Text(
                    '⏱ ${evidence.startTimeLabel}',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                TextButton.icon(
                  onPressed: evidence.playbackUrl != null
                      ? () => _openPlayback(context)
                      : null,
                  icon: const Icon(Icons.play_arrow, size: 16),
                  label: Text(
                    evidence.sourceType == EvidenceType.youtube
                        ? 'فتح يوتيوب'
                        : 'تشغيل',
                    style: const TextStyle(fontSize: 12),
                  ),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    minimumSize: Size.zero,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
