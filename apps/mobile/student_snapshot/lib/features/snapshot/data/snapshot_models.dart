class SnapshotResponse {
  final String requestId;
  final List<DetectedQuestion> detectedQuestions;
  final List<String> warnings;

  const SnapshotResponse({
    required this.requestId,
    required this.detectedQuestions,
    required this.warnings,
  });

  factory SnapshotResponse.fromJson(Map<String, dynamic> json) {
    return SnapshotResponse(
      requestId: json['request_id'] as String,
      detectedQuestions: (json['detected_questions'] as List<dynamic>)
          .map((e) => DetectedQuestion.fromJson(e as Map<String, dynamic>))
          .toList(),
      warnings: (json['warnings'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }
}

class DetectedQuestion {
  final String questionId;
  final String questionText;
  final String answer;
  final double confidence;
  final List<EvidenceItem> evidence;

  const DetectedQuestion({
    required this.questionId,
    required this.questionText,
    required this.answer,
    required this.confidence,
    required this.evidence,
  });

  factory DetectedQuestion.fromJson(Map<String, dynamic> json) {
    return DetectedQuestion(
      questionId: json['question_id'] as String,
      questionText: json['question_text'] as String,
      answer: json['answer'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      evidence: (json['evidence'] as List<dynamic>)
          .map((e) => EvidenceItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  bool get hasAnswer => !answer.startsWith('⚠️');
}

enum EvidenceType { youtube, audio, video, pdf, docx, pptx, text, manual, unknown }

class EvidenceItem {
  final String evidenceId;
  final String sourceId;
  final String sourceTitle;
  final String excerpt;
  final EvidenceType sourceType;
  final int? startMs;
  final int? endMs;
  final String? youtubeVideoId;
  final String? playbackUrl;
  final int? pageNumber;

  const EvidenceItem({
    required this.evidenceId,
    required this.sourceId,
    required this.sourceTitle,
    required this.excerpt,
    required this.sourceType,
    this.startMs,
    this.endMs,
    this.youtubeVideoId,
    this.playbackUrl,
    this.pageNumber,
  });

  factory EvidenceItem.fromJson(Map<String, dynamic> json) {
    final typeStr = (json['source_type'] as String?) ?? 'text';
    final type = EvidenceType.values.firstWhere(
      (e) => e.name == typeStr,
      orElse: () => EvidenceType.unknown,
    );
    return EvidenceItem(
      evidenceId: json['evidence_id'] as String,
      sourceId: json['source_id'] as String,
      sourceTitle: json['source_title'] as String,
      excerpt: json['excerpt'] as String,
      sourceType: type,
      startMs: json['start_ms'] as int?,
      endMs: json['end_ms'] as int?,
      youtubeVideoId: json['youtube_video_id'] as String?,
      playbackUrl: json['playback_url'] as String?,
      pageNumber: json['page_number'] as int?,
    );
  }

  bool get isMedia =>
      sourceType == EvidenceType.youtube ||
      sourceType == EvidenceType.audio ||
      sourceType == EvidenceType.video;

  String get startTimeLabel {
    if (startMs == null) return '';
    final seconds = startMs! ~/ 1000;
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }
}

class PlaybackInfo {
  final String evidenceId;
  final String sourceType;
  final String? playbackUrl;
  final int? startMs;
  final int? endMs;
  final String? youtubeVideoId;

  const PlaybackInfo({
    required this.evidenceId,
    required this.sourceType,
    this.playbackUrl,
    this.startMs,
    this.endMs,
    this.youtubeVideoId,
  });

  factory PlaybackInfo.fromJson(Map<String, dynamic> json) {
    return PlaybackInfo(
      evidenceId: json['evidence_id'] as String,
      sourceType: json['source_type'] as String,
      playbackUrl: json['playback_url'] as String?,
      startMs: json['start_ms'] as int?,
      endMs: json['end_ms'] as int?,
      youtubeVideoId: json['youtube_video_id'] as String?,
    );
  }
}
