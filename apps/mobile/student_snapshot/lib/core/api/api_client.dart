import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:student_snapshot/config/app_config.dart';
import 'package:student_snapshot/core/errors/app_exception.dart';
import 'package:student_snapshot/features/snapshot/data/snapshot_models.dart';

class NaqlaApiClient {
  final http.Client _client;

  NaqlaApiClient({http.Client? client}) : _client = client ?? http.Client();

  Future<SnapshotResponse> submitSnapshot({
    required String tenantId,
    String? imageUrl,
    String? ocrOverride,
    String? studentId,
  }) async {
    final uri = Uri.parse('${AppConfig.apiBaseUrl}/mobile/snapshot-questions');
    final body = {
      'tenant_id': tenantId,
      if (studentId != null) 'student_id': studentId,
      if (imageUrl != null) 'image_url': imageUrl,
      if (ocrOverride != null) 'ocr_override': ocrOverride,
      'language': 'ar',
      'answer_mode': 'tenant_knowledge_only',
    };

    try {
      final response = await _client
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        return SnapshotResponse.fromJson(
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
        );
      }
      throw AppException(
        'فشل الاتصال بالخادم (${response.statusCode})',
        code: response.statusCode,
      );
    } on SocketException {
      throw AppException('لا يوجد اتصال بالإنترنت. يرجى التحقق من الشبكة.');
    } on HttpException {
      throw AppException('حدث خطأ في الاتصال. يرجى المحاولة مجدداً.');
    }
  }

  Future<PlaybackInfo> getEvidencePlayback(String evidenceId) async {
    final uri = Uri.parse(
      '${AppConfig.apiBaseUrl}/mobile/evidence/$evidenceId/playback',
    );
    final response = await _client
        .get(uri)
        .timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      return PlaybackInfo.fromJson(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
      );
    }
    throw AppException('تعذر تحميل بيانات التشغيل.', code: response.statusCode);
  }
}
